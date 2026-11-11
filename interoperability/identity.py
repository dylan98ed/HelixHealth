"""Resolve identities from validated FHIR data without creating login access."""

from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from patients.models import Patient
from patients.validators import validate_patient_dni
from professionals.models import Professional
from professionals.validators import (
    canonicalize_professional_dni,
    normalize_license_number,
    normalize_required_name,
)


class ExternalIdentityConflict(ValueError):
    """An imported identity contradicts a person already stored locally."""


@transaction.atomic
def resolve_imported_patient(
    *, dni: str, first_name: str, last_name: str, date_of_birth: date, gender: str
) -> tuple[Patient, bool]:
    """Reuse an active or inactive DNI, or create an incomplete external patient."""
    validate_patient_dni(dni)
    if not first_name.strip() or not last_name.strip():
        raise ValidationError("Patient first and last names are required.")
    sex = {"male": "M", "female": "F", "other": "O", "unknown": "U"}.get(gender)
    if sex is None:
        raise ValidationError("Unsupported Patient.gender value.")
    patient, created = Patient.all_objects.get_or_create(
        dni=dni,
        defaults={
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "date_of_birth": date_of_birth,
            "sex": sex,
            "phone": "",
            "email": "",
            "address": "",
            "health_insurer": "",
            "is_external": True,
        },
    )
    if created:
        patient.full_clean()
    elif patient.date_of_birth != date_of_birth:
        raise ExternalIdentityConflict("Patient DNI matches but birth date differs.")
    return patient, created


@transaction.atomic
def resolve_imported_professional(
    *, dni: str, first_name: str, last_name: str, license_number: str
) -> tuple[Professional, bool]:
    """Resolve Practitioner by DNI; a new identity has no account or role."""
    canonical_dni = canonicalize_professional_dni(dni)
    first_name = normalize_required_name(first_name)
    last_name = normalize_required_name(last_name)
    license_number = normalize_license_number(license_number)
    if not license_number:
        raise ValidationError("Practitioner qualification identifier is required.")
    professional, created = Professional.objects.get_or_create(
        dni=canonical_dni,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "license_number": license_number,
            "is_external": True,
            "user": None,
        },
    )
    if created:
        professional.full_clean()
    elif professional.license_number and professional.license_number != license_number:
        raise ExternalIdentityConflict(
            "Practitioner DNI matches but license number differs."
        )
    return professional, created
