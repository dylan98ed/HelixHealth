from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction

from access_control.actors import ActorContext, ActorRole
from access_control.policies import ADMINISTRATIVE_POLICY, MEDICAL_PROFESSIONAL_POLICY
from clinical_records.models import Admission
from patients.models import Patient
from professionals.models import Professional


class InactivePatientError(ValueError):
    """Raised when a clinical event targets an inactive patient."""


def admission_author_for_actor(actor: ActorContext | None):
    """Resolve the current recorder and any clinical professional identity."""
    if actor is None:
        MEDICAL_PROFESSIONAL_POLICY.require(actor)
    assert actor is not None
    if actor.has_role(ActorRole.MEDICAL_PROFESSIONAL):
        try:
            professional = active_professional_for_actor(actor)
        except PermissionDenied:
            if not actor.has_role(ActorRole.ADMINISTRATIVE):
                raise
        else:
            return professional.user, professional
    ADMINISTRATIVE_POLICY.require(actor)
    administrator = (
        get_user_model()
        .objects.filter(
            pk=actor.user_id,
            is_active=True,
            groups__name=ActorRole.ADMINISTRATIVE.value,
        )
        .first()
    )
    if administrator is None:
        raise PermissionDenied("An active administrative account is required.")
    return administrator, None


def active_professional_for_actor(actor: ActorContext | None) -> Professional:
    actor = MEDICAL_PROFESSIONAL_POLICY.require(actor)
    try:
        return Professional.objects.get(
            user_id=actor.user_id,
            user__is_active=True,
            is_active=True,
            registration_completed_at__isnull=False,
        )
    except Professional.DoesNotExist as error:
        raise PermissionDenied(
            "An active completed professional registration is required."
        ) from error


def lookup_active_patient_for_admission(
    *,
    actor: ActorContext | None,
    dni: str,
) -> Patient | None:
    active_professional_for_actor(actor)
    Patient._meta.get_field("dni").run_validators(dni)
    return Patient.objects.filter(dni=dni).first()


@transaction.atomic
def create_admission(
    *,
    actor: ActorContext | None,
    patient: Patient,
    consultation_reason: str,
    systolic_blood_pressure: int,
    diastolic_blood_pressure: int,
    heart_rate: int,
    temperature: Decimal,
) -> Admission:
    recorder, professional = admission_author_for_actor(actor)
    locked_patient = (
        Patient.all_objects.select_for_update().filter(pk=patient.pk).first()
    )
    if locked_patient is None or not locked_patient.is_active:
        raise InactivePatientError("Admissions require an active patient.")

    admission = Admission(
        patient=locked_patient,
        professional=professional,
        recorded_by=recorder,
        consultation_reason=consultation_reason.strip(),
        systolic_blood_pressure=systolic_blood_pressure,
        diastolic_blood_pressure=diastolic_blood_pressure,
        heart_rate=heart_rate,
        temperature=temperature,
    )
    admission.full_clean()
    admission.save(force_insert=True)
    return admission
