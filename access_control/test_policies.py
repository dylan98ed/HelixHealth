import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import override_settings
from django.urls import path
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.views import APIView

from access_control.actors import ActorContext, ActorRole, actor_context_from_user
from access_control.policies import (
    ADMINISTRATIVE_POLICY,
    MEDICAL_PROFESSIONAL_POLICY,
    IsAdministrativeActor,
    IsMedicalProfessionalActor,
    MissingActorError,
    RoleNotPermittedError,
)
from access_control.roles import (
    ADMINISTRATIVE_GROUP,
    MEDICAL_PROFESSIONAL_GROUP,
)


class AdministrativeProbeView(APIView):
    permission_classes = [IsAdministrativeActor]

    def post(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


class MedicalProfessionalProbeView(APIView):
    permission_classes = [IsMedicalProfessionalActor]

    def post(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


urlpatterns = [
    path("administrative/", AdministrativeProbeView.as_view()),
    path("medical-professional/", MedicalProfessionalProbeView.as_view()),
]


class RoleGroups:
    def __init__(self, names):
        self.names = tuple(names)

    def filter(self, *, name__in):
        return RoleGroups(name for name in self.names if name in name__in)

    def values_list(self, field_name, *, flat):
        assert field_name == "name"
        assert flat is True
        return self.names


class AuthenticatedUser:
    is_authenticated = True

    def __init__(self, user_id, *roles):
        self.pk = user_id
        self.groups = RoleGroups(roles)


def test_actor_context_distinguishes_missing_and_assigned_roles():
    administrative_user = AuthenticatedUser(1, ADMINISTRATIVE_GROUP)
    professional_user = AuthenticatedUser(2, MEDICAL_PROFESSIONAL_GROUP)

    assert actor_context_from_user(AnonymousUser()) is None
    assert actor_context_from_user(administrative_user).roles == {  # type: ignore[arg-type]
        ActorRole.ADMINISTRATIVE
    }
    assert actor_context_from_user(professional_user).roles == {  # type: ignore[arg-type]
        ActorRole.MEDICAL_PROFESSIONAL
    }


def test_role_policy_reports_missing_and_wrong_role_separately():
    with pytest.raises(MissingActorError):
        ADMINISTRATIVE_POLICY.require(None)

    with pytest.raises(RoleNotPermittedError):
        ADMINISTRATIVE_POLICY.require(
            ActorContext(
                user_id=1,
                roles=frozenset({ActorRole.MEDICAL_PROFESSIONAL}),
            )
        )


@pytest.mark.parametrize(
    ("url", "allowed_group", "denied_group"),
    [
        (
            "/administrative/",
            ADMINISTRATIVE_GROUP,
            MEDICAL_PROFESSIONAL_GROUP,
        ),
        (
            "/medical-professional/",
            MEDICAL_PROFESSIONAL_GROUP,
            ADMINISTRATIVE_GROUP,
        ),
    ],
)
@override_settings(ROOT_URLCONF=__name__)
def test_protected_operation_distinguishes_missing_allowed_and_wrong_actor(
    url,
    allowed_group,
    denied_group,
):
    client = APIClient()

    assert client.post(url).status_code == status.HTTP_403_FORBIDDEN

    allowed_user = AuthenticatedUser(1, allowed_group)
    client.force_authenticate(allowed_user)
    assert client.post(url).status_code == status.HTTP_204_NO_CONTENT

    denied_user = AuthenticatedUser(2, denied_group)
    client.force_authenticate(denied_user)
    assert client.post(url).status_code == status.HTTP_403_FORBIDDEN


def test_actor_with_both_roles_can_use_both_policies():
    user = AuthenticatedUser(
        1,
        ADMINISTRATIVE_GROUP,
        MEDICAL_PROFESSIONAL_GROUP,
    )
    actor = actor_context_from_user(user)  # type: ignore[arg-type]

    assert ADMINISTRATIVE_POLICY.require(actor) is actor
    assert MEDICAL_PROFESSIONAL_POLICY.require(actor) is actor
