import pytest
from django.contrib.auth.models import Group, Permission
from django.urls import reverse
from django.utils import timezone

from access_control.roles import (
    ADMINISTRATIVE_GROUP,
    MEDICAL_PROFESSIONAL_GROUP,
)
from professionals.models import HospitalService, Professional, Specialty


def create_completed_profile(user) -> Professional:
    specialty, _ = Specialty.objects.get_or_create(
        code="login-general", defaults={"name": "Login General"}
    )
    service, _ = HospitalService.objects.get_or_create(
        code="login-ward", defaults={"name": "Login Ward"}
    )
    return Professional.objects.create(
        user=user,
        dni=str(60_000_000 + user.pk),
        license_number=f"MN {user.pk:06d}",
        registration_number=f"PR-LOGIN-{user.pk:08d}",
        first_name="Login",
        last_name="Professional",
        date_of_birth="1990-01-01",
        specialty=specialty,
        hospital_service=service,
        registration_completed_at=timezone.now(),
    )


@pytest.mark.django_db
def test_non_staff_completed_medical_role_login_opens_workspace(
    client,
    user_factory,
):
    password = "application-login-password"
    user = user_factory(
        username="application-medical-professional",
        password=password,
        is_staff=False,
    )
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))

    professional = create_completed_profile(user)

    response = client.post(
        reverse("login"),
        {"username": user.username, "password": password},
    )

    assert response.status_code == 302
    assert response.url == reverse("clinical_records:dashboard")
    assert Professional.objects.get(user=user) == professional
    assert client.get(response.url).status_code == 200


@pytest.mark.django_db
def test_administrative_application_login_opens_patient_search(client, user_factory):
    password = "application-login-password"
    user = user_factory(
        username="application-administrator",
        password=password,
        is_staff=False,
    )
    user.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))

    response = client.post(
        reverse("login"),
        {"username": user.username, "password": password},
    )

    assert response.status_code == 302
    assert response.url == reverse("patients:search")


@pytest.mark.django_db
def test_medical_role_without_active_profile_cannot_open_workspace(
    client,
    user_factory,
):
    user = user_factory(username="unlinked-application-professional")
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    client.force_login(user)

    response = client.get(reverse("clinical_records:dashboard"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_application_login_does_not_reactivate_inactive_professional(
    client,
    user_factory,
):
    password = "inactive-professional-password"
    user = user_factory(
        username="inactive-application-professional",
        password=password,
    )
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    professional = Professional.objects.create(user=user, is_active=False)

    response = client.post(
        reverse("login"),
        {"username": user.username, "password": password},
    )

    assert response.status_code == 302
    assert response.url == reverse("home")
    professional.refresh_from_db()
    assert not professional.is_active


@pytest.mark.django_db
def test_medical_role_login_with_workspace_next_is_denied_without_registration(
    client,
    user_factory,
):
    password = "workspace-next-password"
    user = user_factory(username="workspace-next-professional", password=password)
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    dashboard_url = reverse("clinical_records:dashboard")

    response = client.post(
        f"{reverse('login')}?next={dashboard_url}",
        {
            "username": user.username,
            "password": password,
            "next": dashboard_url,
        },
        follow=True,
    )

    assert response.status_code == 200
    assert response.request["PATH_INFO"] == reverse("home")
    assert b"Professional registration or reactivation is required" in response.content
    assert not Professional.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_authenticated_medical_role_on_home_is_explained_without_registration(
    client,
    user_factory,
):
    user = user_factory(username="medical-professional-on-home")
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    client.force_login(user)

    response = client.get(reverse("home"))

    assert response.status_code == 200
    assert b"Professional registration or reactivation is required" in response.content
    assert not Professional.objects.filter(user=user).exists()


def test_anonymous_workspace_request_redirects_to_application_login(client):
    dashboard_url = reverse("clinical_records:dashboard")

    response = client.get(dashboard_url)

    assert response.status_code == 302
    assert response.url == f"{reverse('login')}?next={dashboard_url}"


@pytest.mark.django_db
def test_staff_medical_professional_admin_login_redirects_to_clinical_workspace(
    client,
    user_factory,
):
    password = "legacy-admin-login-password"
    user = user_factory(
        username="legacy-staff-medical-professional",
        password=password,
        is_staff=True,
    )
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    profile = create_completed_profile(user)

    admin_index = reverse("admin:index")
    response = client.post(
        f"{reverse('admin:login')}?next={admin_index}",
        {
            "username": user.username,
            "password": password,
            "next": admin_index,
        },
        follow=True,
    )

    assert response.status_code == 200
    assert response.redirect_chain == [
        (admin_index, 302),
        (reverse("clinical_records:dashboard"), 302),
    ]
    assert response.request["PATH_INFO"] == reverse("clinical_records:dashboard")
    assert b"Clinical workspace" in response.content
    assert Professional.objects.get(user=user) == profile


@pytest.mark.django_db
def test_medical_staff_user_with_admin_permission_stays_in_django_admin(
    client,
    user_factory,
):
    user = user_factory(
        username="medical-professional-with-admin-permission",
        is_staff=True,
    )
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    user.user_permissions.add(Permission.objects.get(codename="view_group"))
    Professional.objects.create(user=user)
    client.force_login(user)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 200
    assert b"Django administration" in response.content
