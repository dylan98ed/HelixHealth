from uuid import uuid4

from django import forms
from django.core.exceptions import ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from access_control.actors import actor_context_from_user
from appointments.availability import clinic_zone
from clinical_records.chart_access import chart_assignment
from clinical_records.documentation import (
    DocumentationConflict,
    add_progress_note,
    save_consultation,
    save_history,
)
from clinical_records.models import HistoryEntry
from clinical_records.views import medical_professional_required


class SubmissionForm(forms.Form):
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid4)


class ConsultationForm(SubmissionForm):
    visited_at = forms.DateTimeField(
        label="Visit time",
        initial=timezone.now,
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
        ),
    )
    reason = forms.CharField(label="Consultation reason", widget=forms.Textarea)
    initial_evolution = forms.CharField(
        label="Initial evolution", widget=forms.Textarea
    )


class ProgressForm(SubmissionForm):
    text = forms.CharField(label="Progress note", widget=forms.Textarea)


class HistoryForm(SubmissionForm):
    expected_version = forms.IntegerField(
        min_value=0, initial=0, widget=forms.HiddenInput
    )
    relationship = forms.CharField(max_length=120, label="Family relationship")
    description = forms.CharField(widget=forms.Textarea)


@never_cache
@medical_professional_required
@require_http_methods(["GET", "POST"])
def new_consultation(request: HttpRequest, patient_pk: int) -> HttpResponse:
    actor = actor_context_from_user(request.user)
    patient = chart_assignment(actor, patient_pk).patient
    assert actor is not None
    with timezone.override(clinic_zone()):
        form = ConsultationForm(request.POST if request.method == "POST" else None)
        status = 200
        if request.method == "POST":
            status = 422
            if form.is_valid():
                try:
                    consultation = save_consultation(
                        actor=actor, patient_pk=patient_pk, **form.cleaned_data
                    )
                except DocumentationConflict as error:
                    form.add_error(None, error)
                    status = 409
                else:
                    return redirect(
                        "clinical_records:consultation", patient_pk, consultation.pk
                    )
        return render(
            request,
            "clinical_records/document_form.html",
            {
                "patient": patient,
                "form": form,
                "title": "Record consultation",
                "clinic_zone": str(clinic_zone()),
            },
            status=status,
        )


@never_cache
@medical_professional_required
@require_http_methods(["GET", "POST"])
def consultation_detail(
    request: HttpRequest, patient_pk: int, consultation_pk: int
) -> HttpResponse:
    actor = actor_context_from_user(request.user)
    patient = chart_assignment(actor, patient_pk).patient
    assert actor is not None
    consultation = get_object_or_404(
        patient.consultations.select_related("author"), pk=consultation_pk
    )
    form = ProgressForm(request.POST if request.method == "POST" else None)
    status = 200
    if request.method == "POST":
        status = 422
        if form.is_valid():
            try:
                add_progress_note(
                    actor=actor,
                    patient_pk=patient_pk,
                    consultation_pk=consultation_pk,
                    **form.cleaned_data,
                )
            except DocumentationConflict as error:
                form.add_error(None, error)
                status = 409
            else:
                return redirect(
                    "clinical_records:consultation", patient_pk, consultation_pk
                )
    with timezone.override(clinic_zone()):
        return render(
            request,
            "clinical_records/consultation.html",
            {
                "patient": patient,
                "consultation": consultation,
                "notes": consultation.notes.select_related("author"),
                "form": form,
                "clinic_zone": str(clinic_zone()),
            },
            status=status,
        )


@never_cache
@medical_professional_required
@require_http_methods(["GET", "POST"])
def history_form(
    request: HttpRequest, patient_pk: int, category: str, entry_pk: int | None = None
) -> HttpResponse:
    actor = actor_context_from_user(request.user)
    patient = chart_assignment(actor, patient_pk).patient
    assert actor is not None
    if category not in HistoryEntry.Category.values:
        raise Http404
    entry = (
        None
        if entry_pk is None
        else get_object_or_404(patient.history_entries, pk=entry_pk, category=category)
    )
    previous = entry.revisions.select_related("author").first() if entry else None
    initial = (
        {
            "expected_version": previous.version,
            "relationship": previous.relationship,
            "description": previous.description,
        }
        if previous
        else {}
    )
    form = HistoryForm(
        request.POST if request.method == "POST" else None, initial=initial
    )
    if category == HistoryEntry.Category.PERSONAL:
        del form.fields["relationship"]
    status = 200
    if request.method == "POST":
        status = 422
        if form.is_valid():
            values = {"relationship": "", **form.cleaned_data}
            try:
                save_history(
                    actor=actor,
                    patient_pk=patient_pk,
                    category=category,
                    entry_pk=entry_pk,
                    **values,
                )
            except ValidationError as error:
                form.add_error(None, error)
                if isinstance(error, DocumentationConflict):
                    status = 409
            else:
                return redirect("clinical_records:chart", patient_pk)
    title = f"{'Edit' if entry else 'Add'} {category} history"
    return render(
        request,
        "clinical_records/document_form.html",
        {
            "patient": patient,
            "form": form,
            "title": title,
            "prior_revisions": entry.revisions.select_related("author").filter(
                version__lt=previous.version
            )
            if entry
            and previous
            and request.user.has_perm("clinical_records.review_chart_audit")
            else (),
        },
        status=status,
    )
