"""Real HTTP contract tests for catalog endpoints."""

import json
from datetime import date

import pytest
from django.contrib import admin
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from access_control.roles import ADMINISTRATIVE_GROUP, MEDICAL_PROFESSIONAL_GROUP
from catalogs.models import MedicationEntry, TerminologyEntry
from professionals.admin import SpecialtyAdmin
from professionals.models import HospitalService, Professional, Specialty


def terminology_payload(code="100"):
    return {
        "system": "https://snomed.example.test",
        "version": "2026-09",
        "code": code,
        "display": f"Finding {code}",
        "source_label": "Manual catalog",
    }


@pytest.fixture
def administrative_user(user_factory):
    user = user_factory(username="catalog-api-administrator", is_staff=False)
    user.groups.add(Group.objects.get_or_create(name=ADMINISTRATIVE_GROUP)[0])
    return user


@pytest.fixture
def administrator_client(administrative_user):
    client = APIClient()
    client.force_authenticate(administrative_user)
    return client


@pytest.fixture
def active_medical_user(user_factory):
    user = user_factory(username="catalog-api-medical")
    user.groups.add(Group.objects.get_or_create(name=MEDICAL_PROFESSIONAL_GROUP)[0])
    specialty = Specialty.objects.create(code="catalog-api-medical", name="Catalog API")
    service = HospitalService.objects.create(
        code="catalog-api-ward", name="Catalog API ward"
    )
    Professional.objects.create(
        user=user,
        dni="34567890",
        registration_number="PR-CATALOG-API-0001",
        license_number="MN 123",
        first_name="Active",
        last_name="Reader",
        date_of_birth=date(1990, 1, 1),
        specialty=specialty,
        hospital_service=service,
        registration_completed_at=timezone.now(),
    )
    return user


@pytest.mark.django_db
def test_specialty_api_enforces_roles_immutable_codes_and_protected_deletion(
    administrator_client,
    administrative_user,
    user_factory,
):
    collection = reverse("catalogs:api-specialties")
    created = administrator_client.post(
        collection,
        {"code": "catalog-api-cardio", "name": "Catalog API Cardiology"},
        format="json",
    )
    assert created.status_code == status.HTTP_201_CREATED, created.data
    detail = reverse("catalogs:api-specialty-detail", args=[created.data["id"]])

    immutable = administrator_client.patch(detail, {"code": "changed"}, format="json")
    assert immutable.status_code == status.HTTP_400_BAD_REQUEST
    edited = administrator_client.patch(
        detail, {"name": "Clinical Cardiology", "is_active": False}, format="json"
    )
    assert edited.status_code == status.HTTP_200_OK
    assert edited.data["code"] == "catalog-api-cardio"
    assert edited.data["is_active"] is False

    subject = user_factory(username="catalog-api-assigned")
    service = HospitalService.objects.create(
        code="catalog-api-service", name="API Service"
    )
    Professional.objects.create(
        user=subject,
        dni="45678901",
        registration_number="PR-CATALOG-API-0002",
        license_number="MN 124",
        first_name="Assigned",
        last_name="Reader",
        date_of_birth=date(1990, 1, 1),
        specialty_id=created.data["id"],
        hospital_service=service,
        registration_completed_at=timezone.now(),
    )
    assert administrator_client.delete(detail).status_code == status.HTTP_409_CONFLICT

    anonymous = APIClient()
    assert (
        anonymous.get(
            reverse("catalogs:api-specialty-detail", args=[99999])
        ).status_code
        == 403
    )
    wrong_role = user_factory(username="catalog-api-wrong-role")
    anonymous.force_authenticate(wrong_role)
    assert (
        anonymous.get(
            reverse("catalogs:api-specialty-detail", args=[99999])
        ).status_code
        == 403
    )
    assert (
        administrator_client.get(
            reverse("catalogs:api-specialty-detail", args=[99999])
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_catalog_http_read_search_and_twenty_row_pagination(
    administrator_client, active_medical_user
):
    for index in range(21):
        TerminologyEntry.objects.create(
            created_by=active_medical_user,
            **terminology_payload(f"TERM-{index:02d}"),
        )
    collection = reverse("catalogs:api-terminology")
    first = administrator_client.get(collection)
    assert first.status_code == status.HTTP_200_OK
    assert set(first.data) == {"count", "next", "previous", "results"}
    assert first.data["count"] == 21
    assert len(first.data["results"]) == 20
    assert first.data["next"] == 2
    second = administrator_client.get(collection, {"page": 2})
    assert len(second.data["results"]) == 1
    assert second.data["previous"] == 1
    found = administrator_client.get(collection, {"search": "TERM-20"})
    assert [entry["code"] for entry in found.data["results"]] == ["TERM-20"]

    medical = APIClient()
    medical.force_authenticate(active_medical_user)
    assert medical.get(collection).status_code == status.HTTP_200_OK
    assert (
        medical.post(
            collection, terminology_payload("NO-WRITE"), format="json"
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_append_only_http_contract_import_limits_and_admin_surface(
    administrator_client, administrative_user
):
    terminology_collection = reverse("catalogs:api-terminology")
    created = administrator_client.post(
        terminology_collection, terminology_payload(), format="json"
    )
    assert created.status_code == status.HTTP_201_CREATED
    detail = reverse("catalogs:api-terminology-detail", args=[created.data["id"]])
    for method in (
        administrator_client.patch,
        administrator_client.put,
        administrator_client.delete,
    ):
        response = (
            method(detail, {}, format="json")
            if method != administrator_client.delete
            else method(detail)
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert TerminologyEntry.objects.filter(pk=created.data["id"]).count() == 1

    import_url = reverse("catalogs:api-terminology-import")
    document = {
        "source_label": "Imported source",
        "entries": [
            {
                "system": "https://snomed.example.test",
                "version": "2026-10",
                "code": "IMP-1",
                "display": "Imported finding",
            }
        ],
    }
    imported = administrator_client.post(
        import_url, json.dumps(document), content_type="application/json"
    )
    assert imported.status_code == status.HTTP_200_OK
    assert imported.data == {"created": 1, "unchanged": 0}
    repeat = administrator_client.post(
        import_url, json.dumps(document), content_type="application/json"
    )
    assert repeat.data == {"created": 0, "unchanged": 1}
    assert (
        administrator_client.post(import_url, document, format="multipart").status_code
        == 415
    )
    oversized = b" " * (2 * 1024 * 1024 + 1)
    assert (
        administrator_client.post(
            import_url, oversized, content_type="application/json"
        ).status_code
        == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    )

    request = type("Request", (), {"user": administrative_user})()
    specialty_admin = SpecialtyAdmin(Specialty, admin.site)
    assert not specialty_admin.has_add_permission(request)
    assert not specialty_admin.has_change_permission(request)
    assert not specialty_admin.has_delete_permission(request)
    assert not admin.site.is_registered(TerminologyEntry)
    assert not admin.site.is_registered(MedicationEntry)


@pytest.mark.django_db
def test_catalog_api_session_authentication_enforces_csrf(administrative_user):
    client = APIClient(enforce_csrf_checks=True)
    login_page = client.get(reverse("login"))
    token = login_page.cookies["csrftoken"].value
    assert client.login(
        username=administrative_user.username, password="foundation-test-password"
    )
    url = reverse("catalogs:api-specialties")
    payload = {"code": "csrf-specialty", "name": "CSRF specialty"}
    assert (
        client.post(url, payload, format="json").status_code
        == status.HTTP_403_FORBIDDEN
    )
    response = client.post(url, payload, format="json", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == status.HTTP_201_CREATED
