"""Atomic persistence for validated external clinical exchange files."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID

from django.db import IntegrityError, transaction

from access_control.actors import ActorContext
from clinical_records.services import active_professional_for_actor
from interoperability.importing import (
    ExternalImportError,
    parse_external_bundle,
    patient_identity,
)
from interoperability.models import (
    ExternalClinicalRecord,
    ImportBatch,
    ImportBatchRecord,
)
from patients.models import Patient
from professionals.models import Professional


class ImportConflictError(ValueError):
    """A request key or stable external resource identity was reused differently."""


@dataclass(frozen=True)
class ImportResult:
    batch: ImportBatch
    created: bool


def _validate_patient_match(xml: bytes, patient: Patient) -> None:
    dni, birth_date = patient_identity(xml)
    if dni != patient.dni or birth_date != patient.date_of_birth.isoformat():
        raise ExternalImportError(
            "The Bundle Patient DNI and birth date must exactly match the selected patient."
        )


@transaction.atomic
def import_external_bundle(
    *,
    actor: ActorContext | None,
    patient: Patient,
    source_system: str,
    request_key: UUID,
    xml: bytes,
) -> ImportResult:
    """Validate all input first, then atomically retain external provenance only."""
    professional = active_professional_for_actor(actor)
    normalized_source = source_system.strip().rstrip("/")
    if not normalized_source:
        raise ExternalImportError("A source system is required.")
    parsed = parse_external_bundle(xml, source_system=normalized_source)
    _validate_patient_match(xml, patient)
    digest = hashlib.sha256(xml).hexdigest()

    professional = Professional.objects.select_for_update().get(pk=professional.pk)
    locked_patient = (
        Patient.all_objects.select_for_update().filter(pk=patient.pk).first()
    )
    if locked_patient is None or not locked_patient.is_active:
        raise ExternalImportError("Imports require an active patient.")
    active_professional_for_actor(actor)

    request_replay = ImportBatch.objects.filter(
        submitted_by=professional, patient=locked_patient, request_key=request_key
    ).first()
    if request_replay is not None:
        if (
            request_replay.input_digest == digest
            and request_replay.source_system == normalized_source
        ):
            return ImportResult(request_replay, False)
        raise ImportConflictError(
            "This request key has already been used with different content."
        )
    exact_replay = ImportBatch.objects.filter(
        patient=locked_patient, source_system=normalized_source, input_digest=digest
    ).first()
    if exact_replay is not None:
        return ImportResult(exact_replay, False)

    records: list[ExternalClinicalRecord] = []
    for parsed_record in parsed.records:
        existing = ExternalClinicalRecord.objects.filter(
            source_system=normalized_source,
            resource_type=parsed_record.resource_type,
            external_identifier=parsed_record.external_identifier,
        ).first()
        if existing is not None:
            if (
                existing.patient_id != locked_patient.pk
                or existing.content_digest != parsed_record.content_digest
            ):
                raise ImportConflictError(
                    "An external resource identifier is already associated with different content."
                )
            records.append(existing)
            continue
        records.append(
            ExternalClinicalRecord(
                patient=locked_patient,
                source_system=normalized_source,
                resource_type=parsed_record.resource_type,
                external_identifier=parsed_record.external_identifier,
                kind=parsed_record.kind,
                source_recorded_at=parsed_record.source_recorded_at,
                external_author=parsed_record.external_author,
                content=parsed_record.content,
                content_digest=parsed_record.content_digest,
            )
        )
    summary = {
        "record_count": len(records),
        "observation_count": sum(record.kind == "observation" for record in records),
        "medication_request_count": sum(
            record.kind == "medication-request" for record in records
        ),
    }
    try:
        with transaction.atomic():
            batch = ImportBatch.objects.create(
                patient=locked_patient,
                submitted_by=professional,
                source_system=normalized_source,
                bundle_identifier=parsed.bundle_identifier,
                input_digest=digest,
                request_key=request_key,
                raw_xml=xml,
                summary=summary,
            )
            for record in records:
                if record._state.adding:
                    record.full_clean()
                    record.save(force_insert=True)
                ImportBatchRecord.objects.create(batch=batch, record=record)
    except IntegrityError as error:
        replay = ImportBatch.objects.filter(
            patient=locked_patient, source_system=normalized_source, input_digest=digest
        ).first()
        if replay is not None:
            return ImportResult(replay, False)
        raise ImportConflictError(
            "The import conflicts with an existing external record."
        ) from error
    return ImportResult(batch, True)
