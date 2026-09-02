from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction

from access_control.actors import ActorContext
from access_control.policies import MEDICAL_PROFESSIONAL_POLICY
from clinical_records.models import Admission
from patients.models import Patient
from professionals.models import Professional


class InactivePatientError(ValueError):
    """Raised when a clinical event targets an inactive patient."""


def active_professional_for_actor(actor: ActorContext | None) -> Professional:
    actor = MEDICAL_PROFESSIONAL_POLICY.require(actor)
    try:
        return Professional.objects.get(
            user_id=actor.user_id,
            user__is_active=True,
            is_active=True,
        )
    except Professional.DoesNotExist as error:
        raise PermissionDenied(
            "An active medical-professional profile is required."
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
    professional = active_professional_for_actor(actor)
    if not patient.is_active:
        raise InactivePatientError("Admissions require an active patient.")

    admission = Admission(
        patient=patient,
        professional=professional,
        consultation_reason=consultation_reason.strip(),
        systolic_blood_pressure=systolic_blood_pressure,
        diastolic_blood_pressure=diastolic_blood_pressure,
        heart_rate=heart_rate,
        temperature=temperature,
    )
    admission.full_clean()
    admission.save(force_insert=True)
    return admission
