from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import close_old_connections, connection

from access_control.actors import ActorContext, ActorRole
from access_control.roles import ADMINISTRATIVE_GROUP, MEDICAL_PROFESSIONAL_GROUP
from professionals.models import HospitalService, Professional, Specialty
from professionals.services import (
    ProfessionalConflictError,
    reactivate_professional,
    register_professional,
)


@pytest.mark.django_db(transaction=True)
def test_competing_registration_for_same_dni_creates_one_active_identity():
    Group.objects.get_or_create(name=MEDICAL_PROFESSIONAL_GROUP)
    admin = get_user_model().objects.create_user(username="admin", password="x")
    admin.groups.add(Group.objects.get_or_create(name=ADMINISTRATIVE_GROUP)[0])
    for username in ("one", "two"):
        get_user_model().objects.create_user(username=username, password="x")
    Specialty.objects.create(code="general", name="General")
    HospitalService.objects.create(code="ward", name="Ward")
    barrier = Barrier(2)
    actor = ActorContext(admin.pk, frozenset({ActorRole.ADMINISTRATIVE}))

    def attempt(username: str) -> str:
        close_old_connections()
        try:
            barrier.wait()
            try:
                register_professional(
                    actor=actor,
                    username=username,
                    dni="01234567",
                    license_number="MN 001234",
                    first_name="Ada",
                    last_name="Lovelace",
                    date_of_birth=date(1990, 1, 1),
                    specialty_code="general",
                    hospital_service_code="ward",
                )
                return "created"
            except ProfessionalConflictError:
                return "conflict"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, ("one", "two")))

    assert sorted(outcomes) == ["conflict", "created"]
    assert Professional.objects.filter(dni="01234567", is_active=True).count() == 1


@pytest.mark.django_db(transaction=True)
def test_competing_reactivation_translates_active_dni_constraint(monkeypatch):
    admin = get_user_model().objects.create_user(username="admin", password="x")
    admin.groups.add(Group.objects.get_or_create(name=ADMINISTRATIVE_GROUP)[0])
    subjects = [
        get_user_model().objects.create_user(username=username, password="x")
        for username in ("one", "two")
    ]
    specialty = Specialty.objects.create(code="general", name="General")
    service = HospitalService.objects.create(code="ward", name="Ward")
    profiles = [
        Professional.objects.create(
            user=subject,
            is_active=False,
            dni="01234567",
            registration_number=f"PR-0000000{index}",
            first_name="Ada",
            last_name="Lovelace",
            date_of_birth=date(1990, 1, 1),
            specialty=specialty,
            hospital_service=service,
            registration_completed_at="2026-01-01T00:00:00Z",
        )
        for index, subject in enumerate(subjects, start=1)
    ]
    barrier = Barrier(2)
    original_save = Professional.save

    def synchronize_activation(self, *args, **kwargs):
        if self.pk in {profile.pk for profile in profiles} and self.is_active:
            barrier.wait(timeout=10)
        return original_save(self, *args, **kwargs)

    monkeypatch.setattr(Professional, "save", synchronize_activation)
    actor = ActorContext(admin.pk, frozenset({ActorRole.ADMINISTRATIVE}))

    def attempt(profile_id: int) -> str:
        close_old_connections()
        try:
            try:
                reactivate_professional(
                    actor=actor,
                    professional=Professional.objects.get(pk=profile_id),
                    confirmed=True,
                )
                return "reactivated"
            except ProfessionalConflictError:
                return "conflict"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, [profile.pk for profile in profiles]))

    assert sorted(outcomes) == ["conflict", "reactivated"]
    assert Professional.objects.filter(dni="01234567", is_active=True).count() == 1
