"""Care-team scope shared by the chart directory, individual reads and writes."""

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404

from access_control.actors import ActorContext, ActorRole, actor_context_from_user
from clinical_records.models import CareRelationship
from patients.models import Patient
from professionals.models import Professional


def chart_assignments(actor: ActorContext | None) -> QuerySet[CareRelationship]:
    if actor is None or not actor.has_role(ActorRole.MEDICAL_PROFESSIONAL):
        raise PermissionDenied
    return CareRelationship.objects.filter(
        is_active=True,
        patient__is_active=True,
        professional__is_active=True,
        professional__registration_completed_at__isnull=False,
        professional__user_id=actor.user_id,
        professional__user__is_active=True,
        professional__user__groups__name=ActorRole.MEDICAL_PROFESSIONAL.value,
    )


def can_read_patient_history(actor: ActorContext | None, patient: Patient) -> bool:
    return chart_assignments(actor).filter(patient=patient).exists()


def assigned_patient(request: HttpRequest, patient_pk: int) -> Patient:
    patient = get_object_or_404(Patient.objects, pk=patient_pk)
    if not can_read_patient_history(actor_context_from_user(request.user), patient):
        raise PermissionDenied
    return patient


def chart_assignment(
    actor: ActorContext | None, patient_pk: int, *, for_update: bool = False
) -> CareRelationship:
    """A writer must request for_update inside the transaction that saves its change."""
    assignments = chart_assignments(actor).filter(patient_id=patient_pk)
    if for_update:
        assert actor is not None
        # Match assignment and identity lifecycle lock order, then recheck scope.
        if (
            not User.objects.select_for_update(no_key=True)
            .filter(pk=actor.user_id, is_active=True)
            .exists()
        ):
            raise PermissionDenied
        if (
            not Professional.objects.select_for_update(no_key=True)
            .filter(user_id=actor.user_id, is_active=True)
            .exists()
        ):
            raise PermissionDenied
        if not Patient.objects.select_for_update().filter(pk=patient_pk).exists():
            raise PermissionDenied
        assignments = assignments.select_for_update(of=("self",))
    relationship = assignments.select_related("patient", "professional").first()
    if relationship is None:
        raise PermissionDenied
    return relationship
