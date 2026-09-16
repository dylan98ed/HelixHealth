from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from access_control.actors import ActorContext, ActorRole
from access_control.roles import MEDICAL_PROFESSIONAL_GROUP
from catalogs.models import MedicationEntry
from patients.models import Patient
from prescriptions.models import Prescription, PrescriptionItem
from prescriptions.services import PrescriptionConflictError, issue_prescription
from professionals.models import HospitalService, Professional, Specialty


def patient() -> Patient:
    return Patient.objects.create(
        dni="12345678",
        clinical_record_number="HC-RX-01",
        first_name="Alex",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        sex="unspecified",
        phone="+54 11 5555-0101",
        email="alex@example.test",
        address="Test address",
        health_insurer="Test insurer",
    )


def prescriber(user_factory):
    user = user_factory(username="prescriber")
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    specialty = Specialty.objects.create(code="rx", name="Prescription")
    service = HospitalService.objects.create(code="rx", name="Prescription")
    professional = Professional.objects.create(
        user=user,
        dni="70123456",
        registration_number="PR-RX-0001",
        license_number="MN 000001",
        first_name="Eva",
        last_name="Doctor",
        date_of_birth=date(1985, 1, 1),
        specialty=specialty,
        hospital_service=service,
        registration_completed_at=timezone.now(),
    )
    return user, professional


def medication(user) -> MedicationEntry:
    return MedicationEntry.objects.create(
        system="https://catalog.example/medications",
        version="2026",
        code="MED-1",
        name="Ibuprofen",
        presentation="400 mg tablet",
        source_label="Test catalog",
        created_by=user,
    )


def data(entry: MedicationEntry) -> list[dict[str, object]]:
    return [
        {
            "medication_id": entry.pk,
            "dose_value": Decimal("400"),
            "dose_unit": "mg",
            "route": "oral",
            "frequency": "every 8 hours",
            "duration_days": 5,
            "instructions": "with food",
        }
    ]


def actor(user) -> ActorContext:
    return ActorContext(
        user_id=user.pk, roles=frozenset({ActorRole.MEDICAL_PROFESSIONAL})
    )


@pytest.mark.django_db
def test_issuance_is_immutable_atomic_and_replays_exact_request(user_factory):
    target = patient()
    user, professional = prescriber(user_factory)
    entry = medication(user)
    key = uuid4()

    result = issue_prescription(
        actor=actor(user),
        patient=target,
        request_key=key,
        reason_entry_id=None,
        items=data(entry),
    )
    replay = issue_prescription(
        actor=actor(user),
        patient=target,
        request_key=key,
        reason_entry_id=None,
        items=data(entry),
    )

    assert result.created is True
    assert replay.created is False
    assert replay.prescription.pk == result.prescription.pk
    assert Prescription.objects.count() == 1
    assert PrescriptionItem.objects.count() == 1
    assert result.prescription.prescriber == professional
    assert result.prescription.fhir_xml.startswith(b"<?xml")
    assert result.prescription.snapshot["patient"]["dni"] == target.dni
    with pytest.raises(PrescriptionConflictError):
        issue_prescription(
            actor=actor(user),
            patient=target,
            request_key=key,
            reason_entry_id=None,
            items=[{**data(entry)[0], "duration_days": 6}],
        )
    assert Prescription.objects.count() == 1


@pytest.mark.django_db
def test_api_rejects_spoofed_or_unknown_input_without_writing(client, user_factory):
    target = patient()
    user, _ = prescriber(user_factory)
    client.force_login(user)
    url = reverse("prescriptions:api-list", args=[target.pk])
    unknown = {
        "request_key": str(uuid4()),
        "items": [
            {
                "medication_id": 999999,
                "dose_value": "400",
                "dose_unit": "mg",
                "route": "oral",
                "frequency": "every 8 hours",
                "duration_days": 5,
            }
        ],
        "prescriber_id": 1,
    }

    response = client.post(url, unknown, content_type="application/json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Prescription.objects.count() == 0


@pytest.mark.django_db
def test_anonymous_html_prescription_routes_redirect_to_sign_in(client):
    patient_pk = 99999
    identifier = uuid4()
    routes = (
        reverse("prescriptions:list", args=[patient_pk]),
        reverse("prescriptions:issue", args=[patient_pk]),
        reverse("prescriptions:detail", args=[patient_pk, identifier]),
        reverse("prescriptions:report", args=[patient_pk, identifier]),
        reverse("prescriptions:xml", args=[patient_pk, identifier]),
    )

    for route in routes:
        response = client.get(route)

        assert response.status_code == status.HTTP_302_FOUND
        assert response.url.startswith(reverse("login"))


@pytest.mark.django_db
def test_report_and_xml_recheck_current_access(client, user_factory):
    target = patient()
    user, professional = prescriber(user_factory)
    entry = medication(user)
    prescription = issue_prescription(
        actor=actor(user),
        patient=target,
        request_key=uuid4(),
        reason_entry_id=None,
        items=data(entry),
    ).prescription
    client.force_login(user)
    report = reverse("prescriptions:report", args=[target.pk, prescription.identifier])
    xml = reverse("prescriptions:xml", args=[target.pk, prescription.identifier])
    assert client.get(report).status_code == 200
    assert client.get(xml).status_code == 200

    professional.is_active = False
    professional.save(update_fields=["is_active"])
    assert client.get(report).status_code == status.HTTP_403_FORBIDDEN
    assert client.get(xml).status_code == status.HTTP_403_FORBIDDEN
