"""Order patient-owned source keys in PostgreSQL, then load only the visible records."""

from collections import defaultdict
from datetime import date, datetime
from typing import Any

from django.core.paginator import Page, Paginator
from django.db.models import (
    Case,
    DateField,
    DateTimeField,
    Exists,
    Expression,
    F,
    OuterRef,
    QuerySet,
    Value,
    When,
)
from django.db.models.functions import Cast, TruncDate
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from appointments.availability import clinic_zone
from clinical_records.models import ProgressNote
from interoperability.models import ImportedMedicationRequest
from patients.models import Patient

# Fields on these sources reflect clinical time. received_at is ingestion metadata.
DATE_FIELDS = {
    "admission": "created_at",
    "consultation": "visited_at",
    "note": "recorded_at",
    "prescription": "issued_at",
    "external": "source_recorded_at",
    "procedure": "authored_on",
    "medication": "authored_on",
}


def sources(patient: Patient) -> dict[str, QuerySet]:
    return {
        "admission": patient.admissions.select_related("professional", "recorded_by"),
        "consultation": patient.consultations.select_related("author"),
        "note": ProgressNote.objects.filter(
            consultation__patient=patient
        ).select_related("author"),
        "prescription": patient.prescriptions.defer("fhir_xml").select_related(
            "prescriber"
        ),
        "external": patient.external_clinical_records.all(),
        "procedure": patient.imported_service_requests.select_related("requester"),
        "medication": patient.imported_medication_requests.select_related("requester"),
    }


def index_rows(kind: str, records: QuerySet) -> QuerySet:
    if kind == "external":
        # Deduplicate list entries only. An earlier source link remains valid after a later import.
        matching_order = ImportedMedicationRequest.objects.filter(
            patient_id=OuterRef("patient_id"),
            source_system=OuterRef("source_system"),
            external_identifier=OuterRef("external_identifier"),
        )
        records = records.exclude(
            Exists(matching_order), resource_type="MedicationRequest"
        )
    instant: Expression | F
    day: Expression
    field = DATE_FIELDS[kind]
    if field == "authored_on":
        # Validated FHIR orders retain either a zoned timestamp or a calendar date.
        instant = Case(
            When(authored_on__contains="T", then=Cast(field, DateTimeField())),
            output_field=DateTimeField(),
        )
        day = Case(
            When(
                authored_on__regex=r"^\d{4}-\d{2}-\d{2}$", then=Cast(field, DateField())
            ),
            default=TruncDate(instant, tzinfo=clinic_zone()),
        )
    else:
        instant = F(field)
        day = TruncDate(field, tzinfo=clinic_zone())
    return (
        records.order_by()
        .annotate(source_kind=Value(kind), clinical_day=day, clinical_instant=instant)
        .values_list("source_kind", "pk", "clinical_day", "clinical_instant")
    )


def chart_timeline(
    patient: Patient, number: str | None, *, page_size: int = 20
) -> Page:
    scoped = sources(patient)
    first, *others = [index_rows(kind, records) for kind, records in scoped.items()]
    ordered = first.union(*others, all=True).order_by(
        F("clinical_day").desc(nulls_last=True),
        F("clinical_instant").desc(nulls_last=True),
        "source_kind",
        "pk",
    )
    page = Paginator(ordered, page_size).get_page(number)
    keys = list(page.object_list)
    ids = defaultdict(list)
    for kind, pk, _, _ in keys:
        ids[kind].append(pk)
    records = {kind: scoped[kind].in_bulk(pks) for kind, pks in ids.items()}
    page.object_list = [
        summarize(patient.pk, kind, records[kind][pk]) for kind, pk, _, _ in keys
    ]
    return page


def clinical_date(value: datetime | str | None) -> str:
    if not value:
        return "Date unavailable"
    if isinstance(value, str):
        if len(value) == 10:
            return date.fromisoformat(value).isoformat()
        value = datetime.fromisoformat(value)
    return timezone.localtime(value, clinic_zone()).isoformat(sep=" ")


