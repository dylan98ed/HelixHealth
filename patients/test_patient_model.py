from datetime import date

import pytest
from django.db import IntegrityError, transaction

from patients.models import Patient


def patient_attributes(**overrides):
    attributes = {
        "dni": "12345678",
        "clinical_record_number": "HC-00000001",
        "first_name": "Alex",
        "last_name": "Patient",
        "date_of_birth": date(1990, 1, 1),
        "sex": "unspecified",
        "phone": "+54 11 5555-0101",
        "email": "alex.patient@example.test",
        "address": "123 Test Street",
        "health_insurer": "Test Health",
    }
    attributes.update(overrides)
    return attributes


@pytest.mark.django_db
def test_patient_persists_all_required_profile_fields():
    patient = Patient.objects.create(**patient_attributes())

    patient.refresh_from_db()

    assert isinstance(patient.id, int)
    assert patient.dni == "12345678"
    assert patient.clinical_record_number == "HC-00000001"
    assert patient.first_name == "Alex"
    assert patient.last_name == "Patient"
    assert patient.date_of_birth == date(1990, 1, 1)
    assert patient.sex == "unspecified"
    assert patient.phone == "+54 11 5555-0101"
    assert patient.email == "alex.patient@example.test"
    assert patient.address == "123 Test Street"
    assert patient.health_insurer == "Test Health"
    assert patient.is_active is True


@pytest.mark.django_db
def test_patient_creation_generates_clinical_record_number_when_omitted():
    attributes = patient_attributes(dni="23456789")
    attributes.pop("clinical_record_number")

    patient = Patient.objects.create(**attributes)

    numeric_part = patient.clinical_record_number.removeprefix("HC-")
    assert patient.clinical_record_number.startswith("HC-")
    assert len(numeric_part) >= 8
    assert numeric_part.isascii()
    assert numeric_part.isdigit()


@pytest.mark.django_db
def test_database_rejects_noncanonical_dni():
    with pytest.raises(IntegrityError), transaction.atomic():
        Patient.objects.create(**patient_attributes(dni="1234 678"))


@pytest.mark.django_db
def test_database_rejects_duplicate_active_dni():
    Patient.objects.create(**patient_attributes())

    with pytest.raises(IntegrityError), transaction.atomic():
        Patient.objects.create(
            **patient_attributes(clinical_record_number="HC-00000002")
        )


@pytest.mark.django_db
def test_database_rejects_duplicate_clinical_record_number():
    Patient.objects.create(**patient_attributes())

    with pytest.raises(IntegrityError), transaction.atomic():
        Patient.objects.create(
            **patient_attributes(dni="1234567"),
        )


@pytest.mark.django_db
def test_inactive_patient_dni_can_be_reused_by_an_active_patient():
    Patient.objects.create(**patient_attributes(is_active=False))

    active_patient = Patient.objects.create(
        **patient_attributes(clinical_record_number="HC-00000002")
    )

    assert active_patient.is_active is True
