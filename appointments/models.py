import calendar
import uuid

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.db import models
from django.db.models import F, Q

from patients.models import Patient
from professionals.models import Professional


class WeeklyRule(models.Model):
    professional = models.ForeignKey(Professional, on_delete=models.PROTECT)
    weekday = models.PositiveSmallIntegerField()
    opens = models.TimeField()
    closes = models.TimeField()
    minutes = models.PositiveSmallIntegerField()
    effective_from = models.DateField()
    effective_until = models.DateField(null=True, blank=True)

    class Meta:
        permissions = [("manage_availability", "Can manage availability")]
        constraints = [
            models.CheckConstraint(
                condition=Q(weekday__lte=6, opens__lt=F("closes"), minutes__gt=0),
                name="weekly_window_valid",
            ),
            models.CheckConstraint(
                condition=Q(effective_until__gte=F("effective_from"))
                | Q(effective_until=None),
                name="weekly_dates_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.professional} · {self.weekday_name} {self.opens}–{self.closes}"

    @property
    def weekday_name(self) -> str:
        return calendar.day_name[self.weekday]


class ScheduleException(models.Model):
    professional = models.ForeignKey(Professional, on_delete=models.PROTECT)
    day = models.DateField()
    # An entirely empty window closes the day. Otherwise it replaces weekly hours.
    opens = models.TimeField(null=True, blank=True)
    closes = models.TimeField(null=True, blank=True)
    minutes = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["professional", "day"], name="one_exception_per_day"
            ),
            models.CheckConstraint(
                condition=Q(opens=None, closes=None, minutes=None)
                | Q(
                    opens__isnull=False,
                    closes__isnull=False,
                    minutes__isnull=False,
                    opens__lt=F("closes"),
                    minutes__gt=0,
                ),
                name="exception_window_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.professional} · {self.day}"


class AppointmentState(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    ATTENDED = "attended", "Attended"
    CANCELED = "canceled", "Canceled"
    ABSENT = "absent", "Absent"


class BookingRequest(models.Model):
    class Channel(models.TextChoices):
        PHONE = "phone", "Phone"
        WHATSAPP = "whatsapp", "WhatsApp"

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    contact = models.CharField(max_length=254)
    preference = models.TextField(blank=True)
    status = models.CharField(max_length=16, default="pending")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    token = models.UUIDField(null=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("created_by", "token"), name="unique_request_submission"
            )
        ]

    def __str__(self) -> str:
        return f"Request {self.pk} · {self.channel}"


class ContactAttempt(models.Model):
    class Outcome(models.TextChoices):
        UNANSWERED = "unanswered", "No answer"
        CONFIRMED = "confirmed", "Confirmed"

    request = models.ForeignKey(BookingRequest, on_delete=models.PROTECT)
    channel = models.CharField(max_length=16, choices=BookingRequest.Channel.choices)
    outcome = models.CharField(max_length=100, choices=Outcome.choices)
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(auto_now_add=True)
    token = models.UUIDField(null=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("request", "token"), name="unique_request_contact_submission"
            )
        ]

    def __str__(self) -> str:
        return f"{self.channel} · {self.outcome}"


class Appointment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT)
    professional = models.ForeignKey(Professional, on_delete=models.PROTECT)
    request = models.OneToOneField(
        BookingRequest, null=True, blank=True, on_delete=models.PROTECT
    )
    start = models.DateTimeField()
    end = models.DateTimeField()
    state = models.CharField(max_length=16, choices=AppointmentState.choices)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)
    schedule_revision = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("start", "pk")
        constraints = [
            models.CheckConstraint(
                condition=Q(start__lt=F("end")), name="appointment_positive_interval"
            ),
            models.CheckConstraint(
                condition=Q(state__in=AppointmentState.values),
                name="appointment_known_state",
            ),
            ExclusionConstraint(
                name="appointment_no_occupied_overlap",
                expressions=[
                    ("professional", RangeOperators.EQUAL),
                    (
                        models.Func(
                            "start",
                            "end",
                            function="TSTZRANGE",
                            output_field=DateTimeRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                condition=~Q(state=AppointmentState.CANCELED),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.professional} · {self.start} ({self.state})"


class AppointmentHistory(models.Model):
    appointment = models.ForeignKey(
        Appointment, on_delete=models.PROTECT, related_name="history"
    )
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operation = models.CharField(max_length=16)
    token = models.UUIDField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField()
    old_state = models.CharField(max_length=16, blank=True)
    new_state = models.CharField(max_length=16)
    old_professional = models.ForeignKey(
        Professional, null=True, on_delete=models.PROTECT, related_name="+"
    )
    new_professional = models.ForeignKey(
        Professional, on_delete=models.PROTECT, related_name="+"
    )
    old_start = models.DateTimeField(null=True)
    old_end = models.DateTimeField(null=True)
    new_start = models.DateTimeField()
    new_end = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["operator", "token"], name="unique_operator_submission"
            ),
            models.UniqueConstraint(
                fields=["appointment", "version"],
                name="unique_booking_history_revision",
            ),
        ]

    def __str__(self) -> str:
        return f"Appointment {self.appointment_id} · {self.operation} (v{self.version})"


class ReminderDelivery(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Scheduled"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        RETRY = "retry", "Temporary delivery failure"
        MISSING = "missing", "Valid email address needed"
        REJECTED = "rejected", "Email rejected"
        REVIEW = (
            "review",
            "Delivery uncertain — review mailbox before contacting patient",
        )
        OBSOLETE = "obsolete", "Superseded"

    appointment = models.ForeignKey(
        Appointment, related_name="reminders", on_delete=models.PROTECT
    )
    schedule_revision = models.PositiveIntegerField()
    message_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.QUEUED
    )
    attempts = models.PositiveIntegerField(default=0)
    attempted_at = models.DateTimeField(null=True)
    sent_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ["-schedule_revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["appointment", "schedule_revision"],
                name="unique_schedule_reminder",
            )
        ]

    def __str__(self) -> str:
        return f"Appointment {self.appointment_id}, schedule {self.schedule_revision}: {self.get_status_display()}"

    @property
    def mail_message_id(self) -> str:
        return f"<{self.message_id}@reminders.helixhealth>"
