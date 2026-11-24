import json
from datetime import datetime, time, timedelta
from typing import Any

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from access_control.actors import actor_context_from_user
from access_control.policies import ADMINISTRATIVE_POLICY
from appointments.availability import clinic_zone
from audit.models import ClinicalAuditEvent
from clinical_records.chart_access import chart_assignment
from clinical_records.models import HistoryRevision
from patients.models import Patient
from patients.validators import validate_patient_dni

SOURCE_NAMES = {
    "clinical_records.admission": "Admission",
    "clinical_records.consultation": "Consultation",
    "clinical_records.progressnote": "Progress note",
    "clinical_records.historyentry": "Personal or family history",
    "prescriptions.prescription": "Local prescription",
    "interoperability.externalclinicalrecord": "External clinical record",
    "interoperability.importedservicerequest": "Requested procedure",
    "interoperability.importedmedicationrequest": "Medication request",
}


class AuditFilters(forms.Form):
    dni = forms.CharField(
        label="Patient DNI", validators=[validate_patient_dni], required=False
    )
    date = forms.DateField(
        label="Event date",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    source = forms.ChoiceField(
        label="Record type",
        required=False,
        choices=[("", "All record types"), *SOURCE_NAMES.items()],
    )


def review_scope(
    request: HttpRequest, patient_pk: int | None, clinical: bool
) -> tuple[Patient | None, QuerySet[ClinicalAuditEvent]]:
    if not request.user.is_active or not request.user.has_perm(
        "clinical_records.review_chart_audit"
    ):
        raise PermissionDenied
    actor = actor_context_from_user(request.user)
    patient: Patient | None
    if clinical:
        assert patient_pk is not None
        patient = chart_assignment(actor, patient_pk).patient
    else:
        if not ADMINISTRATIVE_POLICY.allows(actor):
            raise PermissionDenied
        patient = (
            get_object_or_404(Patient.all_objects, pk=patient_pk)
            if patient_pk is not None
            else None
        )
    events = ClinicalAuditEvent.objects.select_related("patient", "actor")
    if patient is not None:
        events = events.filter(patient=patient)
    return patient, events


@never_cache
@login_required
@require_GET
def review(
    request: HttpRequest, patient_pk: int | None = None, clinical: bool = False
) -> HttpResponse:
    patient, events = review_scope(request, patient_pk, clinical)
    form = AuditFilters(request.GET)
    if clinical:
        del form.fields["dni"]
    valid = form.is_valid()
    if not valid:
        events = events.none()
    else:
        if dni := form.cleaned_data.get("dni"):
            events = events.filter(patient__dni=dni)
        if day := form.cleaned_data["date"]:
            start = datetime.combine(day, time.min, clinic_zone())
            events = events.filter(recorded_at__gte=start)
            if day != datetime.max.date():
                events = events.filter(recorded_at__lt=start + timedelta(days=1))
        if source := form.cleaned_data["source"]:
            events = events.filter(source_type=source)
    page = Paginator(events.order_by("-recorded_at", "-pk"), 20).get_page(
        request.GET.get("page")
    )
    return render(
        request,
        "audit/review.html",
        {
            "patient": patient,
            "form": form,
            "page": page,
            "clinical": clinical,
            "zone": str(clinic_zone()),
            "rows": [(e, SOURCE_NAMES.get(e.source_type, e.source_type)) for e in page],
        },
        status=200 if valid else 422,
    )


def evidence(event: ClinicalAuditEvent, values: dict[str, Any]) -> str:
    if not values:
        return "No value recorded"
    if event.source_type == "clinical_records.historyentry" and "revision_id" in values:
        revision = (
            HistoryRevision.objects.select_related("entry", "author")
            .filter(
                pk=values["revision_id"],
                entry_id=int(event.source_key),
                entry__patient_id=event.patient_id,
            )
            .first()
        )
        if revision:
            return "\n".join(
                filter(
                    None,
                    [
                        f"{revision.entry.get_category_display()} history · revision {revision.version}",
                        revision.relationship,
                        revision.description,
                        revision.author.display_name,
                        revision.recorded_at.isoformat(),
                    ],
                )
            )
    return json.dumps(values, indent=2, ensure_ascii=False)


@never_cache
@login_required
@require_GET
def detail(
    request: HttpRequest, patient_pk: int, event_pk: int, clinical: bool = False
) -> HttpResponse:
    patient, events = review_scope(request, patient_pk, clinical)
    event = get_object_or_404(events, pk=event_pk)
    return render(
        request,
        "audit/detail.html",
        {
            "patient": patient,
            "event": event,
            "clinical": clinical,
            "label": SOURCE_NAMES.get(event.source_type, event.source_type),
            "before": evidence(event, event.before),
            "after": evidence(event, event.after),
            "zone": str(clinic_zone()),
        },
    )
