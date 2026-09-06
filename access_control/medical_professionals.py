from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from access_control.actors import actor_context_from_user
from access_control.policies import MEDICAL_PROFESSIONAL_POLICY
from professionals.models import Professional


def has_active_medical_professional_context(
    user: AbstractBaseUser | AnonymousUser,
    *,
    provision_missing: bool = False,
) -> bool:
    """Return legacy clinical eligibility while HU-04 completion UI rolls out."""
    if not user.is_authenticated or not user.is_active or user.pk is None:
        return False

    actor = actor_context_from_user(user)
    if not MEDICAL_PROFESSIONAL_POLICY.allows(actor):
        return False

    try:
        professional = Professional.objects.get(user_id=user.pk)
    except Professional.DoesNotExist:
        if not provision_missing:
            return False
        professional, _ = Professional.objects.get_or_create(user_id=user.pk)

    return professional.is_active


def has_completed_active_medical_professional_context(
    user: AbstractBaseUser | AnonymousUser,
) -> bool:
    """Return whether a medical-role user has completed registration."""
    if not has_active_medical_professional_context(user):
        return False
    user_id = user.pk
    if user_id is None:
        return False
    return Professional.objects.filter(
        user_id=user_id,
        is_active=True,
        registration_completed_at__isnull=False,
    ).exists()


class IsActiveMedicalProfessionalActor(BasePermission):
    """Require both the medical role and an active professional profile."""

    message = "An active medical-professional profile is required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return has_active_medical_professional_context(request.user)
