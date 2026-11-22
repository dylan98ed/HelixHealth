from datetime import date
from uuid import UUID

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.actors import actor_context_from_user
from access_control.policies import RECEPTION_POLICY
from appointments.availability import (
    Slot,
    clinic_zone,
    eligible_professionals,
    free_slots,
    lock_schedule,
)
from appointments.models import (
    Appointment,
    AppointmentHistory,
    AppointmentState,
    BookingRequest,
    ContactAttempt,
    ReminderDelivery,
)
from patients.models import Patient
from patients.validators import validate_patient_dni


class BookingConflict(ValidationError):
    pass


def require_reception(user: User) -> None:
    if not user.is_active or not RECEPTION_POLICY.allows(actor_context_from_user(user)):
        raise PermissionDenied


def available_choice(
    slot: Slot, specialty_id: int | None, ignore_booking: int | None = None
) -> None:
    people = eligible_professionals().filter(pk=slot.professional_id)
    if specialty_id is not None:
        people = people.filter(specialty_id=specialty_id)
    if slot not in free_slots(
        slot.start.astimezone(clinic_zone()).date(),
        people,
        ignore_booking=ignore_booking,
    ):
        raise BookingConflict(
            "That opening is no longer available. Choose another slot."
        )


def identity_dni(value: str) -> str:
    dni = value.strip().replace(".", "").replace(" ", "")
    validate_patient_dni(dni)
    return dni


def snapshot(booking: Appointment) -> dict:
    return {
        "state": booking.state,
        "professional_id": booking.professional_id,
        "start": booking.start,
        "end": booking.end,
    }


def record(
    booking: Appointment, user_id: int, token: UUID, operation: str, previous: dict
) -> None:
    AppointmentHistory.objects.create(
        appointment=booking,
        operator_id=user_id,
        token=token,
        operation=operation,
        version=booking.version,
        **{f"old_{key}": value for key, value in previous.items()},
        **{f"new_{key}": value for key, value in snapshot(booking).items()},
    )
    if operation in ("move", "cancel", "arrival", "absence"):
        reminders = booking.reminders.all()
        status = ReminderDelivery.Status
        reminders.filter(
            status__in=[status.QUEUED, status.MISSING, status.RETRY, status.REJECTED]
        ).update(status=status.OBSOLETE)
    if booking.state == AppointmentState.CONFIRMED:
        ReminderDelivery.objects.create(
            appointment=booking, schedule_revision=booking.schedule_revision
        )


@transaction.atomic
def reserve(
    *,
    user_id: int,
    slot: Slot,
    dni: str,
    birth_date: date,
    confirmed: bool,
    token: UUID,
    request_id: int | None = None,
    specialty_id: int | None = None,
) -> Appointment:
    require_reception(lock_schedule(user_id, {slot.professional_id}))
    patient = (
        Patient.objects.select_for_update()
        .filter(dni=identity_dni(dni), date_of_birth=birth_date)
        .first()
    )
    if patient is None:
        raise ValidationError(
            "The DNI and date of birth do not match an active patient."
        )
    state = AppointmentState.CONFIRMED if confirmed else AppointmentState.PENDING
    prior = (
        AppointmentHistory.objects.filter(operator_id=user_id, token=token)
        .select_related("appointment")
        .first()
    )
    if prior:
        if (
            prior.operation == "reserve"
            and prior.appointment.patient_id == patient.pk
            and prior.new_state == state
            and prior.appointment.request_id == request_id
            and Slot(prior.new_professional_id, prior.new_start, prior.new_end) == slot
        ):
            return prior.appointment
        raise BookingConflict("This submission has already been used.")
    request = None
    if request_id is not None:
        request = (
            BookingRequest.objects.select_for_update()
            .filter(pk=request_id, patient=patient)
            .first()
        )
        if (
            request is None
            or request.status != "pending"
            or Appointment.objects.filter(request=request).exists()
        ):
            raise BookingConflict("This request cannot be booked again.")
    available_choice(slot, specialty_id)
    booking = Appointment.objects.create(
        professional_id=slot.professional_id,
        patient=patient,
        state=state,
        start=slot.start,
        end=slot.end,
        created_by_id=user_id,
        request_id=request_id,
    )
    record(booking, user_id, token, "reserve", {})
    if request is not None and confirmed:
        _record_request_confirmation(request, user_id, token)
    return booking


