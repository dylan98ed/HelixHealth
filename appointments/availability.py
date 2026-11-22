from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from access_control.actors import actor_context_from_user
from access_control.policies import ADMINISTRATIVE_POLICY
from access_control.roles import MEDICAL_PROFESSIONAL_GROUP
from appointments.models import (
    Appointment,
    AppointmentState,
    ScheduleException,
    WeeklyRule,
)
from professionals.models import Professional


def clinic_zone() -> ZoneInfo:
    return ZoneInfo(
        getattr(settings, "SCHEDULING_TIME_ZONE", "America/Argentina/Buenos_Aires")
    )


def clinic_today() -> date:
    return timezone.localdate(timezone=clinic_zone())


def day_bounds(day: date) -> tuple[datetime, datetime]:
    midnight = datetime.combine(day, time.min, clinic_zone())
    return midnight, midnight + timedelta(days=1)


def eligible_professionals() -> QuerySet[Professional]:
    return Professional.objects.filter(
        is_active=True,
        registration_completed_at__isnull=False,
        user__is_active=True,
        user__groups__name=MEDICAL_PROFESSIONAL_GROUP,
        specialty__is_active=True,
        hospital_service__is_active=True,
    ).order_by("last_name", "first_name", "pk")


def require_manager(user: User) -> None:
    if not (
        user.is_active
        and ADMINISTRATIVE_POLICY.allows(actor_context_from_user(user))
        and user.has_perm("appointments.manage_availability")
    ):
        raise PermissionDenied


def lock_schedule(user_id: int, professional_ids: set[int]) -> User:
    """All schedule writers lock accounts first, then professionals, in PK order."""
    subject_ids = Professional.objects.filter(pk__in=professional_ids).values("user_id")
    accounts = {
        u.pk: u
        for u in User.objects.select_for_update()
        .filter(Q(pk=user_id) | Q(pk__in=subject_ids))
        .order_by("pk")
    }
    user = accounts.get(user_id)
    if user is None or not user.is_active:
        raise PermissionDenied
    list(
        Professional.objects.select_for_update()
        .filter(pk__in=professional_ids)
        .order_by("pk")
    )
    return user


@dataclass(frozen=True)
class Slot:
    professional_id: int
    start: datetime
    end: datetime


def window_slots(day: date, window: WeeklyRule | ScheduleException) -> Iterator[Slot]:
    if window.opens is None or window.closes is None or not window.minutes:
        return
    cursor = datetime.combine(day, window.opens, clinic_zone())
    closing = datetime.combine(day, window.closes, clinic_zone())
    duration = timedelta(minutes=window.minutes)
    while cursor + duration <= closing:
        yield Slot(window.professional_id, cursor, cursor + duration)
        cursor += duration


def schedule_slots(day: date, professional_ids: Iterable[int]) -> Iterator[Slot]:
    ids = list(professional_ids)
    exceptions = ScheduleException.objects.filter(day=day, professional_id__in=ids)
    replaced = set()
    for exception in exceptions:
        replaced.add(exception.professional_id)
        yield from window_slots(day, exception)
    rules = WeeklyRule.objects.filter(
        Q(effective_until=None) | Q(effective_until__gte=day),
        professional_id__in=set(ids) - replaced,
        effective_from__lte=day,
        weekday=day.weekday(),
    )
    for rule in rules:
        yield from window_slots(day, rule)


def free_slots(
    day: date,
    professionals: Iterable[Professional],
    *,
    ignore_booking: int | None = None,
) -> list[Slot]:
    ids = [p.pk for p in professionals]
    midnight, tomorrow = day_bounds(day)
    bookings = Appointment.objects.filter(
        professional_id__in=ids, start__lt=tomorrow, end__gt=midnight
    ).exclude(state=AppointmentState.CANCELED)
    if ignore_booking is not None:
        bookings = bookings.exclude(pk=ignore_booking)
    occupied = defaultdict(list)
    for pid, start, end in bookings.values_list("professional_id", "start", "end"):
        occupied[pid].append((start, end))
    now = timezone.now()
    return sorted(
        (
            slot
            for slot in schedule_slots(day, ids)
            if slot.start > now
            and not any(
                start < slot.end and end > slot.start
                for start, end in occupied[slot.professional_id]
            )
        ),
        key=lambda s: (s.start, s.professional_id),
    )


@transaction.atomic
def save_window(user_id: int, window: WeeklyRule | ScheduleException) -> None:
    require_manager(lock_schedule(user_id, {window.professional_id}))
    if not eligible_professionals().filter(pk=window.professional_id).exists():
        raise ValidationError("Choose an eligible professional.")
    if isinstance(window, WeeklyRule):
        if (
            window.pk
            and not WeeklyRule.objects.filter(
                pk=window.pk, professional_id=window.professional_id
            ).exists()
        ):
            raise ValidationError("Choose the original professional for this rule.")
        conflicts = WeeklyRule.objects.filter(
            Q(effective_until=None) | Q(effective_until__gte=window.effective_from),
            professional_id=window.professional_id,
            weekday=window.weekday,
            opens__lt=window.closes,
            closes__gt=window.opens,
        ).exclude(pk=window.pk)
        if window.effective_until:
            conflicts = conflicts.filter(effective_from__lte=window.effective_until)
        if conflicts.exists():
            raise ValidationError("These hours overlap another effective rule.")
    else:
        existing = ScheduleException.objects.filter(
            professional_id=window.professional_id, day=window.day
        ).first()
        if existing:
            existing.opens, existing.closes, existing.minutes = (
                window.opens,
                window.closes,
                window.minutes,
            )
            window = existing
    window.full_clean()
    window.save()


def affected_bookings(professional_id: int) -> list[Appointment]:
    bookings = (
        Appointment.objects.filter(
            professional_id=professional_id, start__gt=timezone.now()
        )
        .exclude(state=AppointmentState.CANCELED)
        .select_related("patient")
    )
    outside = []
    slots: set[Slot] = set()
    last_day = None
    for booking in bookings:
        day = booking.start.astimezone(clinic_zone()).date()
        if day != last_day:
            slots = set(schedule_slots(day, [professional_id]))
            last_day = day
        if Slot(professional_id, booking.start, booking.end) not in slots:
            outside.append(booking)
    return outside
