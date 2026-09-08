"""Transactional professional lifecycle services."""

from datetime import date
from typing import cast

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from access_control.actors import ActorContext
from access_control.policies import ADMINISTRATIVE_POLICY
from access_control.roles import MEDICAL_PROFESSIONAL_GROUP
from professionals.identifiers import generate_registration_number
from professionals.models import HospitalService, Professional, Specialty
from professionals.validators import (
    canonicalize_professional_dni,
    normalize_license_number,
    normalize_required_name,
    validate_active_reference,
    validate_professional_date_of_birth,
)


class ProfessionalServiceError(ValueError):
    pass


class ProfessionalConflictError(ProfessionalServiceError):
    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        existing_professional_id: int | None = None,
    ):
        super().__init__(message)
        self.field = field
        self.existing_professional_id = existing_professional_id


class ConfirmationRequiredError(ProfessionalServiceError):
    pass


def _actor(actor: ActorContext | None) -> ActorContext:
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
    return authorized


def _references(
    specialty_code: str, hospital_service_code: str
) -> tuple[Specialty, HospitalService]:
    specialty = (
        Specialty.objects.select_for_update().filter(code=specialty_code).first()
    )
    service = (
        HospitalService.objects.select_for_update()
        .filter(code=hospital_service_code)
        .first()
    )
    validate_active_reference(specialty, field_name="specialty")
    validate_active_reference(service, field_name="hospital service")
    return cast(Specialty, specialty), cast(HospitalService, service)


def _replacement_specialty(code: str, current_id: int | None) -> Specialty:
    specialty = Specialty.objects.select_for_update().filter(code=code).first()
    if specialty is None or specialty.pk != current_id:
        validate_active_reference(specialty, field_name="specialty")
    return cast(Specialty, specialty)


def _replacement_hospital_service(code: str, current_id: int | None) -> HospitalService:
    service = HospitalService.objects.select_for_update().filter(code=code).first()
    if service is None or service.pk != current_id:
        validate_active_reference(service, field_name="hospital service")
    return cast(HospitalService, service)


def _is_active_dni_constraint(error: IntegrityError) -> bool:
    cause = error.__cause__
    return bool(
        getattr(cause, "sqlstate", getattr(cause, "pgcode", None)) == "23505"
        and getattr(getattr(cause, "diag", None), "constraint_name", None)
        == "unique_active_professional_dni"
    )


def lookup_professional_by_dni(
    *, actor: ActorContext | None, dni: str
) -> Professional | None:
    _actor(actor)
    return (
        Professional.objects.select_related("user")
        .filter(
            dni=canonicalize_professional_dni(dni),
            is_active=True,
            registration_completed_at__isnull=False,
        )
        .first()
    )


def professional_index_queryset(
    *, actor: ActorContext | None, status: str
) -> QuerySet[Professional]:
    _actor(actor)
    profiles = Professional.objects.select_related(
        "user", "specialty", "hospital_service"
    )
    if status == "incomplete":
        profiles = profiles.filter(registration_completed_at__isnull=True)
    else:
        profiles = profiles.filter(
            registration_completed_at__isnull=False,
            is_active=status != "inactive",
        )
    return profiles.order_by("last_name", "first_name", "id")


@transaction.atomic
def register_professional(
    *,
    actor: ActorContext | None,
    username: str,
    dni: str,
    license_number: object,
    first_name: str,
    last_name: str,
    date_of_birth: date,
    specialty_code: str,
    hospital_service_code: str,
) -> Professional:
    _actor(actor)
    canonical_dni = canonicalize_professional_dni(dni)
    license_number = normalize_license_number(license_number)
    first_name = normalize_required_name(first_name)
    last_name = normalize_required_name(last_name)
    validate_professional_date_of_birth(date_of_birth)
    subject = (
        get_user_model()
        .objects.select_for_update()
        .filter(username=username, is_active=True)
        .first()
    )
    if subject is None:
        raise ValidationError({"username": "Select an existing active account."})
    profile = Professional.objects.select_for_update().filter(user=subject).first()
    if profile is not None and profile.is_registration_complete:
        raise ProfessionalConflictError(
            "This account already has a completed profile.",
            field="username",
            existing_professional_id=profile.pk,
        )
    profile = profile or Professional(user=subject, is_active=True)
    if profile.is_active:
        duplicate = (
            Professional.objects.filter(dni=canonical_dni, is_active=True)
            .exclude(user=subject)
            .first()
        )
        if duplicate is not None:
            raise ProfessionalConflictError(
                "An active professional already has this DNI.",
                field="dni",
                existing_professional_id=duplicate.pk,
            )
    specialty, service = _references(specialty_code, hospital_service_code)
    profile.dni, profile.license_number, profile.first_name, profile.last_name = (
        canonical_dni,
        license_number,
        first_name,
        last_name,
    )
    profile.date_of_birth, profile.specialty, profile.hospital_service = (
        date_of_birth,
        specialty,
        service,
    )
    profile.registration_number = (
        profile.registration_number or generate_registration_number()
    )
    profile.registration_completed_at = (
        profile.registration_completed_at or timezone.now()
    )
    try:
        profile.full_clean(validate_unique=False, validate_constraints=False)
        with transaction.atomic():
            profile.save()
    except IntegrityError as error:
        if _is_active_dni_constraint(error):
            duplicate = Professional.objects.filter(
                dni=canonical_dni, is_active=True
            ).first()
            raise ProfessionalConflictError(
                "An active professional already has this DNI.",
                field="dni",
                existing_professional_id=duplicate.pk if duplicate else None,
            ) from error
        raise
    subject.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    return profile


