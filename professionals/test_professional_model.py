from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from professionals.models import HospitalService, Professional, Specialty


def create_user(username: str):
    return get_user_model().objects.create_user(username=username, password="test-pass")


@pytest.fixture
def references(db):
    return (
        Specialty.objects.create(code="general", name="General"),
        HospitalService.objects.create(code="ward", name="Ward"),
    )


@pytest.mark.django_db
def test_incomplete_legacy_profile_is_permitted_and_identified_as_incomplete():
    professional = Professional.objects.create(user=create_user("legacy"))

    assert professional.is_registration_complete is False
    assert professional.registration_status == "incomplete"
    assert professional.display_name == "legacy"


@pytest.mark.django_db
def test_completeness_is_independent_of_active_flag(references):
    specialty, hospital_service = references
    incomplete_inactive = Professional.objects.create(
        user=create_user("legacy-inactive"), is_active=False
    )
    complete_inactive = Professional.objects.create(
        user=create_user("complete-inactive"),
        is_active=False,
        dni="01234567",
        registration_number="PR-00000009",
        first_name="Grace",
        last_name="Hopper",
        date_of_birth=date(1906, 12, 9),
        specialty=specialty,
        hospital_service=hospital_service,
        registration_completed_at=timezone.now(),
    )

    assert incomplete_inactive.is_registration_complete is False
    assert incomplete_inactive.registration_status == "incomplete"
    assert complete_inactive.is_registration_complete is True
    assert complete_inactive.registration_status == "inactive"


@pytest.mark.django_db
def test_complete_profile_requires_all_registration_fields(references):
    specialty, hospital_service = references
    professional = Professional(
        user=create_user("complete"),
        dni="01234567",
        registration_number="PR-00000001",
        first_name="Ada",
        last_name="Lovelace",
        date_of_birth=date(1815, 12, 10),
        specialty=specialty,
        hospital_service=hospital_service,
        registration_completed_at=timezone.now(),
    )
    professional.full_clean()
    professional.save()

    assert professional.is_registration_complete is True
    assert professional.registration_status == "active"
    assert professional.display_name == "Lovelace, Ada"


@pytest.mark.django_db
def test_database_rejects_completed_profile_missing_required_values():
    with pytest.raises(IntegrityError), transaction.atomic():
        Professional.objects.create(
            user=create_user("bad-complete"),
            registration_completed_at=timezone.now(),
        )


@pytest.mark.django_db
def test_active_only_dni_uniqueness_allows_reuse_after_deactivation():
    Professional.objects.create(
        user=create_user("inactive"), dni="12345678", is_active=False
    )
    active = Professional.objects.create(user=create_user("active"), dni="12345678")

    assert active.dni == "12345678"
    with pytest.raises(IntegrityError), transaction.atomic():
        Professional.objects.create(user=create_user("duplicate"), dni="12345678")


@pytest.mark.django_db
def test_user_and_reference_links_are_protected(references):
    specialty, hospital_service = references
    professional = Professional.objects.create(
        user=create_user("linked"),
        specialty=specialty,
        hospital_service=hospital_service,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        professional.user.delete()
    with pytest.raises(IntegrityError), transaction.atomic():
        specialty.delete()
    with pytest.raises(IntegrityError), transaction.atomic():
        hospital_service.delete()