def observation_values(content: dict) -> list[tuple[str, str]]:
    # XML imports store normalized fields. JSON imports retain the FHIR resource.
    values = []
    for part in [content, *content.get("components", content.get("component", []))]:
        code: dict = part.get("coding") or next(
            iter(part.get("code", {}).get("coding", [])), {}
        )
        quantity = part.get("valueQuantity", part)
        if quantity.get("value") is not None:
            values.append(
                (
                    code.get("display") or code.get("code") or "Value",
                    f"{quantity['value']} {quantity.get('unit') or quantity.get('code') or ''}".strip(),
                )
            )
    return values


def summarize(patient_pk: int, kind: str, record: Any) -> dict[str, Any]:
    row = dict(
        kind=kind,
        pk=record.pk,
        date=clinical_date(getattr(record, DATE_FIELDS[kind])),
        provenance=getattr(record, "source_system", "HelixHealth"),
        received=getattr(record, "received_at", None),
        external_id=getattr(record, "external_identifier", ""),
        author="",
        recorder="",
        summary="",
        measurements=[],
        url=reverse(
            "clinical_records:timeline-source", args=[patient_pk, kind, record.pk]
        ),
    )
    if kind == "admission":
        row.update(
            label="Admission and vital signs",
            title=record.consultation_reason,
            author=record.professional.display_name if record.professional else "",
            recorder=record.recorded_by.username if record.recorded_by else "",
            summary=f"{record.systolic_blood_pressure}/{record.diastolic_blood_pressure} mmHg · {record.heart_rate} bpm · {record.temperature} °C",
            url=reverse(
                "clinical_records:chart-admission", args=[patient_pk, record.pk]
            ),
        )
    elif kind == "consultation":
        row.update(
            label="Consultation",
            title=record.reason,
            author=record.author.display_name,
            url=reverse("clinical_records:consultation", args=[patient_pk, record.pk]),
        )
    elif kind == "note":
        row.update(
            label="Progress note",
            title="Progress note",
            summary=record.text,
            author=record.author.display_name,
            url=reverse(
                "clinical_records:consultation",
                args=[patient_pk, record.consultation_id],
            )
            + f"#note-{record.pk}",
        )
    elif kind == "prescription":
        snapshot = record.snapshot
        name = snapshot.get("prescriber", {})
        row.update(
            label="Local prescription",
            title="Prescription",
            summary=", ".join(
                item["medication"]["display"] for item in snapshot.get("items", [])
            ),
            author=", ".join(
                filter(None, [name.get("last_name"), name.get("first_name")])
            )
            or record.prescriber.display_name,
        )
    elif kind == "procedure":
        row.update(
            label="Requested procedure · Práctica solicitada",
            title=record.description,
            author=record.requester.display_name,
        )
    elif kind == "medication":
        row.update(
            label="Medication request",
            title=record.medication_display,
            author=record.requester.display_name,
        )
    else:
        content, author = record.content, record.external_author
        row["author"] = (
            ", ".join(filter(None, [author.get("family"), author.get("given")]))
            or author.get("name")
            or author.get("identifier_value")
            or (f"DNI {author['dni']}" if author.get("dni") else "")
        )
        if record.kind == "observation":
            code: dict = content.get("coding") or next(
                iter(content.get("code", {}).get("coding", [])), {}
            )
            values = observation_values(content)
            row.update(
                label="Imported observation",
                title=code.get("display")
                or code.get("code")
                or record.external_identifier,
                summary=" · ".join(f"{name}: {quantity}" for name, quantity in values),
                measurements=values,
            )
        else:
            row.update(
                label="Medication request",
                title=content.get("medication", {}).get("display")
                or record.external_identifier,
                summary=content.get("directions", {}).get("text", ""),
            )
    return row


def timeline_source(patient: Patient, kind: str, pk: int) -> tuple[dict, Any]:
    scoped = sources(patient)
    if kind not in {"prescription", "external", "procedure", "medication"}:
        raise Http404
    record = get_object_or_404(scoped[kind], pk=pk)
    return summarize(patient.pk, kind, record), record
