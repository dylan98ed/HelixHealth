from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from access_control.acceptance_personas import (
    ACCEPTANCE_PASSWORD_ENV,
    ACTIVE_PATIENT_DNI,
    ADMINISTRATOR_USERNAME,
    ADMISSION_REASON,
    BROWSER_CREATED_USERNAME,
    DJANGO_ADMIN_USERNAME,
    INACTIVE_PATIENT_DNI,
    MEDICAL_ACTIVE_USERNAME,
    MEDICAL_INACTIVE_USERNAME,
    MEDICAL_LEGACY_STAFF_USERNAME,
    MEDICAL_UNPROVISIONED_USERNAME,
    REGISTERED_PATIENT_DNI,
)
from access_control.roles import ADMINISTRATIVE_GROUP, MEDICAL_PROFESSIONAL_GROUP
from clinical_records.models import Admission
from patients.models import Patient
from professionals.models import Professional

ACCEPTANCE_PASSWORD = "Acceptance-test-password-2026!"


@pytest.mark.django_db
def test_seed_acceptance_creates_deterministic_personas(monkeypatch):
    monkeypatch.setenv(ACCEPTANCE_PASSWORD_ENV, ACCEPTANCE_PASSWORD)

    call_command("seed_acceptance")
    call_command("seed_acceptance")

    user_model = get_user_model()
    django_admin = user_model.objects.get(username=DJANGO_ADMIN_USERNAME)
    assert django_admin.is_staff
    assert django_admin.is_superuser
    assert django_admin.check_password(ACCEPTANCE_PASSWORD)

    administrator = user_model.objects.get(username=ADMINISTRATOR_USERNAME)
    assert set(administrator.groups.values_list("name", flat=True)) == {
        ADMINISTRATIVE_GROUP
    }

    for username in (
        MEDICAL_UNPROVISIONED_USERNAME,
        MEDICAL_LEGACY_STAFF_USERNAME,
        MEDICAL_ACTIVE_USERNAME,
        MEDICAL_INACTIVE_USERNAME,
    ):
        user = user_model.objects.get(username=username)
        assert set(user.groups.values_list("name", flat=True)) == {
            MEDICAL_PROFESSIONAL_GROUP
        }
        assert user.check_password(ACCEPTANCE_PASSWORD)

    assert not Professional.objects.filter(
        user__username=MEDICAL_UNPROVISIONED_USERNAME
    ).exists()
    assert not Professional.objects.filter(
        user__username=MEDICAL_LEGACY_STAFF_USERNAME
    ).exists()
    assert Professional.objects.get(user__username=MEDICAL_ACTIVE_USERNAME).is_active
    assert not Professional.objects.get(
        user__username=MEDICAL_INACTIVE_USERNAME
    ).is_active
    assert Patient.objects.get(dni=ACTIVE_PATIENT_DNI).is_active
    assert not Patient.all_objects.get(dni=INACTIVE_PATIENT_DNI).is_active


@override_settings(ENVIRONMENT="production")
def test_seed_acceptance_refuses_non_test_or_development_environment(monkeypatch):
    monkeypatch.setenv(ACCEPTANCE_PASSWORD_ENV, ACCEPTANCE_PASSWORD)

    with pytest.raises(CommandError, match="only in development or test"):
        call_command("seed_acceptance")


@pytest.mark.django_db
def test_verify_acceptance_checks_persisted_browser_outcomes(monkeypatch):
    monkeypatch.setenv(ACCEPTANCE_PASSWORD_ENV, ACCEPTANCE_PASSWORD)
    call_command("seed_acceptance")
    user_model = get_user_model()

    for username in (
        MEDICAL_UNPROVISIONED_USERNAME,
        MEDICAL_LEGACY_STAFF_USERNAME,
    ):
        Professional.objects.create(user=user_model.objects.get(username=username))

    registered_patient = Patient.objects.create(
        dni=REGISTERED_PATIENT_DNI,
        clinical_record_number="HC-ACCEPTANCE-REGISTERED",
        first_name="Compose",
        last_name="Registered",
        date_of_birth="1990-01-01",
        sex="unspecified",
        phone="+54 11 5555-0199",
        email="compose.patient@example.test",
        address="Compose Test Street 123",
        health_insurer="Compose Health",
    )
    user_model.objects.create_user(username=BROWSER_CREATED_USERNAME)
    Admission.objects.create(
        patient=registered_patient,
        professional=Professional.objects.get(user__username=MEDICAL_ACTIVE_USERNAME),
        consultation_reason=ADMISSION_REASON,
        systolic_blood_pressure=120,
        diastolic_blood_pressure=80,
        heart_rate=72,
        temperature=Decimal("36.7"),
    )

    call_command("verify_acceptance")
