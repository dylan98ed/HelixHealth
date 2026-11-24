from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from access_control.actors import actor_context_from_user
from clinical_records.chart_access import chart_assignment, chart_assignments
from clinical_records.models import HistoryRevision
from clinical_records.timeline import chart_timeline, timeline_source
from clinical_records.views import medical_professional_required
from patients.directory import patient_directory_context
from patients.models import Patient


@never_cache
@medical_professional_required
@require_GET
def assigned_charts(request: HttpRequest) -> HttpResponse:
    assignments = chart_assignments(actor_context_from_user(request.user))
    patients = Patient.objects.filter(pk__in=assignments.values("patient_id"))
    context = patient_directory_context(request, patients)
    partial = (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-Target") == "patient-directory"
    )
    return render(
        request,
        "clinical_records/_assigned_patients.html"
        if partial
        else "clinical_records/assigned_charts.html",
        context,
    )


@never_cache
@medical_professional_required
@require_GET
def chart(request: HttpRequest, patient_pk: int) -> HttpResponse:
    patient = chart_assignment(
        actor_context_from_user(request.user), patient_pk
    ).patient
    return render(
        request,
        "clinical_records/chart.html",
        {
            "patient": patient,
            "timeline": chart_timeline(patient, request.GET.get("page")),
            "history_entries": patient.history_entries.order_by(
                "category", "pk"
            ).prefetch_related(
                Prefetch(
                    "revisions",
                    queryset=HistoryRevision.objects.select_related("author")[:1],
                    to_attr="current",
                )
            ),
        },
    )


@never_cache
@medical_professional_required
@require_GET
def chart_admission(
    request: HttpRequest, patient_pk: int, admission_pk: int
) -> HttpResponse:
    patient = chart_assignment(
        actor_context_from_user(request.user), patient_pk
    ).patient
    admission = get_object_or_404(
        patient.admissions.select_related("professional__user", "recorded_by"),
        pk=admission_pk,
    )
    return render(
        request,
        "clinical_records/chart_admission.html",
        {"patient": patient, "admission": admission},
    )


@never_cache
@medical_professional_required
@require_GET
def source_detail(
    request: HttpRequest, patient_pk: int, kind: str, pk: int
) -> HttpResponse:
    patient = chart_assignment(
        actor_context_from_user(request.user), patient_pk
    ).patient
    entry, record = timeline_source(patient, kind, pk)
    return render(
        request,
        "clinical_records/timeline_source.html",
        {"patient": patient, "entry": entry, "record": record},
    )
