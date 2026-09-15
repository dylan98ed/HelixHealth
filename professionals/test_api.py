from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from access_control.actors import ActorContext, ActorRole
from access_control.roles import ADMINISTRATIVE_GROUP, MEDICAL_PROFESSIONAL_GROUP
from professionals.models import HospitalService, Professional, Specialty
from professionals.services import (
    deactivate_professional,
    register_professional,
)


@pytest.fixture
def references(db):
    return (
        Specialty.objects.create(code="api-general", name="API General Medicine"),
        HospitalService.objects.create(code="api-ward", name="API Medical Ward"),
    )


@pytest.fixture
def administrative_user(user_factory):
    user = user_factory(username="professional-api-admin")
    user.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))
    return user


@pytest.fixture
def api_client(administrative_user):
    client = APIClient()
    client.force_authenticate(administrative_user)
    return client


@pytest.fixture
def payload(user_factory, references):
    subject = user_factory(username="professional-api-subject")
    specialty, service = references
    return {
        "username": subject.username,
        "dni": "01234567",
        "license_number": "MN 001234",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "date_of_birth": "1990-01-01",
        "specialty_code": specialty.code,
        "hospital_service_code": service.code,
    }


def actor(user) -> ActorContext:
    return ActorContext(user.pk, frozenset({ActorRole.ADMINISTRATIVE}))


def register_for_test(administrative_user, payload, **overrides) -> Professional:
    data = {**payload, **overrides, "date_of_birth": date(1990, 1, 1)}
    return register_professional(actor=actor(administrative_user), **data)


