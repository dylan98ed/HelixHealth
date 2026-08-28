from dataclasses import dataclass
from typing import ClassVar

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from access_control.actors import ActorContext, ActorRole, actor_context_from_user


class AuthorizationError(PermissionError):
    """Base error for denied application-service operations."""


class MissingActorError(AuthorizationError):
    """Raised when an operation has no authenticated actor."""


class RoleNotPermittedError(AuthorizationError):
    """Raised when an actor lacks the role required by an operation."""


@dataclass(frozen=True, slots=True)
class RolePolicy:
    required_role: ActorRole

    def allows(self, actor: ActorContext | None) -> bool:
        return actor is not None and actor.has_role(self.required_role)

    def require(self, actor: ActorContext | None) -> ActorContext:
        if actor is None:
            raise MissingActorError("This operation requires an authenticated actor.")
        if not self.allows(actor):
            raise RoleNotPermittedError(
                f"This operation requires the {self.required_role.value} role."
            )
        return actor


ADMINISTRATIVE_POLICY = RolePolicy(ActorRole.ADMINISTRATIVE)
MEDICAL_PROFESSIONAL_POLICY = RolePolicy(ActorRole.MEDICAL_PROFESSIONAL)


class RolePermission(BasePermission):
    policy: ClassVar[RolePolicy]

    def has_permission(self, request: Request, view: APIView) -> bool:
        actor = actor_context_from_user(request.user)
        return self.policy.allows(actor)


class IsAdministrativeActor(RolePermission):
    message = "This operation requires an administrative actor."
    policy = ADMINISTRATIVE_POLICY


class IsMedicalProfessionalActor(RolePermission):
    message = "This operation requires a medical-professional actor."
    policy = MEDICAL_PROFESSIONAL_POLICY
