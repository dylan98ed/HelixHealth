import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from access_control.roles import ADMINISTRATIVE_GROUP, MEDICAL_PROFESSIONAL_GROUP
from professionals.models import HospitalService, Professional, Specialty


@pytest.fixture
def registration_setup(client, user_factory):
    administrator = user_factory(username="professional-admin", is_staff=False)
    administrator.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))
    subject = user_factory(username="professional-subject", is_staff=False)
    specialty = Specialty.objects.create(code="test-specialty", name="Test specialty")
    service = HospitalService.objects.create(code="test-service", name="Test service")
    client.force_login(administrator)
    return subject, {
        "username": subject.username,
        "dni": "01234567",
        "license_number": "MN 001234",
        "first_name": " Ada ",
        "last_name": " Lovelace ",
        "date_of_birth": "1990-01-01",
        "specialty_code": specialty.code,
        "hospital_service_code": service.code,
    }


@pytest.mark.django_db
def test_admin_navigation_and_registration_persist_profile_and_role(
    client, registration_setup
):
    subject, payload = registration_setup
    assert b"/professionals/" in client.get(reverse("patients:search")).content
    response = client.post(reverse("professionals:register"), payload)
    profile = Professional.objects.get(user=subject)
    assert response.status_code == 302
    assert response.url == reverse("professionals:detail", args=[profile.pk])
    assert profile.first_name == "Ada" and profile.dni == "01234567"
    assert profile.is_registration_complete
    assert subject.groups.filter(name=MEDICAL_PROFESSIONAL_GROUP).exists()
    subject.refresh_from_db()
    assert not subject.is_staff
    assert profile.registration_number.encode() in client.get(response.url).content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field,value",
    [
        ("username", "unknown"),
        ("dni", "12.345.678"),
        ("first_name", " "),
        ("date_of_birth", "2999-01-01"),
        ("specialty_code", "unknown"),
        ("hospital_service_code", "unknown"),
    ],
)
def test_invalid_htmx_registration_keeps_bound_fields_without_partial_writes(
    client,
    registration_setup,
    field,
    value,
):
    subject, payload = registration_setup
    payload[field] = value
    response = client.post(
        reverse("professionals:register"), payload, HTTP_HX_REQUEST="true"
    )
    assert response.status_code == 422
    assert f'data-field-error="{field}"'.encode() in response.content
    assert not Professional.objects.filter(user=subject).exists()
    assert not subject.groups.filter(name=MEDICAL_PROFESSIONAL_GROUP).exists()


@pytest.mark.django_db
def test_disabled_account_and_retired_reference_rejected(client, registration_setup):
    subject, payload = registration_setup
    subject.is_active = False
    subject.save(update_fields=["is_active"])
    response = client.post(
        reverse("professionals:register"), payload, HTTP_HX_REQUEST="true"
    )
    assert b'data-field-error="username"' in response.content
    subject.is_active = True
    subject.save(update_fields=["is_active"])
    Specialty.objects.filter(code=payload["specialty_code"]).update(is_active=False)
    response = client.post(
        reverse("professionals:register"), payload, HTTP_HX_REQUEST="true"
    )
    assert b'data-field-error="specialty_code"' in response.content
    assert not Professional.objects.filter(user=subject).exists()


@pytest.mark.django_db
def test_conflicts_show_field_and_existing_record(
    client, registration_setup, user_factory
):
    subject, payload = registration_setup
    client.post(reverse("professionals:register"), payload)
    profile = Professional.objects.get(user=subject)
    response = client.post(
        reverse("professionals:register"), payload, HTTP_HX_REQUEST="true"
    )
    assert response.status_code == 422
    assert b'data-field-error="username"' in response.content
    assert (
        reverse("professionals:detail", args=[profile.pk]).encode() in response.content
    )
    other = user_factory(username="other-subject")
    payload["username"] = other.username
    response = client.post(
        reverse("professionals:register"), payload, HTTP_HX_REQUEST="true"
    )
    assert b'data-field-error="dni"' in response.content
    assert not Professional.objects.filter(user=other).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("active", [True, False])
