from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AbstractUser, AnonymousUser

from access_control.roles import (
    ADMINISTRATIVE_GROUP,
    MEDICAL_PROFESSIONAL_GROUP,
    ROLE_GROUPS,
)


class ActorRole(StrEnum):
    ADMINISTRATIVE = ADMINISTRATIVE_GROUP
    MEDICAL_PROFESSIONAL = MEDICAL_PROFESSIONAL_GROUP


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Authenticated application actor and the domain roles assigned to them."""

    user_id: int
    roles: frozenset[ActorRole]

    def has_role(self, role: ActorRole) -> bool:
        return role in self.roles


def actor_context_from_user(
    user: AbstractBaseUser | AnonymousUser,
) -> ActorContext | None:
    """Resolve an authenticated Django user into the shared actor context."""
    if not user.is_authenticated:
        return None
    if user.pk is None:
        raise ValueError("An authenticated actor must have a persisted user ID.")

    role_user = cast(AbstractUser, user)
    group_names = role_user.groups.filter(name__in=ROLE_GROUPS).values_list(
        "name",
        flat=True,
    )
    roles = frozenset(ActorRole(group_name) for group_name in group_names)
    return ActorContext(user_id=role_user.pk, roles=roles)
