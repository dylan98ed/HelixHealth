from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from appointments.availability import clinic_zone
from appointments.forms import (
    ConfirmForm,
    ContactForm,
    RequestForm,
    RequestReservationForm,
)
from appointments.models import Appointment, BookingRequest, ContactAttempt
from appointments.services import (
    BookingConflict,
    confirm_request,
    create_request,
    identity_dni,
    record_unanswered,
    require_reception,
    reserve,
)
from appointments.views import agenda_url, read_offer, render_slots
from professionals.models import Professional


@login_required
@require_GET
def inbox(request):
    require_reception(request.user)
    rows = BookingRequest.objects.select_related("patient").order_by(
        "-created_at", "-pk"
    )
    page = Paginator(rows, 30).get_page(request.GET.get("page"))
    return render(
        request, "appointments/inbox.html", {"page": page, "zone": clinic_zone().key}
    )


@login_required
@require_http_methods(["GET", "POST"])
def new_request(request):
    require_reception(request.user)
    form = RequestForm(
        request.POST if request.method == "POST" else None, initial={"token": uuid4()}
    )
    if form.is_valid():
        try:
            intake = create_request(user_id=request.user.pk, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(request, "Request recorded.")
            return redirect("appointments:request-detail", pk=intake.pk)
    return render(request, "appointments/new_request.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def request_detail(request, pk):
    require_reception(request.user)
    intake = get_object_or_404(
        BookingRequest.objects.select_related("patient", "created_by"), pk=pk
    )
    booking = (
        Appointment.objects.select_related("professional")
        .filter(request=intake)
        .first()
    )
    action = request.POST.get("action") if request.method == "POST" else None
    contact = ContactForm(
        request.POST if action == "unanswered" else None, initial={"token": uuid4()}
    )
    confirmation = ConfirmForm(
        request.POST if action == "confirm" else None,
        auto_id="confirm_%s",
        initial={"token": uuid4(), "version": booking.version if booking else None},
    )
    status = 200
    if request.method == "POST":
        if action not in ("unanswered", "confirm"):
            return HttpResponseBadRequest()
        form = confirmation if action == "confirm" else contact
        if form.is_valid():
            try:
                if action == "confirm":
                    confirm_request(
                        user_id=request.user.pk, request_id=pk, **form.cleaned_data
                    )
                else:
                    record_unanswered(
                        user_id=request.user.pk, request_id=pk, **form.cleaned_data
                    )
            except BookingConflict as exc:
                messages.error(request, " ".join(exc.messages))
                return redirect("appointments:request-detail", pk=pk)
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
                status = 422
            else:
                return redirect("appointments:request-detail", pk=pk)
    attempts = (
        ContactAttempt.objects.filter(request=intake)
        .select_related("operator")
        .order_by("recorded_at", "pk")
    )
    return render(
        request,
        "appointments/request_detail.html",
        {
            "intake": intake,
            "booking": booking,
            "agenda_url": agenda_url(booking) if booking else None,
            "attempts": attempts,
            "contact": contact,
            "confirmation": confirmation,
            "zone": clinic_zone().key,
        },
        status=status,
    )


@login_required
@require_GET
def request_slots(request, pk):
    require_reception(request.user)
    intake = get_object_or_404(BookingRequest.objects.select_related("patient"), pk=pk)
    if Appointment.objects.filter(request=intake).exists():
        return redirect("appointments:request-detail", pk=pk)
    return render_slots(request, request.GET, intake=intake)


@login_required
@require_http_methods(["GET", "POST"])
def request_choice(request, pk):
    require_reception(request.user)
    intake = get_object_or_404(BookingRequest.objects.select_related("patient"), pk=pk)
    slot, specialty, _, _ = read_offer(request.GET.get("offer", ""), intake)
    form = RequestReservationForm(
        request.POST if request.method == "POST" else None, initial={"token": uuid4()}
    )
    if form.is_valid():
        data = form.cleaned_data
        try:
            if identity_dni(data["dni"]) != intake.patient.dni:
                raise ValidationError("The DNI does not match the request patient.")
            reserve(
                user_id=request.user.pk,
                request_id=pk,
                slot=slot,
                dni=data["dni"],
                birth_date=data["birth_date"],
                specialty_id=specialty,
                confirmed=data["status"] == "confirmed",
                token=data["token"],
            )
        except BookingConflict as exc:
            if Appointment.objects.filter(request=intake).exists():
                messages.error(request, " ".join(exc.messages))
                return redirect("appointments:request-detail", pk=pk)
            return render_slots(
                request,
                {"day": slot.start.date(), "specialty": specialty},
                conflict=" ".join(exc.messages),
                intake=intake,
            )
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            return redirect("appointments:request-detail", pk=pk)
    return render(
        request,
        "appointments/request_choice.html",
        {
            "intake": intake,
            "slot": slot,
            "professional": get_object_or_404(Professional, pk=slot.professional_id),
            "form": form,
            "zone": clinic_zone().key,
        },
    )