@transaction.atomic
def update_professional(
    *,
    actor: ActorContext | None,
    professional: Professional,
    changes: dict[str, object],
) -> Professional:
    _actor(actor)
    profile = Professional.objects.select_for_update().get(pk=professional.pk)
    if not profile.is_registration_complete:
        raise ValidationError({"__all__": "Incomplete profiles must be completed."})
    allowed = {
        "first_name",
        "last_name",
        "date_of_birth",
        "specialty_code",
        "hospital_service_code",
        "license_number",
    }
    unknown = set(changes) - allowed
    if unknown:
        raise ValidationError({key: "This field is immutable." for key in unknown})
    if "first_name" in changes:
        profile.first_name = normalize_required_name(cast(str, changes["first_name"]))
    if "last_name" in changes:
        profile.last_name = normalize_required_name(cast(str, changes["last_name"]))
    if "date_of_birth" in changes:
        validate_professional_date_of_birth(changes["date_of_birth"])  # type: ignore[arg-type]
        profile.date_of_birth = changes["date_of_birth"]  # type: ignore[assignment]
    if "specialty_code" in changes:
        profile.specialty = _replacement_specialty(
            str(changes["specialty_code"]), profile.specialty_id
        )
    if "hospital_service_code" in changes:
        profile.hospital_service = _replacement_hospital_service(
            str(changes["hospital_service_code"]), profile.hospital_service_id
        )
    if "license_number" in changes:
        profile.license_number = normalize_license_number(changes["license_number"])
    profile.full_clean()
    profile.save()
    return profile


@transaction.atomic
def deactivate_professional(
    *, actor: ActorContext | None, professional: Professional, confirmed: bool
) -> Professional:
    _actor(actor)
    if not confirmed:
        raise ConfirmationRequiredError(
            "Professional deactivation requires confirmation."
        )
    profile = Professional.objects.select_for_update().get(pk=professional.pk)
    if profile.is_active:
        profile.is_active = False
        profile.save(update_fields=["is_active"])
    return profile


@transaction.atomic
def reactivate_professional(
    *, actor: ActorContext | None, professional: Professional, confirmed: bool
) -> Professional:
    _actor(actor)
    if not confirmed:
        raise ConfirmationRequiredError(
            "Professional reactivation requires confirmation."
        )
    profile = (
        Professional.objects.select_for_update(of=("self",))
        .select_related("user", "specialty", "hospital_service")
        .get(pk=professional.pk)
    )
    if not profile.is_registration_complete or not profile.user.is_active:
        raise ValidationError(
            {"__all__": "Profile and account must be eligible for reactivation."}
        )
    validate_active_reference(profile.specialty, field_name="specialty")
    validate_active_reference(profile.hospital_service, field_name="hospital service")
    if (
        Professional.objects.filter(dni=profile.dni, is_active=True)
        .exclude(pk=profile.pk)
        .exists()
    ):
        raise ProfessionalConflictError("An active professional already has this DNI.")
    profile.is_active = True
    try:
        # The inner savepoint keeps the outer lifecycle transaction usable when
        # a competing reactivation wins the partial unique-index race.
        with transaction.atomic():
            profile.save(update_fields=["is_active"])
    except IntegrityError as error:
        if _is_active_dni_constraint(error):
            raise ProfessionalConflictError(
                "An active professional already has this DNI."
            ) from error
        raise
    return profile
