"""Administrative care-team assignment with current-state locking."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from access_control.actors import ActorContext
from access_control.policies import ADMINISTRATIVE_POLICY
from access_control.roles import MEDICAL_PROFESSIONAL_GROUP
from clinical_records.models import CareRelationship
from patients.models import Patient
from professionals.models import Professional
from professionals.validators import canonicalize_professional_dni


class CareConfirmationRequired(ValueError):
    pass


def _administrator(actor: ActorContext | None) -> User:
    authorized = ADMINISTRATIVE_POLICY.require(actor)
    user = (
        get_user_model()
        .objects.filter(
            pk=authorized.user_id,
            is_active=True,
            groups__name=ADMINISTRATIVE_POLICY.required_role.value,
        )
        .first()
    )
    if user is None:
        raise PermissionDenied("An active administrative account is required.")
    return user


@transaction.atomic
def assign_care_relationship(
    *, actor: ActorContext | None, patient: Patient, professional_dni: str
) -> tuple[CareRelationship, bool]:
    administrator = _administrator(actor)
    dni = canonicalize_professional_dni(professional_dni)
    candidate = (
        Professional.objects.filter(
            dni=dni, is_active=True, registration_completed_at__isnull=False
        )
        .order_by("pk")
        .first()
    )
    if candidate is None:
        raise ValidationError(
            {"professional_dni": "Select an eligible professional by DNI."}
        )

    # Global order: subject User, Professional, Patient, CareRelationship.
    subject = get_user_model().objects.select_for_update().get(pk=candidate.user_id)
    professional = Professional.objects.select_for_update().get(pk=candidate.pk)
    if not (
        subject.is_active
        and subject.groups.filter(name=MEDICAL_PROFESSIONAL_GROUP).exists()
        and professional.is_active
        and professional.registration_completed_at is not None
        and professional.dni == dni
    ):
        raise ValidationError(
            {"professional_dni": "Select an eligible professional by DNI."}
        )
    target = Patient.all_objects.select_for_update().filter(pk=patient.pk).first()
    if target is None or not target.is_active:
        raise ValidationError({"patient": "Select an active patient."})
    existing = (
        CareRelationship.objects.select_for_update()
        .filter(patient=target, professional=professional, is_active=True)
        .first()
    )
    if existing is not None:
        return existing, False
    try:
        with transaction.atomic():
            return CareRelationship.objects.create(
                patient=target, professional=professional, assigned_by=administrator
            ), True
    except IntegrityError:
        existing = CareRelationship.objects.filter(
            patient=target, professional=professional, is_active=True
        ).first()
        if existing is not None:
            return existing, False
        raise


@transaction.atomic
def revoke_care_relationship(
    *,
    actor: ActorContext | None,
    patient: Patient,
    relationship: CareRelationship,
    confirmed: bool,
) -> CareRelationship:
    administrator = _administrator(actor)
    if not confirmed:
        raise CareConfirmationRequired(
            "Care relationship revocation requires confirmation."
        )
    target = Patient.all_objects.select_for_update().filter(pk=patient.pk).first()
    if target is None:
        raise ValidationError({"patient": "Patient not found."})
    assignment = (
        CareRelationship.objects.select_for_update()
        .filter(pk=relationship.pk, patient_id=target.pk)
        .first()
    )
    if assignment is None:
        raise ValidationError(
            {"relationship": "Care relationship not found for this patient."}
        )
    if assignment.is_active:
        assignment.is_active = False
        assignment.revoked_at = timezone.now()
        assignment.revoked_by = administrator
        assignment.save(update_fields=["is_active", "revoked_at", "revoked_by"])
    return assignment


def revoke_active_relationships(
    *,
    patient: Patient | None = None,
    professional: Professional | None = None,
    actor_user_id: int,
) -> None:
    """Called only after the endpoint row has been locked in the caller's transaction."""
    assignments = CareRelationship.objects.select_for_update().filter(is_active=True)
    if patient is not None:
        assignments = assignments.filter(patient=patient)
    if professional is not None:
        assignments = assignments.filter(professional=professional)
    now = timezone.now()
    for assignment in assignments.order_by("pk"):
        assignment.is_active = False
        assignment.revoked_at = now
        assignment.revoked_by_id = actor_user_id
        assignment.save(update_fields=["is_active", "revoked_at", "revoked_by"])