@pytest.mark.django_db
def test_create_and_detail_api_return_the_exact_professional_contract(
    api_client,
    administrative_user,
    payload,
):
    response = api_client.post(
        reverse("professionals:api-create"), payload, format="json"
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert set(response.data) == {
        "id",
        "username",
        "dni",
        "license_number",
        "registration_number",
        "first_name",
        "last_name",
        "date_of_birth",
        "specialty_code",
        "hospital_service_code",
        "registration_completed_at",
        "is_active",
        "is_clinically_eligible",
    }
    assert response.data["license_number"] == "MN 001234"
    assert response.data["registration_number"].startswith("PR-")
    assert response.data["registration_number"] != response.data["license_number"]
    assert response.data["is_clinically_eligible"] is True
    assert Professional.objects.count() == 1
    assert (
        Professional.objects.get()
        .user.groups.filter(name=MEDICAL_PROFESSIONAL_GROUP)
        .exists()
    )

    detail = api_client.get(
        reverse("professionals:api-detail", args=[response.data["id"]])
    )
    assert detail.status_code == status.HTTP_200_OK
    assert detail.data == response.data


@pytest.mark.django_db
def test_detail_api_keeps_nullable_relation_keys_for_an_incomplete_profile(
    api_client,
    user_factory,
):
    incomplete = Professional.objects.create(
        user=user_factory(username="professional-api-null-relations")
    )

    response = api_client.get(reverse("professionals:api-detail", args=[incomplete.pk]))

    assert response.status_code == status.HTTP_200_OK
    assert set(response.data) == {
        "id",
        "username",
        "dni",
        "license_number",
        "registration_number",
        "first_name",
        "last_name",
        "date_of_birth",
        "specialty_code",
        "hospital_service_code",
        "registration_completed_at",
        "is_active",
        "is_clinically_eligible",
    }
    assert response.data["specialty_code"] is None
    assert response.data["hospital_service_code"] is None


@pytest.mark.django_db
def test_create_api_trims_license_before_applying_the_50_character_limit(
    api_client,
    payload,
):
    license_number = "L" * 50

    response = api_client.post(
        reverse("professionals:api-create"),
        {**payload, "license_number": f"  {license_number}  "},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["license_number"] == license_number
    assert Professional.objects.get().license_number == license_number


@pytest.mark.django_db
def test_create_api_returns_200_when_completing_an_existing_profile(
    api_client,
    payload,
):
    subject = get_user_model().objects.get(username=payload["username"])
    incomplete = Professional.objects.create(user=subject, is_active=True)

    response = api_client.post(
        reverse("professionals:api-create"), payload, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == incomplete.pk
    assert Professional.objects.get().pk == incomplete.pk


@pytest.mark.django_db
@pytest.mark.parametrize(
    "license_value",
    [None, "", "   ", 12345, "L" * 51],
)
def test_create_api_rejects_missing_or_invalid_license_without_partial_writes(
    api_client,
    payload,
    license_value,
):
    submitted = dict(payload)
    if license_value is not None:
        submitted["license_number"] = license_value
    else:
        submitted.pop("license_number")

    response = api_client.post(
        reverse("professionals:api-create"), submitted, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "license_number" in response.data
    assert Professional.objects.count() == 0
    subject = Professional._meta.get_field("user").remote_field.model.objects.get(
        username=payload["username"]
    )
    assert not subject.groups.filter(name=MEDICAL_PROFESSIONAL_GROUP).exists()


@pytest.mark.django_db
def test_create_api_rejects_unknown_fields_and_reports_conflicts(
    api_client,
    user_factory,
    payload,
):
    unknown = api_client.post(
        reverse("professionals:api-create"),
        {**payload, "unexpected": "value"},
        format="json",
    )
    assert unknown.status_code == status.HTTP_400_BAD_REQUEST
    assert "unexpected" in unknown.data
    assert Professional.objects.count() == 0

    created = api_client.post(
        reverse("professionals:api-create"), payload, format="json"
    )
    duplicate_account = api_client.post(
        reverse("professionals:api-create"), payload, format="json"
    )
    other = user_factory(username="professional-api-other")
    duplicate_dni = api_client.post(
        reverse("professionals:api-create"),
        {**payload, "username": other.username},
        format="json",
    )

    assert created.status_code == status.HTTP_201_CREATED
    assert duplicate_account.status_code == status.HTTP_409_CONFLICT
    assert duplicate_account.data["existing_professional_id"] == created.data["id"]
    assert "username" in duplicate_account.data
    assert duplicate_dni.status_code == status.HTTP_409_CONFLICT
    assert "dni" in duplicate_dni.data
    assert Professional.objects.count() == 1


@pytest.mark.django_db
def test_search_api_returns_found_empty_and_legacy_null_license(
    api_client,
    administrative_user,
    payload,
):
    professional = register_for_test(administrative_user, payload)
    found = api_client.get(reverse("professionals:api-search"), {"dni": " 01234567 "})

    assert found.status_code == status.HTTP_200_OK
    assert found.data == {
        "results": [
            {
                "id": professional.pk,
                "full_name": "Ada Lovelace",
                "registration_number": professional.registration_number,
                "license_number": "MN 001234",
            }
        ]
    }
    assert api_client.get(
        reverse("professionals:api-search"), {"dni": "7654321"}
    ).data == {"results": []}

    Professional.objects.filter(pk=professional.pk).update(license_number=None)
    detail = api_client.get(reverse("professionals:api-detail", args=[professional.pk]))
    assert detail.status_code == status.HTTP_200_OK
    assert detail.data["license_number"] is None


@pytest.mark.django_db
def test_patch_updates_mutable_fields_and_protects_identity(
    api_client,
    administrative_user,
    payload,
):
    professional = register_for_test(administrative_user, payload)
    url = reverse("professionals:api-detail", args=[professional.pk])
    original_number = professional.registration_number

    changed = api_client.patch(
        url,
        {"license_number": "  MP 0007  ", "last_name": "Byron"},
        format="json",
    )
    assert changed.status_code == status.HTTP_200_OK
    assert changed.data["license_number"] == "MP 0007"
    assert changed.data["last_name"] == "Byron"
    assert changed.data["registration_number"] == original_number

    maximum_license = "X" * 50
    padded = api_client.patch(
        url,
        {"license_number": f"  {maximum_license}  "},
        format="json",
    )
    assert padded.status_code == status.HTTP_200_OK
    assert padded.data["license_number"] == maximum_license

    omitted = api_client.patch(url, {"first_name": "Grace"}, format="json")
    assert omitted.status_code == status.HTTP_200_OK
    assert omitted.data["license_number"] == maximum_license

    for submitted in ({"license_number": None}, {"license_number": " "}):
        rejected = api_client.patch(url, submitted, format="json")
        assert rejected.status_code == status.HTTP_400_BAD_REQUEST
        assert "license_number" in rejected.data

    protected = api_client.patch(
        url,
        {"registration_number": "PR-99999999", "mystery": True},
        format="json",
    )
    assert protected.status_code == status.HTTP_400_BAD_REQUEST
    assert set(protected.data) == {"registration_number", "mystery"}
    professional.refresh_from_db()
    assert professional.registration_number == original_number


@pytest.mark.django_db
def test_patch_supports_inactive_profiles_but_rejects_incomplete_profiles(
    api_client,
    administrative_user,
    user_factory,
    payload,
):
    professional = deactivate_professional(
        actor=actor(administrative_user),
        professional=register_for_test(administrative_user, payload),
        confirmed=True,
    )
    response = api_client.patch(
        reverse("professionals:api-detail", args=[professional.pk]),
        {"last_name": "Inactive-Edited"},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["is_active"] is False

    incomplete = Professional.objects.create(
        user=user_factory(username="professional-api-incomplete")
    )
    rejected = api_client.patch(
        reverse("professionals:api-detail", args=[incomplete.pk]),
        {"last_name": "Nope"},
        format="json",
    )
    assert rejected.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_status_api_requires_confirmation_and_persists_transitions(
    api_client,
    administrative_user,
    payload,
):
    professional = register_for_test(administrative_user, payload)
    deactivate_url = reverse("professionals:api-deactivate", args=[professional.pk])
    reactivate_url = reverse("professionals:api-reactivate", args=[professional.pk])

    unconfirmed = api_client.post(deactivate_url, {"confirm": False}, format="json")
    assert unconfirmed.status_code == status.HTTP_400_BAD_REQUEST
    assert "confirm" in unconfirmed.data
    assert (
        api_client.post(deactivate_url, {"confirm": True}, format="json").data[
            "is_active"
        ]
        is False
    )
    assert (
        api_client.post(reactivate_url, {"confirm": True}, format="json").data[
            "is_active"
        ]
        is True
    )


@pytest.mark.django_db
def test_reactivation_api_reports_incomplete_and_dni_conflict_states(
    api_client,
    administrative_user,
    user_factory,
    payload,
):
    inactive = deactivate_professional(
        actor=actor(administrative_user),
        professional=register_for_test(administrative_user, payload),
        confirmed=True,
    )
    replacement_user = user_factory(username="professional-api-replacement")
    replacement = register_for_test(
        administrative_user,
        payload,
        username=replacement_user.username,
        license_number="MP 9999",
    )

    conflict = api_client.post(
        reverse("professionals:api-reactivate", args=[inactive.pk]),
        {"confirm": True},
        format="json",
    )
    assert conflict.status_code == status.HTTP_409_CONFLICT
    assert conflict.data == {
        "dni": ["An active professional already has this DNI."],
        "existing_professional_id": replacement.pk,
    }
    inactive.refresh_from_db()
    assert inactive.is_active is False

    incomplete = Professional.objects.create(
        user=user_factory(username="professional-api-incomplete-reactivation"),
        is_active=False,
    )
    rejected = api_client.post(
        reverse("professionals:api-reactivate", args=[incomplete.pk]),
        {"confirm": True},
        format="json",
    )
    assert rejected.status_code == status.HTTP_400_BAD_REQUEST
    assert "__all__" in rejected.data
    assert (
        api_client.post(
            reverse("professionals:api-reactivate", args=[999999]),
            {"confirm": True},
            format="json",
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )


@pytest.mark.django_db
def test_api_authorizes_before_lookup_and_unsupported_methods_stay_405(
    api_client,
    user_factory,
):
    missing_url = reverse("professionals:api-detail", args=[999999])
    anonymous = APIClient()
    assert anonymous.get(missing_url).status_code == status.HTTP_403_FORBIDDEN

    wrong_role = user_factory(username="professional-api-wrong-role")
    anonymous.force_authenticate(wrong_role)
    assert anonymous.get(missing_url).status_code == status.HTTP_403_FORBIDDEN
    assert api_client.get(missing_url).status_code == status.HTTP_404_NOT_FOUND
    assert api_client.put(missing_url, {}, format="json").status_code == 405
    assert api_client.delete(missing_url).status_code == 405


@pytest.mark.django_db
def test_professional_api_session_authentication_enforces_csrf(
    administrative_user,
    payload,
):
    client = APIClient(enforce_csrf_checks=True)
    login_page = client.get(reverse("login"))
    token = login_page.cookies["csrftoken"].value
    assert client.login(
        username=administrative_user.username,
        password="foundation-test-password",
    )
    url = reverse("professionals:api-create")
    assert client.post(url, payload, format="json").status_code == 403

    response = client.post(url, payload, format="json", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == status.HTTP_201_CREATED
