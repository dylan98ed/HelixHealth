from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from access_control.actors import ActorContext, ActorRole
from access_control.roles import ADMINISTRATIVE_GROUP, MEDICAL_PROFESSIONAL_GROUP
from clinical_records.care_services import (
    CareConfirmationRequired,
    assign_care_relationship,
    revoke_care_relationship,
)
from clinical_records.models import CareRelationship
from patients.models import Patient
from patients.services import deactivate_patient
from professionals.models import HospitalService, Professional, Specialty
from professionals.services import deactivate_professional, reactivate_professional


@pytest.fixture
def care_context(user_factory):
    admin = user_factory(username="care-admin")
    administrative_group, _ = Group.objects.get_or_create(name=ADMINISTRATIVE_GROUP)
    admin.groups.add(administrative_group)
    medical = user_factory(username="care-medical")
    medical_group, _ = Group.objects.get_or_create(name=MEDICAL_PROFESSIONAL_GROUP)
    medical.groups.add(medical_group)
    specialty, _ = Specialty.objects.get_or_create(
        code="general-medicine", defaults={"name": "General medicine"}
    )
    service, _ = HospitalService.objects.get_or_create(
        code="inpatient-ward", defaults={"name": "Inpatient ward"}
    )
    professional = Professional.objects.create(
        user=medical,
        dni="12345678",
        registration_number="PR-CARE-1",
        license_number="MN 123",
        first_name="Care",
        last_name="Professional",
        date_of_birth=date(1990, 1, 1),
        specialty=specialty,
        hospital_service=service,
        registration_completed_at=timezone.now(),
    )
    patient = Patient.objects.create(
        dni="87654321",
        first_name="Care",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        sex="unspecified",
        phone="123456789",
        email="care@example.test",
        address="Care Street",
        health_insurer="Care Health",
    )
    actor = ActorContext(admin.pk, frozenset({ActorRole.ADMINISTRATIVE}))
    return admin, medical, professional, patient, actor


@pytest.mark.django_db
def test_assign_duplicate_revoke_and_reassign_preserve_history(care_context):
    admin, _, professional, patient, actor = care_context
    first, created = assign_care_relationship(
        actor=actor, patient=patient, professional_dni=" 12345678 "
    )
    assert created and first.assigned_by_id == admin.pk and first.assigned_at
    duplicate, created = assign_care_relationship(
        actor=actor, patient=patient, professional_dni="12345678"
    )
    assert not created and duplicate.pk == first.pk
    with pytest.raises(CareConfirmationRequired):
        revoke_care_relationship(
            actor=actor, patient=patient, relationship=first, confirmed=False
        )
    revoked = revoke_care_relationship(
        actor=actor, patient=patient, relationship=first, confirmed=True
    )
    assert (
        not revoked.is_active
        and revoked.revoked_by_id == admin.pk
        and revoked.revoked_at
    )
    repeated = revoke_care_relationship(
        actor=actor, patient=patient, relationship=first, confirmed=True
    )
    assert repeated.revoked_at == revoked.revoked_at
    second, created = assign_care_relationship(
        actor=actor, patient=patient, professional_dni="12345678"
    )
    assert created and second.pk != first.pk
    assert list(
        CareRelationship.objects.filter(patient=patient).values_list(
            "is_active", flat=True
        )
    ) == [True, False]


@pytest.mark.django_db
def test_care_constraints_and_endpoint_eligibility(care_context):
    admin, medical, professional, patient, actor = care_context
    first, _ = assign_care_relationship(
        actor=actor, patient=patient, professional_dni="12345678"
    )
    with pytest.raises(ProtectedError):
        patient.delete()
    with pytest.raises(ProtectedError):
        professional.delete()
    with pytest.raises(IntegrityError), transaction.atomic():
        CareRelationship.objects.create(
            patient=patient, professional=professional, assigned_by=admin
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        CareRelationship.objects.create(
            patient_id=999999, professional=professional, assigned_by=admin
        )
        connection.check_constraints()
    with pytest.raises(IntegrityError), transaction.atomic():
        CareRelationship.objects.create(
            patient=patient,
            professional=professional,
            assigned_by=admin,
            is_active=False,
        )
    wrong = Patient.objects.create(
        dni="76543210",
        first_name="Wrong",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        sex="unspecified",
        phone="123456789",
        email="wrong@example.test",
        address="Wrong Street",
        health_insurer="Care Health",
    )
    with pytest.raises(ValidationError):
        revoke_care_relationship(
            actor=actor, patient=wrong, relationship=first, confirmed=True
        )
    with pytest.raises(PermissionError):
        assign_care_relationship(
            actor=ActorContext(medical.pk, frozenset({ActorRole.MEDICAL_PROFESSIONAL})),
            patient=patient,
            professional_dni="12345678",
        )
    medical.is_active = False
    medical.save(update_fields=["is_active"])
    with pytest.raises(ValidationError):
        assign_care_relationship(
            actor=actor, patient=wrong, professional_dni="12345678"
        )


@pytest.mark.django_db
def test_deactivation_revokes_relationship_and_reactivation_does_not_restore(
    care_context,
):
    _, _, professional, patient, actor = care_context
    assignment, _ = assign_care_relationship(
        actor=actor, patient=patient, professional_dni="12345678"
    )
    deactivate_professional(actor=actor, professional=professional, confirmed=True)
    assignment.refresh_from_db()
    assert not assignment.is_active and assignment.revoked_at is not None
    reactivate_professional(actor=actor, professional=professional, confirmed=True)
    assignment.refresh_from_db()
    assert not assignment.is_active
    reassigned, _ = assign_care_relationship(
        actor=actor, patient=patient, professional_dni="12345678"
    )
    deactivate_patient(actor=actor, patient=patient, confirmed=True)
    reassigned.refresh_from_db()
    assert (
        not reassigned.is_active
        and CareRelationship.objects.filter(patient=patient, is_active=True).count()
        == 0
    )


@pytest.mark.django_db
def test_care_api_contract_and_csrf(care_context):
    admin, medical, professional, patient, _ = care_context
    path = reverse("patients:api-care-team", args=[patient.pk])
    anonymous = Client()
    assert anonymous.get(path).status_code == 403
    wrong_role = Client()
    wrong_role.force_login(medical)
    assert wrong_role.get(path).status_code == 403
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin)
    assert client.post(path, {"professional_dni": professional.dni}).status_code == 403
    token = (
        client.get(reverse("patients:care-team", args=[patient.pk]))
        .cookies["csrftoken"]
        .value
    )
    headers = {"HTTP_X_CSRFTOKEN": token}
    assert client.get(path).json() == {
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }
    created = client.post(path, {"professional_dni": professional.dni}, **headers)
    assert created.status_code == 201
    assert set(created.json()) == {
        "id",
        "patient_id",
        "professional_id",
        "professional_registration_number",
        "is_active",
        "assigned_at",
        "revoked_at",
    }
    assert (
        created.json()["professional_registration_number"]
        == professional.registration_number
    )
    assert (
        client.post(path, {"professional_dni": professional.dni}, **headers).status_code
        == 200
    )
    assert client.get(path).json()["count"] == 1
    revoke_path = reverse(
        "patients:api-revoke-care", args=[patient.pk, created.json()["id"]]
    )
    assert client.post(revoke_path, {"confirm": False}, **headers).status_code == 400
    assert client.post(revoke_path, {"confirm": True}, **headers).status_code == 200
    assert client.get(path).json()["count"] == 0
