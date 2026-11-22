"""Patient-scoped clinical documentation. All writes recheck the care team under lock."""

from datetime import datetime
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from access_control.actors import ActorContext
from audit.services import record_clinical_change
from clinical_records.chart_access import chart_assignment
from clinical_records.models import (
    Consultation,
    HistoryEntry,
    HistoryRevision,
    ProgressNote,
)


class DocumentationConflict(ValidationError):
    pass


def required_text(value: str) -> str:
    if not value.strip():
        raise ValidationError("Enter the required clinical text.")
    return value.strip()


@transaction.atomic
def save_consultation(
    *,
    actor: ActorContext,
    patient_pk: int,
    operation_key: UUID,
    visited_at: datetime,
    reason: str,
    initial_evolution: str,
) -> Consultation:
    team = chart_assignment(actor, patient_pk, for_update=True)
    reason, initial_evolution = required_text(reason), required_text(initial_evolution)
    if timezone.is_naive(visited_at):
        raise ValidationError("Visit time requires a time zone.")
    consultation, created = Consultation.objects.get_or_create(
        patient=team.patient,
        author=team.professional,
        operation_key=operation_key,
        defaults=dict(
            visited_at=visited_at, reason=reason, initial_evolution=initial_evolution
        ),
    )
    if not created:
        if (
            consultation.visited_at,
            consultation.reason,
            consultation.initial_evolution,
        ) != (visited_at, reason, initial_evolution):
            raise DocumentationConflict(
                "This submission already recorded a different consultation."
            )
        return consultation
    record_clinical_change(
        source=consultation,
        operation="create",
        operation_key=str(operation_key),
        actor_id=actor.user_id,
        after=dict(
            reason=reason,
            initial_evolution=initial_evolution,
            visited_at=visited_at.isoformat(),
            professional_id=team.professional_id,
        ),
    )
    return consultation


@transaction.atomic
def add_progress_note(
    *,
    actor: ActorContext,
    patient_pk: int,
    consultation_pk: int,
    operation_key: UUID,
    text: str,
) -> ProgressNote:
    team = chart_assignment(actor, patient_pk, for_update=True)
    consultation = team.patient.consultations.filter(pk=consultation_pk).first()
    if consultation is None:
        raise Http404
    text = required_text(text)
    note, created = ProgressNote.objects.get_or_create(
        consultation=consultation,
        author=team.professional,
        operation_key=operation_key,
        defaults={"text": text},
    )
    if not created:
        if note.text != text:
            raise DocumentationConflict(
                "This submission already recorded a different note."
            )
        return note
    record_clinical_change(
        source=note,
        operation="create",
        operation_key=str(operation_key),
        actor_id=actor.user_id,
        after=dict(
            text=text,
            consultation_id=consultation.pk,
            professional_id=team.professional_id,
            recorded_at=note.recorded_at.isoformat(),
        ),
    )
    return note


@transaction.atomic
def save_history(
    *,
    actor: ActorContext,
    patient_pk: int,
    category: str,
    description: str,
    relationship: str,
    operation_key: UUID,
    expected_version: int,
    entry_pk: int | None = None,
) -> HistoryEntry:
    team = chart_assignment(actor, patient_pk, for_update=True)
    description, relationship = required_text(description), relationship.strip()
    if category not in HistoryEntry.Category.values:
        raise ValidationError("Choose a valid history category.")
    if (category == HistoryEntry.Category.FAMILY) != bool(relationship) or len(
        relationship
    ) > 120:
        raise ValidationError("Supply a family relationship only for family history.")
    entry = None
    if entry_pk is not None:
        entry = team.patient.history_entries.filter(
            pk=entry_pk, category=category
        ).first()
        if entry is None:
            raise Http404
    replay = (
        HistoryRevision.objects.select_related("entry")
        .filter(author=team.professional, operation_key=operation_key)
        .first()
    )
    if replay:
        if (
            replay.entry.patient_id == patient_pk
            and replay.entry.category == category
            and entry_pk == (None if replay.version == 1 else replay.entry_id)
            and replay.version == expected_version + 1
            and replay.description == description
            and replay.relationship == relationship
        ):
            return replay.entry
        raise DocumentationConflict(
            "This submission already recorded a different history revision."
        )
    previous = entry.revisions.first() if entry else None
    current_version = previous.version if previous else 0
    if expected_version != current_version:
        raise DocumentationConflict(
            "This history has changed. Reopen the current entry before editing."
        )
    if entry is None:
        entry = HistoryEntry.objects.create(patient=team.patient, category=category)
    revision = HistoryRevision.objects.create(
        entry=entry,
        author=team.professional,
        operation_key=operation_key,
        version=current_version + 1,
        description=description,
        relationship=relationship,
    )
    record_clinical_change(
        source=entry,
        operation="revise" if previous else "create",
        operation_key=str(operation_key),
        actor_id=actor.user_id,
        before={"revision_id": previous.pk} if previous else {},
        after={"revision_id": revision.pk},
    )
    return entry
