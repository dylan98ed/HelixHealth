"""Dispatch confirmed-visit reminders through the configured Django mail transport."""

import logging
import smtplib
from datetime import datetime, timedelta

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from appointments.availability import clinic_zone
from appointments.models import Appointment, AppointmentState, ReminderDelivery
from patients.models import Patient

logger = logging.getLogger(__name__)
Status = ReminderDelivery.Status
READY = (Status.QUEUED, Status.RETRY, Status.MISSING)
WINDOW = timedelta(hours=24)


def _usable(address: str) -> bool:
    try:
        validate_email(address)
    except ValidationError:
        return False
    return True


def _eligible(visit: Appointment, revision: int, now: datetime) -> bool:
    return (
        visit.state == AppointmentState.CONFIRMED
        and visit.schedule_revision == revision
        and now < visit.start <= now + WINDOW
    )


@transaction.atomic
def _claim(delivery_id: int) -> bool:
    delivery = (
        ReminderDelivery.objects.select_for_update(skip_locked=True, of=("self",))
        .select_related("appointment__patient")
        .filter(pk=delivery_id, status__in=READY)
        .first()
    )
    now = timezone.now()
    if delivery is None or not _eligible(
        delivery.appointment, delivery.schedule_revision, now
    ):
        return False
    if not _usable(delivery.appointment.patient.email):
        if delivery.status != Status.MISSING:
            delivery.status = Status.MISSING
            delivery.save(update_fields=["status"])
        return False
    delivery.status = Status.SENDING
    delivery.attempted_at = now
    delivery.attempts += 1
    delivery.save(update_fields=["status", "attempted_at", "attempts"])
    return True


def _send(visit: Appointment, address: str, delivery: ReminderDelivery) -> Status:
    zone = clinic_zone()
    start = visit.start.astimezone(zone)
    message = mail.EmailMessage(
        subject="HelixHealth appointment reminder",
        body=f"Your appointment with {visit.professional} is on {start:%Y-%m-%d} at {start:%H:%M} ({zone.key}).",
        to=[address],
        headers={"Message-ID": delivery.mail_message_id},
    )
    transport = mail.get_connection(fail_silently=False)
    try:
        try:
            transport.open()
        except (OSError, ValueError):
            return Status.RETRY  # No message has been submitted.
        if not _eligible(visit, delivery.schedule_revision, timezone.now()):
            return Status.OBSOLETE
        try:
            accepted = transport.send_messages([message])
        except smtplib.SMTPRecipientsRefused as exc:
            # Each reminder has one envelope recipient.
            code, _ = next(iter(exc.recipients.values()))
            return Status.RETRY if 400 <= code < 500 else Status.REJECTED
        except smtplib.SMTPResponseException as exc:
            return Status.RETRY if 400 <= exc.smtp_code < 500 else Status.REJECTED
        except OSError:
            return Status.REVIEW  # The final SMTP acknowledgment may have been lost.
        return Status.SENT if accepted == 1 else Status.REVIEW
    finally:
        try:
            transport.close()
        except OSError:
            logger.warning(
                "Could not close the mail connection for reminder %s", delivery.pk
            )


@transaction.atomic
def _dispatch(delivery_id: int, visit_id: int, patient_id: int) -> None:
    # Use the booking writers' lock order through the SMTP acknowledgment.
    # The sending claim already committed, so a crash cannot cause an automatic resend.
    patient = Patient.all_objects.select_for_update().get(pk=patient_id)
    visit = (
        Appointment.objects.select_for_update(of=("self",))
        .select_related("professional")
        .get(pk=visit_id)
    )
    delivery = ReminderDelivery.objects.select_for_update().get(pk=delivery_id)
    if delivery.status != Status.SENDING:
        return
    if not _eligible(visit, delivery.schedule_revision, timezone.now()):
        delivery.status = Status.OBSOLETE
    elif not _usable(patient.email):
        delivery.status = Status.MISSING
    else:
        try:
            delivery.status = _send(visit, patient.email, delivery)
        except Exception:
            logger.exception(
                "Unexpected transport failure for reminder %s", delivery.pk
            )
            delivery.status = Status.REVIEW
        if delivery.status == Status.SENT:
            delivery.sent_at = timezone.now()
    delivery.save(update_fields=["status", "sent_at"])


def send_due_reminders() -> None:
    now = timezone.now()
    ReminderDelivery.objects.filter(
        status=Status.SENDING, attempted_at__lte=now - timedelta(minutes=5)
    ).update(status=Status.REVIEW)
    ReminderDelivery.objects.filter(
        status=Status.QUEUED, appointment__start__lte=now
    ).update(status=Status.OBSOLETE)
    due = ReminderDelivery.objects.filter(
        status__in=READY,
        appointment__state=AppointmentState.CONFIRMED,
        appointment__start__gt=now,
        appointment__start__lte=now + WINDOW,
    ).order_by("appointment__start", "pk")
    for delivery_id, visit_id, patient_id in due.values_list(
        "pk", "appointment_id", "appointment__patient_id"
    ).iterator():
        if _claim(delivery_id):
            _dispatch(delivery_id, visit_id, patient_id)
