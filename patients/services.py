from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from access_control.actors import ActorContext
from access_control.policies import ADMINISTRATIVE_POLICY
from patients.models import Patient


class PatientServiceError(ValueError):
    """Base error for patient application-service operations."""


class DuplicateActivePatientDNIError(PatientServiceError):
    def __init__(self, patient: Patient):
        self.patient = patient
        super().__init__("An active patient with this DNI already exists.")


class DeactivationConfirmationRequiredError(PatientServiceError):
    """Raised when patient deactivation has not been explicitly confirmed."""


@transaction.atomic
def create_patient(
    *,
    actor: ActorContext | None,
    dni: str,
    first_name: str,
    last_name: str,
    date_of_birth: date,
    sex: str,
    phone: str,
    email: str,
    address: str,
    health_insurer: str,
) -> Patient:
    ADMINISTRATIVE_POLICY.require(actor)

    existing_patient = Patient.objects.filter(dni=dni).first()
    if existing_patient is not None:
        raise DuplicateActivePatientDNIError(existing_patient)

    patient = Patient(
        dni=dni,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        sex=sex,
        phone=phone,
        email=email,
        address=address,
        health_insurer=health_insurer,
    )
    patient.full_clean()

    try:
        with transaction.atomic():
            patient.save(force_insert=True)
    except IntegrityError as error:
        existing_patient = Patient.objects.filter(dni=dni).first()
        if existing_patient is not None:
            raise DuplicateActivePatientDNIError(existing_patient) from error
        raise

    return patient


@transaction.atomic
def update_patient(
    *,
    actor: ActorContext | None,
    patient: Patient,
    changes: dict[str, object],
) -> Patient:
    ADMINISTRATIVE_POLICY.require(actor)
    if not patient.is_active:
        raise ValidationError({"__all__": "Inactive patients cannot be updated."})

    mutable_fields = {
        "first_name",
        "last_name",
        "date_of_birth",
        "sex",
        "phone",
        "email",
        "address",
        "health_insurer",
    }
    for field_name, value in changes.items():
        if field_name not in mutable_fields:
            raise ValidationError({field_name: "This field is immutable."})
        setattr(patient, field_name, value)

    patient.full_clean()
    patient.save(update_fields=sorted(changes))
    return patient


@transaction.atomic
def deactivate_patient(
    *,
    actor: ActorContext | None,
    patient: Patient,
    confirmed: bool,
) -> Patient:
    ADMINISTRATIVE_POLICY.require(actor)
    if not confirmed:
        raise DeactivationConfirmationRequiredError(
            "Patient deactivation requires explicit confirmation."
        )

    if patient.is_active:
        patient.is_active = False
        patient.save(update_fields=["is_active"])
    return patient


def lookup_active_patient_by_dni(
    *,
    actor: ActorContext | None,
    dni: str,
) -> Patient | None:
    """Return the active patient whose DNI exactly matches a canonical value."""
    ADMINISTRATIVE_POLICY.require(actor)
    Patient._meta.get_field("dni").run_validators(dni)
    return Patient.objects.filter(dni=dni).first()
