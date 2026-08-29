from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError

from patients.models import Patient


def valid_patient_data(**overrides):
    data = {
        "dni": "12345678",
        "first_name": "Alex",
        "last_name": "Patient",
        "date_of_birth": date(1990, 1, 1),
        "sex": "unspecified",
        "phone": "+54 11 5555-0101",
        "email": "alex.patient@example.test",
        "address": "123 Test Street",
        "health_insurer": "Test Health",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("dni", "phone"),
    [
        ("1234567", "55550101"),
        ("12345678", "+54 (11) 5555-0101"),
    ],
)
def test_patient_validation_accepts_supported_field_formats(dni, phone):
    patient = Patient(**valid_patient_data(dni=dni, phone=phone))

    patient.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("dni", "1234 678"),
        ("dni", "123456"),
        ("first_name", ""),
        ("last_name", ""),
        ("date_of_birth", None),
        ("date_of_birth", date.today() + timedelta(days=1)),
        ("sex", ""),
        ("phone", "phone-number"),
        ("phone", "12345"),
        ("email", "not-an-email"),
        ("address", ""),
        ("health_insurer", ""),
        ("first_name", "   "),
        ("last_name", "   "),
        ("sex", "   "),
        ("address", "   "),
        ("health_insurer", "   "),
    ],
)
def test_patient_validation_rejects_each_invalid_field_class(
    field_name,
    invalid_value,
):
    patient = Patient(**valid_patient_data(**{field_name: invalid_value}))

    with pytest.raises(ValidationError) as error:
        patient.full_clean()

    assert field_name in error.value.message_dict
