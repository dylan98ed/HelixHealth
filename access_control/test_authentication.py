from importlib import import_module

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import migrations
from django.http import JsonResponse
from django.test import override_settings
from django.urls import path
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.views import APIView

from access_control.roles import ROLE_GROUPS


class UnsafeSessionProbeView(APIView):
    def post(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


@ensure_csrf_cookie
def csrf_seed(request):
    return JsonResponse({"csrf": "ready"})


urlpatterns = [
    path("csrf/", csrf_seed),
    path("unsafe-session-probe/", UnsafeSessionProbeView.as_view()),
]


def test_role_group_migration_uses_a_non_destructive_reverse():
    migration_module = import_module(
        "access_control.migrations.0001_seed_role_groups"
    )
    operation = migration_module.Migration.operations[0]

    assert operation.reverse_code is migrations.RunPython.noop


@pytest.mark.django_db
def test_role_groups_are_seeded():
    assert set(
        Group.objects.filter(name__in=ROLE_GROUPS).values_list("name", flat=True)
    ) == set(ROLE_GROUPS)


@override_settings(ROOT_URLCONF=__name__)
def test_browsable_api_renders_html_for_anonymous_requests():
    response = APIClient().get(
        "/unsafe-session-probe/",
        HTTP_ACCEPT="text/html",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response["Content-Type"].startswith("text/html")


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=__name__)
def test_unsafe_session_request_requires_authentication_and_csrf():
    anonymous_client = APIClient(enforce_csrf_checks=True)
    anonymous_response = anonymous_client.post(
        "/unsafe-session-probe/",
        {},
        format="json",
    )
    assert anonymous_response.status_code == status.HTTP_403_FORBIDDEN

    password = "foundation-test-password"
    user = get_user_model().objects.create_user(
        username="foundation-user",
        password=password,
    )
    authenticated_client = APIClient(enforce_csrf_checks=True)
    assert authenticated_client.login(username=user.username, password=password)

    missing_csrf_response = authenticated_client.post(
        "/unsafe-session-probe/",
        {},
        format="json",
    )
    assert missing_csrf_response.status_code == status.HTTP_403_FORBIDDEN

    csrf_response = authenticated_client.get("/csrf/")
    csrf_token = csrf_response.cookies["csrftoken"].value
    valid_response = authenticated_client.post(
        "/unsafe-session-probe/",
        {},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert valid_response.status_code == status.HTTP_204_NO_CONTENT
