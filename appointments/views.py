from datetime import datetime
from uuid import UUID, uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.forms.models import model_to_dict
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from appointments.availability import (
    Slot,
    add_weekly_rules,
    affected_bookings,
    available_slots,
    clinic_today,
    clinic_zone,
    day_bounds,
    eligible_professionals,
    require_manager,
    save_window,
)
from appointments.forms import (
    AddWeeklyForm,
    AgendaFilter,
    BookingActionForm,
    ConfirmForm,
    EditWeeklyForm,
    ExceptionForm,
    IdentityForm,
    ReservationForm,
    SlotFilter,
    WeeklyForm,
)
from appointments.models import (
    Appointment,
    AppointmentHistory,
    AppointmentState,
    ScheduleException,
    WeeklyRule,
)
from appointments.services import (
    BookingConflict,
    change_booking,
    identity_dni,
    record_attendance,
    require_reception,
    reserve,
)
from patients.models import Patient
from professionals.models import Professional


def agenda_url(booking):
    return reverse(
        "appointments:agenda",
        query={
            "day": booking.start.astimezone(clinic_zone()).date().isoformat(),
            "professional": booking.professional_id,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def availability(request):
    require_manager(request.user)
    people = eligible_professionals()
    professional = None
    rule = None
    rules = WeeklyRule.objects.none()
    exceptions = ScheduleException.objects.none()
    outside: list[Appointment] = []
    weekly: WeeklyForm = AddWeeklyForm(initial={"effective_from": clinic_today()})
    exception = ExceptionForm(prefix="exception")
    professional_id = request.GET.get("professional", "")
    if professional_id:
        if not professional_id.isdecimal():
            raise Http404
        professional = get_object_or_404(people, pk=professional_id)
        rules = WeeklyRule.objects.filter(professional=professional).order_by(
            "weekday", "effective_from", "opens"
        )
        exceptions = ScheduleException.objects.filter(
            professional=professional
        ).order_by("day")
        if rule_id := request.GET.get("rule"):
            if not rule_id.isdecimal():
                raise Http404
            rule = get_object_or_404(rules, pk=rule_id)
            weekly = EditWeeklyForm(initial=model_to_dict(rule))
    if request.method == "POST":
        if professional is None or request.POST.get("kind") not in (
            "weekly",
            "exception",
        ):
            return HttpResponseBadRequest()
        form: WeeklyForm | ExceptionForm
        if request.POST["kind"] == "weekly":
            form = weekly = (
                EditWeeklyForm(request.POST) if rule else AddWeeklyForm(request.POST)
            )
        else:
            form = exception = ExceptionForm(request.POST, prefix="exception")
        if form.is_valid():
            data = form.cleaned_data.copy()
            try:
                if isinstance(form, AddWeeklyForm):
                    add_weekly_rules(
                        request.user.pk, professional.pk, data.pop("weekday"), **data
                    )
                elif isinstance(form, EditWeeklyForm):
                    assert rule is not None
                    for field, value in data.items():
                        setattr(rule, field, value)
                    save_window(request.user.pk, rule)
                else:
                    data.pop("mode")
                    save_window(
                        request.user.pk,
                        ScheduleException(professional=professional, **data),
                    )
            except ValidationError as error:
                form.add_error(None, " ".join(error.messages))
            else:
                messages.success(request, "Availability saved.")
                return redirect(
                    reverse(
                        "appointments:availability",
                        query={"professional": professional.pk},
                    )
                )
    if professional:
        outside = affected_bookings(professional.pk)
    return render(
        request,
        "appointments/availability.html",
        {
            "people": people,
            "professional": professional,
            "rules": rules,
            "exceptions": exceptions,
            "weekly": weekly,
            "exception": exception,
            "editing": rule,
            "outside": outside,
            "zone": clinic_zone().key,
        },
    )


@login_required
@require_GET
def agenda(request):
    require_reception(request.user)
    form = AgendaFilter(request.GET or {"day": clinic_today()})
    bookings = []
    if form.is_valid():
        midnight, tomorrow = day_bounds(form.cleaned_data["day"])
        rows = (
            Appointment.objects.filter(start__gte=midnight, start__lt=tomorrow)
            .select_related("patient", "professional")
            .prefetch_related(
                "reminders",
                Prefetch(
                    "history",
                    queryset=AppointmentHistory.objects.filter(
                        new_state__in=[
                            AppointmentState.ATTENDED,
                            AppointmentState.ABSENT,
                            AppointmentState.CANCELED,
                        ]
                    ).select_related("operator"),
                    to_attr="final_events",
                ),
            )
        )
        if professional := form.cleaned_data["professional"]:
            rows = rows.filter(professional=professional)
        bookings = [(row, uuid4()) for row in rows]
    return render(
        request,
        "appointments/agenda.html",
        {
            "form": form,
            "bookings": bookings,
            "zone": clinic_zone().key,
            "now": timezone.now(),
        },
    )


def render_slots(request, params, moving=None, version=None, conflict="", intake=None):
    form = SlotFilter(
        params or None,
        initial={"specialty": moving.professional.specialty_id if moving else None},
    )
    choices = []
    next_offer = None
    if form.is_bound and form.is_valid():
        specialty = form.cleaned_data["specialty"]
        names = {p.pk: p for p in eligible_professionals().filter(specialty=specialty)}
        after = None
        first = clinic_today()
        if cursor := params.get("after"):
            previous, _, _, _ = read_offer(cursor, intake)
            after = (previous.start, previous.professional_id)
            first = previous.start.astimezone(clinic_zone()).date()
        for slot in available_slots(
            first, list(names), ignore_booking=moving.pk if moving else None
        ):
            if after and (slot.start, slot.professional_id) <= after:
                continue
            if moving and slot == Slot(
                moving.professional_id, moving.start, moving.end
            ):
                continue
            if len(choices) == 40:
                next_offer = choices[-1][2]
                break
            payload = [
                slot.professional_id,
                slot.start.isoformat(),
                slot.end.isoformat(),
                specialty.pk,
                moving.pk if moving else None,
                version,
            ]
            choices.append(
                (
                    names[slot.professional_id],
                    slot,
                    signing.dumps(payload, salt=offer_salt(intake)),
                )
            )
    return render(
        request,
        "appointments/slots.html",
        {
            "form": form,
            "choices": choices,
            "next_offer": next_offer,
            "moving": moving,
            "intake": intake,
            "version": version,
            "conflict": conflict,
        },
        status=409 if conflict else 200,
    )


@login_required
@require_GET
def slots(request, booking_id=None):
    require_reception(request.user)
    moving = get_object_or_404(Appointment, pk=booking_id) if booking_id else None
    version = request.GET.get("version", str(moving.version) if moving else "")
    if moving and (
        version != str(moving.version) or moving.state not in ("confirmed", "pending")
    ):
        messages.error(
            request, "The appointment has changed. Review its current details."
        )
        return redirect(agenda_url(moving))
    return render_slots(
        request,
        request.GET if "specialty" in request.GET else {},
        moving,
        int(version) if moving else None,
    )


def offer_salt(intake):
    return f"request-choice-{intake.pk}" if intake else "appointment-choice"


def read_offer(offer, intake=None):
    try:
        pid, start, end, specialty, booking_id, version = signing.loads(
            offer, salt=offer_salt(intake)
        )
    except signing.BadSignature as exc:
        raise Http404 from exc
    slot = Slot(pid, datetime.fromisoformat(start), datetime.fromisoformat(end))
    return slot, specialty, booking_id, version


@login_required
@require_http_methods(["GET", "POST"])
def choice(request):
    require_reception(request.user)
    offer = request.GET.get("offer", "")
    slot, specialty, booking_id, version = read_offer(offer)
    person = get_object_or_404(Professional, pk=slot.professional_id)
    moving = get_object_or_404(Appointment, pk=booking_id) if booking_id else None
    lookup = IdentityForm()
    reservation = None
    patient = None
    error = ""
    token = uuid4()
    if request.method == "POST":
        try:
            if moving:
                try:
                    submitted_token = UUID(request.POST.get("token", ""))
                except ValueError:
                    return HttpResponseBadRequest()
                booking = change_booking(
                    user_id=request.user.pk,
                    booking_id=moving.pk,
                    version=version,
                    token=submitted_token,
                    destination=slot,
                    specialty_id=specialty,
                )
                messages.success(request, "Appointment moved.")
                return redirect(agenda_url(booking))
            if "identity" in request.POST:
                reservation = ReservationForm(request.POST)
                try:
                    dni = signing.loads(request.POST["identity"], salt=offer)
                except signing.BadSignature:
                    return HttpResponseBadRequest()
                patient = Patient.objects.filter(dni=dni).first()
                if reservation.is_valid():
                    data = reservation.cleaned_data
                    booking = reserve(
                        user_id=request.user.pk,
                        slot=slot,
                        dni=dni,
                        birth_date=data["birth_date"],
                        confirmed=data["status"] == "confirmed",
                        token=data["token"],
                        specialty_id=specialty,
                    )
                    messages.success(request, "Appointment reserved.")
                    return redirect(agenda_url(booking))
            else:
                lookup = IdentityForm(request.POST)
                if lookup.is_valid():
                    dni = identity_dni(lookup.cleaned_data["dni"])
                    patient = Patient.objects.filter(dni=dni).first()
                    if patient is None:
                        raise ValidationError("No active patient matches this DNI.")
                    reservation = ReservationForm(
                        initial={
                            "identity": signing.dumps(dni, salt=offer),
                            "token": token,
                        }
                    )
        except BookingConflict as exc:
            if moving:
                moving.refresh_from_db()
                if moving.version != version:
                    messages.error(request, " ".join(exc.messages))
                    return redirect(agenda_url(moving))
            return render_slots(
                request,
                {"specialty": specialty},
                moving,
                moving.version if moving else None,
                " ".join(exc.messages),
            )
        except ValidationError as exc:
            error = " ".join(exc.messages)
    return render(
        request,
        "appointments/choice.html",
        {
            "person": person,
            "slot": slot,
            "lookup": lookup,
            "patient": patient,
            "reservation": reservation,
            "moving": moving,
            "error": error,
            "token": token,
            "zone": clinic_zone().key,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def arrival(request, booking_id):
    require_reception(request.user)
    booking = get_object_or_404(
        Appointment.objects.select_related("patient", "professional"), pk=booking_id
    )
    if request.method == "GET" and (
        booking.state not in (AppointmentState.PENDING, AppointmentState.CONFIRMED)
        or request.GET.get("version", str(booking.version)) != str(booking.version)
    ):
        return _agenda_conflict(request, booking)
    form = ConfirmForm(
        request.POST if request.method == "POST" else None,
        initial={"token": uuid4(), "version": booking.version},
    )
    if form.is_valid():
        try:
            booking = record_attendance(
                user_id=request.user.pk,
                booking_id=booking.pk,
                state=AppointmentState.ATTENDED,
                **form.cleaned_data,
            )
        except BookingConflict:
            return _agenda_conflict(request, booking)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(request, "Arrival recorded.")
            return redirect(agenda_url(booking))
    return render(
        request,
        "appointments/arrival.html",
        {
            "form": form,
            "booking": booking,
            "zone": clinic_zone().key,
            "agenda_url": agenda_url(booking),
        },
        status=422 if request.method == "POST" else 200,
    )


def _agenda_conflict(request, booking):
    booking.refresh_from_db()
    messages.error(
        request,
        f"The appointment has changed. Current status is {booking.get_state_display()}.",
    )
    return redirect(agenda_url(booking))


@login_required
@require_POST
def absence(request, booking_id):
    require_reception(request.user)
    booking = get_object_or_404(Appointment, pk=booking_id)
    form = BookingActionForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest()
    try:
        booking = record_attendance(
            user_id=request.user.pk,
            booking_id=booking_id,
            state=AppointmentState.ABSENT,
            **form.cleaned_data,
        )
    except BookingConflict:
        return _agenda_conflict(request, booking)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Absence recorded.")
    return redirect(agenda_url(booking))


@login_required
@require_POST
def cancel(request, booking_id):
    require_reception(request.user)
    booking = get_object_or_404(Appointment, pk=booking_id)
    form = BookingActionForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest()
    try:
        booking = change_booking(
            user_id=request.user.pk,
            booking_id=booking_id,
            **form.cleaned_data,
            destination=None,
        )
    except BookingConflict:
        return _agenda_conflict(request, booking)
    else:
        messages.success(request, "Appointment canceled.")
    return redirect(agenda_url(booking))
