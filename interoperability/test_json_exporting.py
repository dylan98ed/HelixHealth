"""FHIR JSON export must round-trip without changing local clinical state."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from django.contrib.auth.models import Group
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from access_control.actors import ActorContext, ActorRole
from access_control.roles import MEDICAL_PROFESSIONAL_GROUP
from catalogs.models import MedicationEntry
from clinical_records.models import Admission
from interoperability.clinical_requests import (
    save_imported_medication_request,
    save_imported_service_request,
)
from interoperability.identity import (
    resolve_imported_patient,
    resolve_imported_professional,
)
from interoperability.json_exporting import (
    JsonExportSelectionError,
    export_selected_json,
    json_export_filename,
)
from interoperability.json_importing import parse_json_bundle
from interoperability.models import ExternalClinicalRecord, ImportedServiceRequest
from prescriptions.services import issue_prescription
from professionals.models import HospitalService, Professional, Specialty

FIXTURE = Path(
    "docs/interoperability/fhir-r4/json-v2/fixtures/independent-valid-bundle.json"
)


@pytest.fixture
def export_records(user_factory):
    patient, _ = resolve_imported_patient(
        dni="12345678",
        first_name="Alex",
        last_name="Pérez",
        date_of_birth=date(1990, 1, 15),
        gender="unknown",
    )
    user = user_factory(username="json-export-doctor")
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    specialty = Specialty.objects.create(code="json-export", name="JSON Export")
    service = HospitalService.objects.create(code="json-export", name="JSON Export")
    practitioner = Professional.objects.create(
        user=user,
        dni="23456789",
        registration_number="PR-JSON-EXPORT",
        license_number="MN 12345",
        first_name="Patricia",
        last_name="Gómez",
        date_of_birth=date(1980, 1, 1),
        specialty=specialty,
        hospital_service=service,
        registration_completed_at=timezone.now(),
    )
    resources = json.loads(FIXTURE.read_text(encoding="utf-8"))["entry"]
    procedure, _ = save_imported_service_request(
        resource=resources[2]["resource"],
        source_system="https://partner.example",
        patient=patient,
        requester=practitioner,
    )
    medication, _ = save_imported_medication_request(
        resource=resources[3]["resource"],
        source_system="https://partner.example",
        patient=patient,
        requester=practitioner,
    )
    catalog = MedicationEntry.objects.create(
        system="https://catalog.example/medications",
        version="2026",
        code="MED-2",
        name="Ibuprofen",
        presentation="400 mg tablet",
        source_label="Test",
        created_by=user,
    )
    prescription = issue_prescription(
        actor=ActorContext(
            user_id=user.pk, roles=frozenset({ActorRole.MEDICAL_PROFESSIONAL})
        ),
        patient=patient,
        request_key=uuid4(),
        reason_entry_id=None,
        items=[
            {
                "medication_id": catalog.pk,
                "dose_value": Decimal("400"),
                "dose_unit": "mg",
                "route": "oral",
                "frequency": "every 8 hours",
                "duration_days": 5,
                "instructions": "with food",
            }
        ],
    ).prescription
    return patient, practitioner, procedure, medication, prescription


@pytest.mark.django_db
def test_exports_received_and_local_medication_with_stable_ids(export_records):
    patient, practitioner, procedure, medication, prescription = export_records
    selection = {
        "patient": patient,
        "service_request_ids": [procedure.pk],
        "medication_request_ids": [medication.pk],
        "prescription_ids": [prescription.identifier],
    }
    first = export_selected_json(**selection)
    second = export_selected_json(**selection)
    parsed = parse_json_bundle(first)
    assert json_export_filename(first, student_last_name="Dá Silva") == (
        "FHIR_12345678_23456789_DaSilva.json"
    )
    assert parsed.patient_dni == patient.dni
    assert parsed.practitioner_dni == practitioner.dni
    assert len(parsed.service_requests) == 1
    assert len(parsed.medication_requests) == 2
    first_ids = [entry["resource"]["id"] for entry in json.loads(first)["entry"]]
    second_ids = [entry["resource"]["id"] for entry in json.loads(second)["entry"]]
    assert first_ids == second_ids
    assert ImportedServiceRequest.objects.count() == 1


@pytest.mark.django_db
def test_rejects_incomplete_and_wrong_patient_selections(export_records):
    patient, _, procedure, medication, _ = export_records
    with pytest.raises(JsonExportSelectionError, match="medication"):
        export_selected_json(
            patient=patient,
            service_request_ids=[procedure.pk],
            medication_request_ids=[],
            prescription_ids=[],
        )
    with pytest.raises(Http404):
        export_selected_json(
            patient=patient,
            service_request_ids=[procedure.pk + 9999],
            medication_request_ids=[medication.pk],
            prescription_ids=[],
        )


@pytest.mark.django_db
def test_optional_vital_sign_and_api_download(export_records, client):
    patient, practitioner, procedure, medication, _ = export_records
    observation = {
        "resourceType": "Observation",
        "id": "pulse-export-test",
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
        "subject": {"reference": "Patient/unused"},
        "effectiveDateTime": "2026-10-27T14:30:00Z",
        "valueQuantity": {
            "value": 72,
            "system": "http://unitsofmeasure.org",
            "code": "/min",
        },
    }
    record = ExternalClinicalRecord.objects.create(
        patient=patient,
        source_system="https://partner.example",
        resource_type="Observation",
        external_identifier="pulse-export-test",
        kind=ExternalClinicalRecord.KIND_OBSERVATION,
        source_recorded_at=timezone.now(),
        external_author={"professional_id": practitioner.pk},
        content=observation,
        content_digest="a" * 64,
    )
    url = reverse("interoperability:api-json-export", args=[patient.pk])
    payload = {
        "service_request_ids": [procedure.pk],
        "medication_request_ids": [medication.pk],
        "observation_ids": [record.pk],
    }
    assert client.post(url, payload, content_type="application/json").status_code in (
        401,
        403,
    )
    client.force_login(practitioner.user)
    response = client.post(url, json.dumps(payload), content_type="application/json")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/fhir+json")
    assert response["Content-Disposition"].endswith(
        'filename="FHIR_12345678_23456789_Gomez.json"'
    )
    assert (
        len(parse_json_bundle(b"".join(response.streaming_content)).observations) == 1
    )


@pytest.mark.django_db
def test_rejects_requests_from_different_practitioners(export_records):
    patient, _, procedure, _, _ = export_records
    other, _ = resolve_imported_professional(
        dni="34567890",
        first_name="Other",
        last_name="Doctor",
        license_number="MN 67890",
    )
    resource = json.loads(FIXTURE.read_text(encoding="utf-8"))["entry"][3]["resource"]
    resource["id"] = "medication-other-doctor"
    medication, _ = save_imported_medication_request(
        resource=resource,
        source_system="https://partner.example",
        patient=patient,
        requester=other,
    )
    with pytest.raises(JsonExportSelectionError, match="same practitioner"):
        export_selected_json(
            patient=patient,
            service_request_ids=[procedure.pk],
            medication_request_ids=[medication.pk],
            prescription_ids=[],
        )


@pytest.mark.django_db
def test_api_denies_missing_role_and_inactive_profile(
    export_records, client, user_factory
):
    patient, practitioner, procedure, medication, _ = export_records
    url = reverse("interoperability:api-json-export", args=[patient.pk])
    payload = json.dumps(
        {
            "service_request_ids": [procedure.pk],
            "medication_request_ids": [medication.pk],
        }
    )
    client.force_login(user_factory(username="json-export-no-role"))
    assert client.post(url, payload, content_type="application/json").status_code == 403
    practitioner.is_active = False
    practitioner.save(update_fields=["is_active"])
    client.force_login(practitioner.user)
    assert client.post(url, payload, content_type="application/json").status_code == 403


@pytest.mark.django_db
def test_local_admission_exports_three_vitals_alone_and_with_prescription(
    export_records, client
):
    patient, practitioner, _, _, prescription = export_records
    admission = Admission.objects.create(
        patient=patient,
        professional=practitioner,
        consultation_reason="Fever",
        systolic_blood_pressure=120,
        diastolic_blood_pressure=80,
        heart_rate=72,
        temperature=Decimal("38.0"),
    )
    selection = {
        "patient": patient,
        "service_request_ids": [],
        "medication_request_ids": [],
        "prescription_ids": [],
        "admission_ids": [admission.pk],
    }
    vital_only = parse_json_bundle(export_selected_json(**selection))
    assert not vital_only.service_requests and not vital_only.medication_requests
    assert {
        resource["code"]["coding"][0]["code"] for resource in vital_only.observations
    } == {
        "85354-9",
        "8867-4",
        "8310-5",
    }
    selection["prescription_ids"] = [prescription.identifier]
    combined = parse_json_bundle(export_selected_json(**selection))
    assert len(combined.observations) == 3
    assert len(combined.medication_requests) == 1
    client.force_login(practitioner.user)
    response = client.post(
        reverse("interoperability:api-json-export", args=[patient.pk]),
        json.dumps({"admission_ids": [admission.pk]}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response["Content-Disposition"].endswith(
        'filename="FHIR_12345678_23456789_Gomez.json"'
    )
    assert (
        len(parse_json_bundle(b"".join(response.streaming_content)).observations) == 3
    )


@pytest.mark.django_db
def test_administrative_admission_cannot_be_exported_as_physician_authored(
    export_records,
):
    patient, practitioner, _, _, _ = export_records
    admission = Admission.objects.create(
        patient=patient,
        recorded_by_id=practitioner.user_id,
        consultation_reason="Administrative",
        systolic_blood_pressure=120,
        diastolic_blood_pressure=80,
        heart_rate=72,
        temperature=Decimal("37.0"),
    )
    with pytest.raises(JsonExportSelectionError, match="administrators"):
        export_selected_json(
            patient=patient,
            service_request_ids=[],
            medication_request_ids=[],
            prescription_ids=[],
            admission_ids=[admission.pk],
        )