def _lock_booking(
    user_id: int, booking_id: int, destination: Slot | None = None
) -> tuple[Appointment, Patient]:
    original = Appointment.objects.get(pk=booking_id)
    people = {original.professional_id}
    if destination:
        people.add(destination.professional_id)
    require_reception(lock_schedule(user_id, people))
    patient = Patient.all_objects.select_for_update().get(pk=original.patient_id)
    booking = Appointment.objects.select_for_update().get(pk=booking_id)
    if booking.professional_id not in people:
        raise BookingConflict(
            "The appointment has changed. Review its current details."
        )
    return booking, patient


def _already_applied(
    booking: Appointment,
    user_id: int,
    version: int,
    token: UUID,
    operation: str,
    destination: Slot | None = None,
) -> bool:
    prior = AppointmentHistory.objects.filter(operator_id=user_id, token=token).first()
    if prior:
        if (
            prior.appointment_id == booking.pk
            and prior.operation == operation
            and prior.version == version + 1
            and (
                destination is None
                or destination
                == Slot(prior.new_professional_id, prior.new_start, prior.new_end)
            )
        ):
            return True
        raise BookingConflict("This submission has already been used.")
    if booking.version != version:
        raise BookingConflict(
            "The appointment has changed. Review its current details."
        )
    if booking.state not in (AppointmentState.PENDING, AppointmentState.CONFIRMED):
        raise BookingConflict("This appointment is already final.")
    return False


@transaction.atomic
def change_booking(
    *,
    user_id: int,
    booking_id: int,
    version: int,
    token: UUID,
    destination: Slot | None,
    specialty_id: int | None = None,
) -> Appointment:
    """Move to a named destination, or cancel when the destination is empty."""
    booking, patient = _lock_booking(user_id, booking_id, destination)
    operation = "move" if destination else "cancel"
    if _already_applied(booking, user_id, version, token, operation, destination):
        return booking
    previous = snapshot(booking)
    if destination:
        if not patient.is_active:
            raise ValidationError(
                "An active patient is required to move an appointment."
            )
        if destination == Slot(booking.professional_id, booking.start, booking.end):
            raise ValidationError("Choose a different opening.")
        available_choice(destination, specialty_id, ignore_booking=booking.pk)
        booking.professional_id = destination.professional_id
        booking.start, booking.end = destination.start, destination.end
        booking.schedule_revision += 1
    else:
        booking.state = AppointmentState.CANCELED
        if booking.request_id:
            BookingRequest.objects.filter(pk=booking.request_id).update(
                status="canceled"
            )
    booking.version += 1
    booking.save()
    record(booking, user_id, token, operation, previous)
    return booking


@transaction.atomic
def record_attendance(
    *,
    user_id: int,
    booking_id: int,
    version: int,
    token: UUID,
    state: AppointmentState,
    dni: str = "",
    birth_date: date | None = None,
) -> Appointment:
    booking, patient = _lock_booking(user_id, booking_id)
    if state == AppointmentState.ATTENDED:
        if (
            not patient.is_active
            or identity_dni(dni) != patient.dni
            or birth_date != patient.date_of_birth
        ):
            raise ValidationError(
                "The DNI and date of birth must match the active patient on this appointment."
            )
        operation = "arrival"
    elif state == AppointmentState.ABSENT:
        operation = "absence"
    else:
        raise ValidationError("Choose arrival or absence.")
    if _already_applied(booking, user_id, version, token, operation):
        return booking
    if state == AppointmentState.ABSENT and timezone.now() < booking.start:
        raise ValidationError("Absence can be recorded once the appointment starts.")
    previous = snapshot(booking)
    booking.state = state
    booking.version += 1
    booking.save(update_fields=["state", "version", "updated_at"])
    if booking.request_id:
        # A pending contact request no longer needs a confirmation after the visit closes.
        BookingRequest.objects.filter(pk=booking.request_id, status="pending").update(
            status="closed"
        )
    record(booking, user_id, token, operation, previous)
    return booking


