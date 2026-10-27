from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from access_control.roles import MEDICAL_PROFESSIONAL_GROUP
from clinical_records.care_services import assign_care_relationship
from clinical_records.models import Admission, CareRelationship
from clinical_records.test_care_relationships import care_context as _care_context
from patients.models import Patient
from professionals.models import Professional

care_context = _care_context


@pytest.mark.django_db
def test_html_and_api_authorization_precede_patient_lookup(care_context):
    admin, medical, _, patient, _ = care_context
    html = reverse("patients:care-team", args=[patient.pk])
    api = reverse("patients:api-care-team", args=[patient.pk])
    anonymous = Client()
    assert anonymous.get(html).status_code == 302
    assert anonymous.get(api).status_code == 403
    wrong = Client()
    wrong.force_login(medical)
    assert wrong.get(html).status_code == 403
    assert wrong.get(api).status_code == 403
    assert (
        wrong.get(reverse("patients:api-care-team", args=[999999])).status_code == 403
    )
    allowed = Client()
    allowed.force_login(admin)
    assert (
        allowed.get(reverse("patients:api-care-team", args=[999999])).status_code == 404
    )
    assert allowed.get(reverse("patients:care-team", args=[999999])).status_code == 404


@pytest.mark.django_db
def test_assignment_payload_validation_inactive_patient_and_no_notes(care_context):
    admin, _, professional, patient, _ = care_context
    api = reverse("patients:api-care-team", args=[patient.pk])
    client = Client()
    client.force_login(admin)
    html = reverse("patients:care-team", args=[patient.pk])
    found = client.get(html, {"professional_dni": professional.dni})
    assert found.status_code == 200 and b"Professional found" in found.content
    assert b"Assign professional" in found.content
    invalid = client.get(html, {"professional_dni": "12.345.678"})
    assert invalid.status_code == 200 and b"alert" in invalid.content
    assert client.post(api, {"professional_dni": "12.345.678"}).status_code == 400
    assert (
        client.post(
            api, {"professional_dni": professional.dni, "note": "secret"}
        ).status_code
        == 400
    )
    assert CareRelationship.objects.count() == 0
    created = client.post(api, {"professional_dni": professional.dni})
    assert created.status_code == 201
    assert "note" not in str(created.json()).lower()
    assert "license_number" not in str(created.json())
    patient.is_active = False
    patient.save(update_fields=["is_active"])
    assert client.post(api, {"professional_dni": professional.dni}).status_code == 400
    # An administrator can still inspect retained assignment history through the patient record.
    assert client.get(api).status_code == 200


@pytest.mark.django_db
def test_assignment_list_is_bounded_and_revoke_rejects_wrong_patient(
    care_context, user_factory
):
    admin, _, original, patient, _ = care_context
    group = Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP)
    for index in range(21):
        user = user_factory(username=f"care-page-{index}")
        user.groups.add(group)
        professional = Professional.objects.create(
            user=user,
            dni=f"4{index:07d}",
            registration_number=f"PR-CARE-PAGE-{index}",
            license_number=f"MN PAGE {index}",
            first_name="Care",
            last_name=f"Page {index}",
            date_of_birth=date(1990, 1, 1),
            specialty=original.specialty,
            hospital_service=original.hospital_service,
            registration_completed_at=timezone.now(),
        )
        CareRelationship.objects.create(
            patient=patient, professional=professional, assigned_by=admin
        )
    client = Client()
    client.force_login(admin)
    api = reverse("patients:api-care-team", args=[patient.pk])
    first = client.get(api).json()
    second = client.get(api + "?page=2").json()
    assert first["count"] == 21 and len(first["results"]) == 20
    assert len(second["results"]) == 1 and first["next"] and second["previous"]
    other = Patient.objects.create(
        dni="76543210",
        first_name="Other",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        sex="unspecified",
        phone="123456789",
        email="other@example.test",
        address="Other Street",
        health_insurer="Care Health",
    )
    wrong = reverse(
        "patients:api-revoke-care", args=[other.pk, first["results"][0]["id"]]
    )
    assert client.post(wrong, {"confirm": True}).status_code == 404


@pytest.mark.django_db
def test_http_deactivation_revokes_care_and_preserves_admission(care_context):
    admin, _, professional, patient, actor = care_context
    admission = Admission.objects.create(
        patient=patient,
        professional=professional,
        consultation_reason="Care history",
        systolic_blood_pressure=120,
        diastolic_blood_pressure=80,
        heart_rate=72,
        temperature="36.7",
    )
    relationship, _ = assign_care_relationship(
        actor=actor, patient=patient, professional_dni=professional.dni
    )
    client = Client()
    client.force_login(admin)
    assert (
        client.post(
            reverse("professionals:api-deactivate", args=[professional.pk]),
            data={"confirm": True},
        ).status_code
        == 200
    )
    relationship.refresh_from_db()
    assert not relationship.is_active and relationship.revoked_by_id == admin.pk
    assert Admission.objects.filter(
        pk=admission.pk, patient=patient, professional=professional
    ).exists()
    assert (
        client.post(
            reverse("professionals:api-reactivate", args=[professional.pk]),
            data={"confirm": True},
        ).status_code
        == 200
    )
    relationship.refresh_from_db()
    assert not relationship.is_active
    second, _ = assign_care_relationship(
        actor=actor, patient=patient, professional_dni=professional.dni
    )
    assert (
        client.post(
            reverse("patients:api-deactivate", args=[patient.pk]),
            data={"confirm": True},
        ).status_code
        == 200
    )
    second.refresh_from_db()
    assert not second.is_active and second.revoked_by_id == admin.pk
    assert Admission.objects.filter(pk=admission.pk).exists()
