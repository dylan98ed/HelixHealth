import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone

from access_control.medical_professionals import (
    has_active_medical_professional_context,
    has_completed_active_medical_professional_context,
)
from access_control.roles import MEDICAL_PROFESSIONAL_GROUP
from professionals.models import HospitalService, Professional, Specialty


@pytest.mark.django_db
def test_eligibility_requires_active_user_group_complete_and_active_profile():
    user = get_user_model().objects.create_user(username="medical", password="x")
    assert not has_active_medical_professional_context(user)
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    assert not has_active_medical_professional_context(user)
    assert not has_completed_active_medical_professional_context(user)
    specialty = Specialty.objects.create(code="general", name="General")
    service = HospitalService.objects.create(code="ward", name="Ward")
    profile = Professional.objects.create(
        user=user,
        dni="01234567",
        registration_number="PR-00000001",
        first_name="Ada",
        last_name="Lovelace",
        date_of_birth="1990-01-01",
        specialty=specialty,
        hospital_service=service,
        registration_completed_at=timezone.now(),
    )
    assert has_active_medical_professional_context(user)
    assert has_completed_active_medical_professional_context(user)
    profile.is_active = False
    profile.save(update_fields=["is_active"])
    assert not has_active_medical_professional_context(user)
    assert not has_completed_active_medical_professional_context(user)


@pytest.mark.django_db
def test_active_legacy_profile_keeps_existing_clinical_eligibility():
    user = get_user_model().objects.create_user(username="legacy", password="x")
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    Professional.objects.create(user=user)

    assert has_active_medical_professional_context(user)
    assert not has_completed_active_medical_professional_context(user)


@pytest.mark.django_db
def test_missing_profile_is_provisioned_only_when_requested():
    user = get_user_model().objects.create_user(username="provisioned", password="x")
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))

    assert not has_active_medical_professional_context(user)
    assert has_active_medical_professional_context(user, provision_missing=True)
    assert Professional.objects.filter(user=user, is_active=True).exists()


@pytest.mark.django_db
def test_eligibility_has_no_superuser_or_dual_role_bypass():
    superuser = get_user_model().objects.create_superuser(
        "root", "root@example.test", "x"
    )
    assert not has_active_medical_professional_context(superuser)
    dual = get_user_model().objects.create_user(username="dual", password="x")
    dual.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    assert not has_active_medical_professional_context(dual)
