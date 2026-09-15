from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from access_control.actors import ActorContext, ActorRole
from access_control.roles import ADMINISTRATIVE_GROUP
from professionals.models import HospitalService, Professional, Specialty
from professionals.services import (
    lookup_professional_by_dni,
    professional_index_queryset,
    register_professional,
)


def actor(user) -> ActorContext:
    return ActorContext(user.pk, frozenset({ActorRole.ADMINISTRATIVE}))


@pytest.fixture
def search_setup(user_factory):
    admin = user_factory(username="professional-search-admin")
    admin.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))
    specialty = Specialty.objects.create(code="search-general", name="Search General")
    service = HospitalService.objects.create(code="search-ward", name="Search Ward")
    return admin, specialty, service


def create_completed(
    *,
    admin,
    specialty,
    service,
    username: str,
    dni: str,
    first_name: str = "Ada",
    last_name: str = "Lovelace",
    license_number: str = "MN 001234",
) -> Professional:
    get_user_model().objects.create_user(username=username, password="x")
    return register_professional(
        actor=actor(admin),
        username=username,
        dni=dni,
        license_number=license_number,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date(1990, 1, 1),
        specialty_code=specialty.code,
        hospital_service_code=service.code,
    )


@pytest.mark.django_db
def test_exact_lookup_trims_surrounding_whitespace_and_excludes_other_states(
    search_setup,
    user_factory,
):
    admin, specialty, service = search_setup
    active = create_completed(
        admin=admin,
        specialty=specialty,
        service=service,
        username="search-active",
        dni="01234567",
    )
    inactive = create_completed(
        admin=admin,
        specialty=specialty,
        service=service,
        username="search-inactive",
        dni="7654321",
    )
    inactive.is_active = False
    inactive.save(update_fields=["is_active"])
    Professional.objects.create(
        user=user_factory(username="search-incomplete"),
        dni="23456789",
    )

    assert lookup_professional_by_dni(actor=actor(admin), dni=" 01234567 ") == active
    assert lookup_professional_by_dni(actor=actor(admin), dni="7654321") is None
    assert lookup_professional_by_dni(actor=actor(admin), dni="23456789") is None
    with pytest.raises(ValidationError):
        lookup_professional_by_dni(actor=actor(admin), dni="01.234.567")


@pytest.mark.django_db
def test_index_querysets_separate_states_and_order_stably(search_setup, user_factory):
    admin, specialty, service = search_setup
    second = create_completed(
        admin=admin,
        specialty=specialty,
        service=service,
        username="ordered-second",
        dni="11234567",
        first_name="Zoe",
        last_name="Alpha",
    )
    first = create_completed(
        admin=admin,
        specialty=specialty,
        service=service,
        username="ordered-first",
        dni="21234567",
        first_name="Amy",
        last_name="Alpha",
    )
    inactive = create_completed(
        admin=admin,
        specialty=specialty,
        service=service,
        username="ordered-inactive",
        dni="31234567",
    )
    inactive.is_active = False
    inactive.save(update_fields=["is_active"])
    incomplete = Professional.objects.create(
        user=user_factory(username="ordered-incomplete")
    )

    assert list(professional_index_queryset(actor=actor(admin), status="active")) == [
        first,
        second,
    ]
    assert list(professional_index_queryset(actor=actor(admin), status="inactive")) == [
        inactive
    ]
    assert list(
        professional_index_queryset(actor=actor(admin), status="incomplete")
    ) == [incomplete]


@pytest.mark.django_db
def test_index_and_search_pages_show_both_numbers_and_bound_pages(
    client,
    search_setup,
):
    admin, specialty, service = search_setup
    client.force_login(admin)
    target = None
    for index in range(21):
        target = create_completed(
            admin=admin,
            specialty=specialty,
            service=service,
            username=f"paged-{index:02d}",
            dni=str(40_000_000 + index),
            first_name=f"Name {index:02d}",
            last_name="Paged",
            license_number=f"MN {index:06d}",
        )

    first_page = client.get(reverse("professionals:index"))
    second_page = client.get(reverse("professionals:index"), {"page": 2})
    assert len(first_page.context["page_obj"]) == 20
    assert len(second_page.context["page_obj"]) == 1
    assert b"Next" in first_page.content
    assert b"Previous" in second_page.content
    assert b"License number:" in first_page.content
    assert b"Registration number:" in first_page.content

    assert target is not None
    found = client.get(reverse("professionals:search"), {"dni": target.dni})
    assert target.license_number.encode() in found.content
    assert target.registration_number.encode() in found.content

    Professional.objects.filter(pk=target.pk).update(license_number=None)
    legacy = client.get(reverse("professionals:detail", args=[target.pk]))
    assert b"Not recorded" in legacy.content


def _plan_index_names(plan: dict) -> set[str]:
    names = {plan["Index Name"]} if "Index Name" in plan else set()
    for child in plan.get("Plans", []):
        names.update(_plan_index_names(child))
    return names


@pytest.mark.django_db
def test_exact_active_dni_query_uses_partial_unique_index(search_setup):
    admin, specialty, service = search_setup
    user_model = get_user_model()
    users = [user_model(username=f"search-perf-{index:05d}") for index in range(10_000)]
    user_model.objects.bulk_create(users, batch_size=1_000)
    now = timezone.now()
    profiles = [
        Professional(
            user=user,
            dni=str(50_000_000 + index),
            license_number=f"MN {index:06d}",
            registration_number=f"PR-PERF-{index:08d}",
            first_name="Performance",
            last_name=f"Professional {index:05d}",
            date_of_birth=date(1990, 1, 1),
            specialty=specialty,
            hospital_service=service,
            registration_completed_at=now,
        )
        for index, user in enumerate(users)
    ]
    Professional.objects.bulk_create(profiles, batch_size=1_000)
    target_dni = profiles[-1].dni
    queryset = Professional.objects.filter(
        dni=target_dni,
        is_active=True,
        registration_completed_at__isnull=False,
    )
    sql, params = queryset.query.sql_with_params()

    with connection.cursor() as cursor:
        cursor.execute("ANALYZE professionals_professional")
        cursor.execute(f"EXPLAIN (FORMAT JSON) {sql}", params)
        explained = cursor.fetchone()[0]

    assert "unique_active_professional_dni" in _plan_index_names(explained[0]["Plan"])
    assert (
        lookup_professional_by_dni(actor=actor(admin), dni=target_dni).dni == target_dni
    )
