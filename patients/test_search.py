import math
from datetime import date
from time import perf_counter

import pytest
from django.contrib.auth.models import Group
from django.db import connection
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from access_control.actors import ActorContext, ActorRole
from access_control.roles import ADMINISTRATIVE_GROUP
from patients.models import Patient
from patients.services import lookup_active_patient_by_dni

MVP_PATIENT_COUNT = 10_000


def administrative_actor() -> ActorContext:
    return ActorContext(user_id=1, roles=frozenset({ActorRole.ADMINISTRATIVE}))


def administrative_api_client(user_factory) -> APIClient:
    user = user_factory(username="patient-search-api-admin")
    user.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))
    client = APIClient()
    client.force_authenticate(user)
    return client


def create_patient(*, dni: str = "12345678", is_active: bool = True) -> Patient:
    return Patient.all_objects.create(
        dni=dni,
        first_name="Alex",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        sex="unspecified",
        phone="+54 11 5555-0101",
        email="alex.patient@example.test",
        address="123 Test Street",
        health_insurer="Test Health",
        is_active=is_active,
    )


def seed_mvp_patients() -> str:
    patients = []
    for offset in range(MVP_PATIENT_COUNT):
        value = 10_000_000 + offset
        patients.append(
            Patient(
                dni=str(value),
                clinical_record_number=f"HC-PERF-{value}",
                first_name="Performance",
                last_name=f"Patient {offset}",
                date_of_birth=date(1990, 1, 1),
                sex="unspecified",
                phone="+54 11 5555-0101",
                email=f"patient-{offset}@example.test",
                address="MVP dataset",
                health_insurer="Test Health",
            )
        )
    Patient.all_objects.bulk_create(patients, batch_size=1_000)
    return str(10_000_000 + MVP_PATIENT_COUNT - 1)


def plan_index_names(plan: dict) -> set[str]:
    names = {plan["Index Name"]} if "Index Name" in plan else set()
    for child in plan.get("Plans", []):
        names.update(plan_index_names(child))
    return names


@pytest.mark.django_db
def test_exact_active_dni_query_uses_unique_index():
    target_dni = seed_mvp_patients()
    queryset = Patient.objects.filter(dni=target_dni)
    sql, params = queryset.query.sql_with_params()

    with connection.cursor() as cursor:
        cursor.execute("ANALYZE patients_patient")
        cursor.execute(f"EXPLAIN (FORMAT JSON) {sql}", params)
        explained = cursor.fetchone()[0]

    plan = explained[0]["Plan"]
    assert "unique_active_patient_dni" in plan_index_names(plan)


@pytest.mark.django_db
def test_lookup_service_returns_exact_active_match_and_excludes_inactive():
    active = create_patient()
    create_patient(dni="7654321", is_active=False)

    assert (
        lookup_active_patient_by_dni(actor=administrative_actor(), dni=active.dni)
        == active
    )
    assert (
        lookup_active_patient_by_dni(actor=administrative_actor(), dni="7654321")
        is None
    )


@pytest.mark.django_db
def test_search_api_returns_found_and_empty_result_shapes(user_factory):
    client = administrative_api_client(user_factory)
    patient = create_patient()
    url = reverse("patients:api-search")

    found = client.get(url, {"dni": patient.dni})
    missing = client.get(url, {"dni": "7654321"})

    assert found.status_code == status.HTTP_200_OK
    assert found.data == {
        "results": [
            {
                "id": patient.pk,
                "full_name": "Alex Patient",
                "clinical_record_number": patient.clinical_record_number,
            }
        ]
    }
    assert missing.status_code == status.HTTP_200_OK
    assert missing.data == {"results": []}


@pytest.mark.django_db
def test_search_api_rejects_noncanonical_dni_and_non_administrative_actor(
    user_factory,
):
    url = reverse("patients:api-search")
    client = administrative_api_client(user_factory)

    invalid = client.get(url, {"dni": "12.345.678"})
    anonymous = APIClient().get(url, {"dni": "12345678"})

    assert invalid.status_code == status.HTTP_400_BAD_REQUEST
    assert "dni" in invalid.data
    assert anonymous.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_htmx_search_result_links_to_patient_detail(client, user_factory):
    user = user_factory(username="patient-search-template-admin")
    user.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))
    client.force_login(user)
    patient = create_patient()

    response = client.get(
        reverse("patients:search-results"),
        {"dni": patient.dni},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Alex Patient" in response.content
    assert patient.clinical_record_number.encode() in response.content
    assert reverse("patients:detail", args=[patient.pk]).encode() in response.content


@pytest.mark.django_db
def test_unmatched_dni_registration_action_prefills_without_creating(
    client,
    user_factory,
):
    user = user_factory(username="patient-search-prefill-admin")
    user.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))
    client.force_login(user)
    unmatched_dni = "7654321"

    search_response = client.get(
        reverse("patients:search-results"),
        {"dni": unmatched_dni},
        HTTP_HX_REQUEST="true",
    )
    registration_response = client.get(
        reverse("patients:register"),
        {"dni": unmatched_dni},
    )

    expected_url = f"{reverse('patients:register')}?dni={unmatched_dni}"
    assert search_response.status_code == 200
    assert expected_url.encode() in search_response.content
    assert b"No patient matches" in search_response.content
    assert registration_response.status_code == 200
    assert f'value="{unmatched_dni}"'.encode() in registration_response.content
    assert Patient.all_objects.count() == 0


@pytest.mark.django_db
def test_patient_search_p95_is_below_two_seconds_for_mvp_dataset(user_factory):
    target_dni = seed_mvp_patients()
    client = administrative_api_client(user_factory)
    url = reverse("patients:api-search")

    response_times = []
    for _ in range(40):
        started = perf_counter()
        response = client.get(url, {"dni": target_dni})
        response_times.append(perf_counter() - started)
        assert response.status_code == status.HTTP_200_OK

    ordered = sorted(response_times)
    p95_seconds = ordered[math.ceil(0.95 * len(ordered)) - 1]
    print(f"HU-02 lookup p95: {p95_seconds:.6f}s ({MVP_PATIENT_COUNT} patients)")
    assert p95_seconds < 2.0
