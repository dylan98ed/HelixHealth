from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from heapq import merge
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
        for u in User.objects.select_for_update(no_key=True)
        .filter(Q(pk=user_id) | Q(pk__in=subject_ids))
        .order_by("pk")
    }
    user = accounts.get(user_id)
    if user is None or not user.is_active:
        raise PermissionDenied
    list(
        Professional.objects.select_for_update(no_key=True)
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


def _weekly_slots(rule, first, last, exceptions):
    day = max(first, rule.effective_from)
    # An undersized window never yields a slot, even if it recurs indefinitely.
    if not next(window_slots(day, rule), None):
        return
    first_ordinal = day.toordinal() + (rule.weekday - day.weekday()) % 7
    until = min(last, rule.effective_until or date.max)
    for ordinal in range(first_ordinal, until.toordinal() + 1, 7):
        day = date.fromordinal(ordinal)
        if (rule.professional_id, day) not in exceptions:
            yield from window_slots(day, rule)


def available_slots(first, professional_ids, *, through=None, ignore_booking=None):
    """Merge recurring and exceptional openings in clinic-time order."""
    now = timezone.now()
    first = max(first, now.astimezone(clinic_zone()).date())
    if through and through < first:
        return
    rules = WeeklyRule.objects.filter(
        Q(effective_until=None) | Q(effective_until__gte=first),
        professional_id__in=professional_ids,
    )
    overrides = ScheduleException.objects.filter(
        professional_id__in=professional_ids, day__gte=first
    )
    bookings = Appointment.objects.filter(
        professional_id__in=professional_ids, end__gt=now
    ).exclude(state=AppointmentState.CANCELED)
    if through:
        rules = rules.filter(effective_from__lte=through)
        overrides = overrides.filter(day__lte=through)
        bookings = bookings.filter(start__lt=day_bounds(through)[1])
    if ignore_booking is not None:
        bookings = bookings.exclude(pk=ignore_booking)
    occupied = defaultdict(list)
    for pid, start, end in bookings.values_list("professional_id", "start", "end"):
        occupied[pid].append((start, end))

    exceptions = {(ex.professional_id, ex.day): ex for ex in overrides}
    streams = [window_slots(ex.day, ex) for ex in exceptions.values()]
    streams.extend(
        _weekly_slots(rule, first, through or date.max, exceptions) for rule in rules
    )
    for slot in merge(*streams, key=lambda s: (s.start, s.professional_id)):
        if slot.start > now and not any(
            start < slot.end and end > slot.start
            for start, end in occupied[slot.professional_id]
        ):
            yield slot


def free_slots(
    day: date,
    professionals: Iterable[Professional],
    *,
    ignore_booking: int | None = None,
) -> list[Slot]:
    return list(
        available_slots(
            day,
            [p.pk for p in professionals],
            through=day,
            ignore_booking=ignore_booking,
        )
    )


def _lock_managed_schedule(user_id: int, professional_id: int) -> None:
    require_manager(lock_schedule(user_id, {professional_id}))
    if not eligible_professionals().filter(pk=professional_id).exists():
        raise ValidationError("Choose an eligible professional.")


def _save_weekly_rule(window: WeeklyRule) -> None:
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
        raise ValidationError(
            f"{window.weekday_name}: these hours overlap another effective rule."
        )
    window.full_clean()
    window.save()


@transaction.atomic
def add_weekly_rules(
    user_id: int,
    professional_id: int,
    weekdays: list[int],
    *,
    opens: time,
    closes: time,
    minutes: int,
    effective_from: date,
    effective_until: date | None,
) -> None:
    _lock_managed_schedule(user_id, professional_id)
    for weekday in sorted(set(weekdays)):
        _save_weekly_rule(
            WeeklyRule(
                professional_id=professional_id,
                weekday=weekday,
                opens=opens,
                closes=closes,
                minutes=minutes,
                effective_from=effective_from,
                effective_until=effective_until,
            )
        )


@transaction.atomic
def save_window(user_id: int, window: WeeklyRule | ScheduleException) -> None:
    _lock_managed_schedule(user_id, window.professional_id)
    if isinstance(window, WeeklyRule):
        _save_weekly_rule(window)
        return
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
    by_day: dict[date, list[Appointment]] = defaultdict(list)
    zone = clinic_zone()
    for booking in bookings:
        by_day[booking.start.astimezone(zone).date()].append(booking)
    if not by_day:
        return []

    exceptions = {
        window.day: window
        for window in ScheduleException.objects.filter(
            professional_id=professional_id, day__in=by_day.keys()
        )
    }
    by_weekday: dict[int, list[WeeklyRule]] = defaultdict(list)
    for rule in WeeklyRule.objects.filter(
        Q(effective_until=None) | Q(effective_until__gte=min(by_day)),
        professional_id=professional_id,
        effective_from__lte=max(by_day),
    ):
        by_weekday[rule.weekday].append(rule)

    outside: list[Appointment] = []
    for day, daily_bookings in by_day.items():
        if day in exceptions:
            slots = set(window_slots(day, exceptions[day]))
        else:
            slots = {
                slot
                for rule in by_weekday[day.weekday()]
                if rule.effective_from <= day
                and (rule.effective_until is None or day <= rule.effective_until)
                for slot in window_slots(day, rule)
            }
        outside.extend(
            booking
            for booking in daily_bookings
            if Slot(professional_id, booking.start, booking.end) not in slots
        )
    return outside
