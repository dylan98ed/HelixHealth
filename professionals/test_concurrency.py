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
from professionals.services import ProfessionalConflictError, register_professional


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
def test_inactive_dni_cannot_be_claimed_by_another_profile():
    from django.db import IntegrityError, transaction

    first = get_user_model().objects.create_user(username="inactive", password="x")
    second = get_user_model().objects.create_user(username="other", password="x")
    Professional.objects.create(user=first, dni="01234567", is_active=False)
    with pytest.raises(IntegrityError), transaction.atomic():
        Professional.objects.create(user=second, dni="01234567", is_active=True)
    assert Professional.objects.filter(dni="01234567").count() == 1