@transaction.atomic
def create_request(
    *, user_id: int, dni: str, channel: str, contact: str, preference: str, token: UUID
) -> BookingRequest:
    require_reception(lock_schedule(user_id, set()))
    patient = Patient.objects.select_for_update().filter(dni=identity_dni(dni)).first()
    if patient is None:
        raise ValidationError("No active patient matches this DNI.")
    data = dict(
        patient=patient,
        channel=channel,
        contact=contact.strip(),
        preference=preference.strip(),
    )
    prior = BookingRequest.objects.filter(created_by_id=user_id, token=token).first()
    if prior:
        if all(getattr(prior, field) == value for field, value in data.items()):
            return prior
        raise BookingConflict("This submission has already been used.")
    intake = BookingRequest(created_by_id=user_id, token=token, **data)
    intake.full_clean()
    intake.save()
    return intake


@transaction.atomic
def record_unanswered(*, user_id: int, request_id: int, token: UUID) -> None:
    require_reception(lock_schedule(user_id, set()))
    intake = BookingRequest.objects.select_for_update().get(pk=request_id)
    prior = ContactAttempt.objects.filter(request=intake, token=token).first()
    if (
        prior
        and prior.operator_id == user_id
        and prior.outcome == ContactAttempt.Outcome.UNANSWERED
    ):
        return
    if prior or intake.status != "pending":
        raise BookingConflict("This request has changed. Review the contact history.")
    ContactAttempt.objects.create(
        request=intake,
        operator_id=user_id,
        channel=intake.channel,
        outcome=ContactAttempt.Outcome.UNANSWERED,
        token=token,
    )


def _record_request_confirmation(
    intake: BookingRequest, user_id: int, token: UUID
) -> None:
    if ContactAttempt.objects.filter(request=intake, token=token).exists():
        raise BookingConflict("This contact submission has already been used.")
    ContactAttempt.objects.create(
        request=intake,
        operator_id=user_id,
        channel=intake.channel,
        outcome=ContactAttempt.Outcome.CONFIRMED,
        token=token,
    )
    intake.status = "confirmed"
    intake.save(update_fields=["status"])


@transaction.atomic
def confirm_request(
    *,
    user_id: int,
    request_id: int,
    dni: str,
    birth_date: date,
    version: int,
    token: UUID,
) -> Appointment:
    original = Appointment.objects.filter(request_id=request_id).first()
    require_reception(
        lock_schedule(user_id, {original.professional_id} if original else set())
    )
    if original is None:
        raise BookingConflict("Choose and reserve an opening first.")
    patient = (
        Patient.objects.select_for_update()
        .filter(pk=original.patient_id, dni=identity_dni(dni), date_of_birth=birth_date)
        .first()
    )
    if patient is None:
        raise ValidationError(
            "The DNI and date of birth do not match the active request patient."
        )
    intake = BookingRequest.objects.select_for_update().get(
        pk=request_id, patient=patient
    )
    booking = Appointment.objects.select_for_update().get(request=intake)
    prior = AppointmentHistory.objects.filter(operator_id=user_id, token=token).first()
    if prior:
        if (
            prior.appointment_id == booking.pk
            and prior.operation == "confirm"
            and prior.version == version + 1
        ):
            return booking
        raise BookingConflict("This submission has already been used.")
    if (
        intake.status != "pending"
        or booking.state != AppointmentState.PENDING
        or booking.version != version
        or booking.professional_id != original.professional_id
        or booking.start <= timezone.now()
        or not eligible_professionals().filter(pk=booking.professional_id).exists()
    ):
        raise BookingConflict(
            "This reservation can no longer be confirmed as shown. Review the request."
        )
    previous = snapshot(booking)
    booking.state = AppointmentState.CONFIRMED
    booking.version += 1
    booking.save(update_fields=["state", "version", "updated_at"])
    record(booking, user_id, token, "confirm", previous)
    _record_request_confirmation(intake, user_id, token)
    return booking
