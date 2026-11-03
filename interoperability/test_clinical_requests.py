"""Received orders retain their source identity and never become local events."""

import copy
import json
from datetime import date
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError

from clinical_records.models import Admission
from interoperability.clinical_requests import (
    ImportedRequestConflict,
    save_imported_medication_request,
    save_imported_service_request,
)
from interoperability.identity import (
    resolve_imported_patient,
    resolve_imported_professional,
)
from interoperability.models import ImportedMedicationRequest, ImportedServiceRequest
from prescriptions.models import Prescription

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "docs/interoperability/fhir-r4/json-v2/fixtures/independent-valid-bundle.json"
)
SOURCE = "https://partner.example"


@pytest.fixture
def identities_and_requests():
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))
    patient, _ = resolve_imported_patient(
        dni="12345678",
        first_name="Alex",
        last_name="Pérez",
        date_of_birth=date(1990, 1, 15),
        gender="unknown",
    )
    professional, _ = resolve_imported_professional(
        dni="23456789",
        first_name="Patricia",
        last_name="Gómez",
        license_number="MN 12345",
    )
    return (
        patient,
        professional,
        bundle["entry"][2]["resource"],
        bundle["entry"][3]["resource"],
    )


@pytest.mark.django_db
def test_requests_are_distinct_from_local_issue_and_replays_are_idempotent(
    identities_and_requests,
):
    patient, professional, service_resource, medication_resource = (
        identities_and_requests
    )
    service, created = save_imported_service_request(
        resource=service_resource,
        source_system=SOURCE,
        patient=patient,
        requester=professional,
    )
    medication, medication_created = save_imported_medication_request(
        resource=medication_resource,
        source_system=SOURCE,
        patient=patient,
        requester=professional,
    )
    assert created and medication_created
    assert service.patient_id == patient.pk and service.requester_id == professional.pk
    assert service.authored_on == "2026-10-27"  # No invented time.
    assert service.code_system == "http://loinc.org" and service.status == "active"
    assert medication.medication_display == "Medicamento de demostración"
    assert medication.dosage_instructions[0]["text"] == "Una dosis diaria"
    assert medication.dosage_instructions[0]["route"]["text"] == "Oral"
    assert medication.dispense_quantity == {"value": 10, "unit": "comprimidos"}
    assert medication.notes == [{"text": "Ejemplo académico"}]
    assert medication.authored_on == "2026-10-27T14:30:00Z"
    assert save_imported_service_request(
        resource=service_resource,
        source_system=SOURCE,
        patient=patient,
        requester=professional,
    ) == (service, False)
    assert save_imported_medication_request(
        resource=medication_resource,
        source_system=SOURCE,
        patient=patient,
        requester=professional,
    ) == (medication, False)
    assert ImportedServiceRequest.objects.count() == 1
    assert ImportedMedicationRequest.objects.count() == 1
    assert Prescription.objects.count() == 0 and Admission.objects.count() == 0


@pytest.mark.django_db
def test_reused_external_id_with_changed_content_is_rejected(identities_and_requests):
    patient, professional, service_resource, medication_resource = (
        identities_and_requests
    )
    save_imported_service_request(
        resource=service_resource,
        source_system=SOURCE,
        patient=patient,
        requester=professional,
    )
    save_imported_medication_request(
        resource=medication_resource,
        source_system=SOURCE,
        patient=patient,
        requester=professional,
    )
    changed_service = copy.deepcopy(service_resource)
    changed_service["status"] = "completed"
    with pytest.raises(ImportedRequestConflict):
        save_imported_service_request(
            resource=changed_service,
            source_system=SOURCE,
            patient=patient,
            requester=professional,
        )
    changed_medication = copy.deepcopy(medication_resource)
    changed_medication["dosageInstruction"][0]["text"] = "Twice daily"
    with pytest.raises(ImportedRequestConflict):
        save_imported_medication_request(
            resource=changed_medication,
            source_system=SOURCE,
            patient=patient,
            requester=professional,
        )
    assert ImportedServiceRequest.objects.get().status == "active"
    assert (
        ImportedMedicationRequest.objects.get().dosage_instructions[0]["text"]
        == "Una dosis diaria"
    )


@pytest.mark.django_db
def test_missing_medication_directions_do_not_create_a_record(identities_and_requests):
    patient, professional, _, medication_resource = identities_and_requests
    medication_resource.pop("dosageInstruction")
    with pytest.raises(ValidationError):
        save_imported_medication_request(
            resource=medication_resource,
            source_system=SOURCE,
            patient=patient,
            requester=professional,
        )
    assert not ImportedMedicationRequest.objects.exists()
