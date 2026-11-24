from typing import Any

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.transaction import TransactionManagementError

from audit.models import ClinicalAuditEvent


def record_clinical_change(
    *,
    source: models.Model,
    operation: str,
    operation_key: str,
    actor_id: int | None = None,
    external_origin: str = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> ClinicalAuditEvent:
    """Append within the source writer's atomic block. Let failures roll back the write.

    Pass the saved patient-owned record and a key stable across retries of this
    change. Before/after contain changed fields or immutable revision references.
    """
    db = source._state.db
    if source._state.adding or db is None or source.pk is None:
        raise ValueError("The clinical source must already be saved.")
    if not transaction.get_connection(db).in_atomic_block:
        raise TransactionManagementError(
            "Record the clinical change inside the source transaction."
        )
    # Read ownership from the persisted source, including for inactive patients.
    patient_id = (
        type(source)
        ._base_manager.using(db)
        .values_list(
            getattr(type(source), "audit_patient_lookup", "patient_id"), flat=True
        )
        .get(pk=source.pk)
    )
    operation = operation.strip()
    operation_key = operation_key.strip()
    external_origin = external_origin.strip()
    if not operation or not operation_key:
        raise ValidationError("An operation and stable operation key are required.")
    if actor_id is None and not external_origin:
        raise ValidationError("A clinical change requires an actor or external origin.")
    if before is None:
        before = {}
    if after is None:
        after = {}
    if (
        not isinstance(before, dict)
        or not isinstance(after, dict)
        or not (before or after)
    ):
        raise ValidationError("Supply changed fields or immutable version references.")

    evidence = dict(
        patient_id=patient_id,
        operation=operation,
        actor_id=actor_id,
        external_origin=external_origin,
        before=before,
        after=after,
    )
    events = ClinicalAuditEvent.objects.using(db)
    event, created = events.get_or_create(
        source_type=source._meta.label_lower,
        source_key=str(source.pk),
        operation_key=operation_key,
        defaults=evidence,
    )
    # PostgreSQL compares the stored JSON, including encoded dates and decimals.
    if not created and not events.filter(pk=event.pk, **evidence).exists():
        raise ValidationError(
            "This source operation already has a different audit event."
        )
    return event