def test_complete_legacy_profile_keeps_identity_state_and_fixed_account(
    client, registration_setup, active
):
    subject, payload = registration_setup
    legacy = Professional.objects.create(user=subject, is_active=active)
    payload["username"] = "tampered-account"
    response = client.post(reverse("professionals:complete", args=[legacy.pk]), payload)
    assert response.status_code == 302
    legacy.refresh_from_db()
    assert legacy.user_id == subject.pk and legacy.is_active == active
    assert legacy.is_registration_complete
    assert Professional.objects.count() == 1
    if not active:
        assert b"Reactivate professional" in client.get(response.url).content


@pytest.mark.django_db
def test_index_tabs_search_prefill_and_stable_pagination(
    client, registration_setup, user_factory
):
    subject, payload = registration_setup
    for index in range(21):
        Professional.objects.create(user=user_factory(username=f"legacy-{index:02d}"))
    first = client.get(reverse("professionals:index"), {"status": "incomplete"})
    assert len(first.context["page_obj"]) == 20
    second = client.get(
        reverse("professionals:index"), {"status": "incomplete", "page": 2}
    )
    assert len(second.context["page_obj"]) == 1
    response = client.get(reverse("professionals:search"), {"dni": " 01234567 "})
    assert b"?dni=01234567" in response.content
    assert not Professional.objects.filter(user=subject).exists()
    client.post(reverse("professionals:register"), payload)
    profile = Professional.objects.get(user=subject)
    response = client.get(reverse("professionals:search"), {"dni": "01234567"})
    assert profile.registration_number.encode() in response.content
    profile.is_active = False
    profile.save(update_fields=["is_active"])
    response = client.get(reverse("professionals:search"), {"dni": "01234567"})
    assert b"No active registered professional" in response.content
    assert (
        profile
        in client.get(reverse("professionals:index"), {"status": "inactive"}).context[
            "page_obj"
        ]
    )


@pytest.mark.django_db
def test_professional_search_results_are_announced_to_screen_readers(
    client, registration_setup
):
    response = client.get(reverse("professionals:search"))

    assert b'aria-live="polite"' in response.content
    assert b'aria-atomic="true"' in response.content


@pytest.mark.django_db
def test_status_confirmation_and_inactive_edit(client, registration_setup):
    subject, payload = registration_setup
    client.post(reverse("professionals:register"), payload)
    profile = Professional.objects.get(user=subject)
    deactivate = reverse("professionals:deactivate", args=[profile.pk])
    assert client.post(deactivate, {}).status_code == 200
    profile.refresh_from_db()
    assert profile.is_active
    assert client.post(deactivate, {"confirm": "on"}).status_code == 302
    profile.refresh_from_db()
    assert not profile.is_active
    changes = {
        key: value for key, value in payload.items() if key not in {"username", "dni"}
    }
    changes["last_name"] = "Byron"
    assert (
        client.post(
            reverse("professionals:update", args=[profile.pk]), changes
        ).status_code
        == 302
    )
    profile.refresh_from_db()
    assert profile.last_name == "Byron" and not profile.is_active
    assert (
        client.post(
            reverse("professionals:reactivate", args=[profile.pk]), {"confirm": "on"}
        ).status_code
        == 302
    )
    profile.refresh_from_db()
    assert profile.is_active


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name",
    [
        "index",
        "register",
        "search",
        "detail",
        "complete",
        "update",
        "deactivate",
        "reactivate",
    ],
)
def test_authorization_precedes_profile_lookup(client, user_factory, name):
    url = reverse(
        f"professionals:{name}",
        kwargs={"pk": 99999}
        if name in {"detail", "complete", "update", "deactivate", "reactivate"}
        else {},
    )
    assert client.get(url).status_code == 302
    user = user_factory(username="medical-only")
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    client.force_login(user)
    assert client.get(url).status_code == 403
    assert b"/professionals/" not in client.get(reverse("home")).content


@pytest.mark.django_db
def test_registration_enforces_csrf(registration_setup):
    _, payload = registration_setup
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(get_user_model().objects.get(username="professional-admin"))
    assert (
        csrf_client.post(reverse("professionals:register"), payload).status_code == 403
    )
