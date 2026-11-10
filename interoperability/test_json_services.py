"""Atomic import and replay checks for complete FHIR JSON Bundles."""

import json
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from access_control.actors import ActorContext, ActorRole
from access_control.roles import MEDICAL_PROFESSIONAL_GROUP
from interoperability.json_services import JsonImportConflict, import_json_bundle
from interoperability.models import (
    ExternalClinicalRecord,
    ImportedMedicationRequest,
    ImportedServiceRequest,
    JsonImportBatch,
)
from patients.models import Patient
from professionals.models import HospitalService, Professional, Specialty

FIXTURE = Path("docs/interoperability/fhir-r4/json-v2/fixtures/independent-valid-bundle.json")
SOURCE = "https://partner.example"


@pytest.fixture
def importing_actor(user_factory) -> ActorContext:
    user = user_factory(username="json-import-service-doctor")
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    specialty = Specialty.objects.create(code="json-import-service", name="JSON Import")
    hospital_service = HospitalService.objects.create(
        code="json-import-service", name="JSON Import"
    )
    Professional.objects.create(
        user=user, dni="70123456", registration_number="PR-JSON-IMPORT",
        license_number="MN 701234", first_name="Import", last_name="Doctor",
        date_of_birth=date(1980, 1, 1), specialty=specialty,
        hospital_service=hospital_service, registration_completed_at=timezone.now(),
    )
    return ActorContext(user_id=user.pk, roles=frozenset({ActorRole.MEDICAL_PROFESSIONAL}))


def _bundle() -> dict:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["entry"].append({
        "fullUrl": "urn:uuid:50000000-0000-4000-8000-000000000003",
        "resource": {
            "resourceType": "Observation", "id": "pulse-service-test", "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
            "subject": document["entry"][2]["resource"]["subject"],
            "effectiveDateTime": "2026-10-27T14:30:00Z",
            "valueQuantity": {"value": 72, "system": "http://unitsofmeasure.org", "code": "/min"},
        },
    })
    return document


def _raw(document: dict) -> bytes:
    return json.dumps(document, ensure_ascii=False).encode()


@pytest.mark.django_db
def test_replay_observation_deduplication_and_atomic_conflict(importing_actor):
    document = _bundle()
    key = uuid4()
    first = import_json_bundle(
        actor=importing_actor, source_system=SOURCE, request_key=key,
        raw_json=_raw(document),
    )
    assert first.created
    assert import_json_bundle(
        actor=importing_actor, source_system=SOURCE, request_key=key,
        raw_json=_raw(document),
    ).batch.pk == first.batch.pk
    document["timestamp"] = "2026-10-28T15:00:00Z"
    second = import_json_bundle(
        actor=importing_actor, source_system=SOURCE, request_key=uuid4(),
        raw_json=_raw(document),
    )
    assert second.created
    assert second.batch.summary["new_service_request_count"] == 0
    assert second.batch.summary["new_medication_request_count"] == 0
    assert second.batch.summary["new_observation_count"] == 0
    assert (Patient.all_objects.count(), Professional.objects.count()) == (1, 2)
    assert (ImportedServiceRequest.objects.count(), ImportedMedicationRequest.objects.count()) == (1, 1)
    assert (ExternalClinicalRecord.objects.count(), JsonImportBatch.objects.count()) == (1, 2)

    document["timestamp"] = "2026-10-29T15:00:00Z"
    document["entry"][2]["resource"]["id"] = "new-service-before-conflict"
    document["entry"][3]["resource"]["note"] = [{"text": "Changed medication note"}]
    with pytest.raises(JsonImportConflict, match="different content"):
        import_json_bundle(
            actor=importing_actor, source_system=SOURCE, request_key=uuid4(),
            raw_json=_raw(document),
        )
    assert (ImportedServiceRequest.objects.count(), ImportedMedicationRequest.objects.count()) == (1, 1)
    assert (ExternalClinicalRecord.objects.count(), JsonImportBatch.objects.count()) == (1, 2)


@pytest.mark.django_db
def test_json_upload_requires_active_medical_profile(importing_actor, client, user_factory):
    url = reverse("interoperability:json-import-upload")
    assert client.get(url).status_code == 302
    client.force_login(user_factory(username="json-import-no-role"))
    assert client.get(url).status_code == 403
    professional = Professional.objects.get(user_id=importing_actor.user_id)
    professional.is_active = False
    professional.save(update_fields=["is_active"])
    client.force_login(get_user_model().objects.get(pk=importing_actor.user_id))
    assert client.get(url).status_code == 403


@pytest.mark.django_db
def test_vital_sign_only_bundle_imports_without_requests(importing_actor):
    document = _bundle()
    document["entry"] = [
        entry for entry in document["entry"]
        if entry["resource"]["resourceType"] not in {"ServiceRequest", "MedicationRequest"}
    ]
    result = import_json_bundle(
        actor=importing_actor, source_system=SOURCE, request_key=uuid4(),
        raw_json=_raw(document),
    )
    assert result.created
    assert result.batch.summary["new_observation_count"] == 1
    assert result.batch.summary["service_request_count"] == 0
    assert result.batch.summary["medication_request_count"] == 0
    assert ExternalClinicalRecord.objects.filter(patient=result.batch.patient).count() == 1
    assert not ImportedServiceRequest.objects.exists()
    assert not ImportedMedicationRequest.objects.exists()
