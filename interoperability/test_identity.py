"""Identity reconciliation for incoming FHIR patients and practitioners."""

from datetime import date

import pytest
from django.db import IntegrityError, transaction

from interoperability.identity import (
    ExternalIdentityConflict,
    resolve_imported_patient,
    resolve_imported_professional,
)
from patients.models import Patient
from professionals.models import Professional


@pytest.mark.django_db
def test_new_imported_people_are_marked_and_have_no_login() -> None:
    patient, patient_created = resolve_imported_patient(
        dni="12345678",
        first_name="Alex",
        last_name="Pérez",
        date_of_birth=date(1990, 1, 15),
        gender="unknown",
    )
    professional, professional_created = resolve_imported_professional(
        dni="23456789",
        first_name="Patricia",
        last_name="Gómez",
        license_number="MN 12345",
    )

    assert patient_created and professional_created
    assert patient.is_external and professional.is_external
    assert patient.created_at and professional.created_at
    assert patient.sex == "U" and patient.phone == "" and patient.address == ""
    assert professional.user_id is None
    assert not professional.is_registration_complete
    assert professional.registration_number is None
    assert professional.license_number == "MN 12345"


@pytest.mark.django_db
def test_inactive_people_are_reused_without_reactivation_or_origin_change() -> None:
    patient = Patient.all_objects.create(
        dni="12345678",
        first_name="Alex",
        last_name="Pérez",
        date_of_birth=date(1990, 1, 15),
        sex="U",
        phone="",
        email="",
        address="",
        health_insurer="",
        is_active=False,
    )
    professional = Professional.objects.create(
        dni="23456789",
        first_name="Patricia",
        last_name="Gómez",
        license_number="MN 12345",
        is_active=False,
    )

    found_patient, new_patient = resolve_imported_patient(
        dni=patient.dni,
        first_name="Another",
        last_name="Name",
        date_of_birth=patient.date_of_birth,
        gender="unknown",
    )
    found_professional, new_professional = resolve_imported_professional(
        dni=professional.dni,
        first_name="Another",
        last_name="Name",
        license_number="MN 12345",
    )

    assert found_patient.pk == patient.pk and not new_patient
    assert found_professional.pk == professional.pk and not new_professional
    assert not found_patient.is_active and not found_professional.is_active
    assert not found_patient.is_external and not found_professional.is_external
    assert found_patient.first_name == "Alex"
    assert found_professional.first_name == "Patricia"


@pytest.mark.django_db
def test_conflicts_leave_one_identity_and_database_prevents_dni_reuse() -> None:
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
    patient.is_active = False
    patient.save(update_fields=["is_active"])
    professional.is_active = False
    professional.save(update_fields=["is_active"])

    with pytest.raises(ExternalIdentityConflict, match="birth date"):
        resolve_imported_patient(
            dni=patient.dni,
            first_name="Alex",
            last_name="Pérez",
            date_of_birth=date(1991, 1, 15),
            gender="unknown",
        )
    with pytest.raises(ExternalIdentityConflict, match="license number"):
        resolve_imported_professional(
            dni=professional.dni,
            first_name="Patricia",
            last_name="Gómez",
            license_number="MN 99999",
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Patient.all_objects.create(
            dni=patient.dni,
            first_name="Duplicate",
            last_name="Patient",
            date_of_birth=patient.date_of_birth,
            sex="U",
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Professional.objects.create(dni=professional.dni)
    assert Patient.all_objects.filter(dni=patient.dni).count() == 1
    assert Professional.objects.filter(dni=professional.dni).count() == 1
