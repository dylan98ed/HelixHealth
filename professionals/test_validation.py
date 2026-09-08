from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError

from professionals.models import HospitalService, Specialty
from professionals.validators import (
    canonicalize_professional_dni,
    normalize_license_number,
    normalize_required_name,
    validate_active_reference,
    validate_professional_date_of_birth,
)


@pytest.mark.parametrize("value", [" 01234567 ", "0123456"])
def test_professional_dni_trims_surrounding_whitespace_and_preserves_zeroes(value):
    assert canonicalize_professional_dni(value) == value.strip()


@pytest.mark.parametrize(
    "value",
    ["1234 567", "12.345.678", "１２３４５６７", "123456", "123456789"],
)
def test_professional_dni_rejects_noncanonical_values(value):
    with pytest.raises(ValidationError):
        canonicalize_professional_dni(value)


def test_professional_names_are_trimmed_nonblank_and_bounded():
    assert normalize_required_name("  Ada  ") == "Ada"
    with pytest.raises(ValidationError):
        normalize_required_name(" \t ")
    with pytest.raises(ValidationError):
        normalize_required_name("a" * 151)


def test_license_numbers_trim_only_outer_whitespace_and_preserve_text():
    assert normalize_license_number("  MN 001234  ") == "MN 001234"
    for value in (None, " \t ", "x" * 51):
        with pytest.raises(ValidationError):
            normalize_license_number(value)


def test_professional_birth_date_cannot_be_future():
    validate_professional_date_of_birth(date.today())
    with pytest.raises(ValidationError):
        validate_professional_date_of_birth(date.today() + timedelta(days=1))


@pytest.mark.django_db
def test_only_active_reference_inputs_are_accepted():
    specialty = Specialty.objects.create(code="active", name="Active")
    retired_service = HospitalService.objects.create(
        code="retired", name="Retired", is_active=False
    )

    validate_active_reference(specialty, field_name="specialty")
    with pytest.raises(ValidationError):
        validate_active_reference(retired_service, field_name="hospital service")
