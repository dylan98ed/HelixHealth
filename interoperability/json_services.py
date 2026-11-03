"""Atomic FHIR JSON import after complete offline profile validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError, transaction

from access_control.actors import ActorContext
from clinical_records.services import active_professional_for_actor
from interoperability.clinical_requests import (
    ImportedRequestConflict,
    save_imported_medication_request,
    save_imported_service_request,
)
from interoperability.identity import (
    ExternalIdentityConflict,
    resolve_imported_patient,
    resolve_imported_professional,
)
from interoperability.json_importing import JsonImportError, parse_json_bundle
from interoperability.models import ExternalClinicalRecord, JsonImportBatch
from patients.models import Patient
from professionals.models import Professional


class JsonImportConflict(ValueError):
    """A request key or source resource was reused with conflicting content."""


@dataclass(frozen=True)
class JsonImportResult:
    batch: JsonImportBatch
    created: bool


def _save_observation(
    *, resource: dict, source: str, patient: Patient, practitioner: Professional
) -> bool:
    digest = hashlib.sha256(
        json.dumps(resource, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    from datetime import datetime

    recorded_at = datetime.fromisoformat(resource["effectiveDateTime"].replace("Z", "+00:00"))
    record, created = ExternalClinicalRecord.objects.get_or_create(
        source_system=source,
        resource_type="Observation",
        external_identifier=resource["id"],
        defaults={
            "patient": patient,
            "kind": ExternalClinicalRecord.KIND_OBSERVATION,
            "source_recorded_at": recorded_at,
            "external_author": {"professional_id": practitioner.pk, "dni": practitioner.dni},
            "content": resource,
            "content_digest": digest,
        },
    )
    if not created and (record.patient_id != patient.pk or record.content_digest != digest):
        raise JsonImportConflict("Observation identifier already has different content or patient.")
    return created


def import_json_bundle(
    *, actor: ActorContext | None, source_system: str, request_key: UUID,
    raw_json: bytes,
) -> JsonImportResult:
    """Validate first, then reconcile identities and persist everything atomically."""
    submitter = active_professional_for_actor(actor)
    source = source_system.strip().rstrip("/")
    try:
        URLValidator()(source)
    except ValidationError as error:
        raise JsonImportError("A valid source system URL is required.") from error
    parsed = parse_json_bundle(raw_json)
    digest = hashlib.sha256(raw_json).hexdigest()
    try:
        with transaction.atomic():
            Professional.objects.select_for_update().get(pk=submitter.pk)
            active_professional_for_actor(actor)
            replay = JsonImportBatch.objects.filter(
                submitted_by=submitter, request_key=request_key
            ).first()
            if replay is not None:
                if replay.source_system == source and replay.input_digest == digest:
                    return JsonImportResult(replay, False)
                raise JsonImportConflict("This request key was already used with different content.")
            replay = JsonImportBatch.objects.filter(
                source_system=source, input_digest=digest
            ).first()
            if replay is not None:
                return JsonImportResult(replay, False)

            patient, patient_created = resolve_imported_patient(
                dni=parsed.patient_dni,
                first_name=parsed.patient_first_name,
                last_name=parsed.patient_last_name,
                date_of_birth=parsed.patient_birth_date,
                gender=parsed.patient_gender,
            )
            practitioner, practitioner_created = resolve_imported_professional(
                dni=parsed.practitioner_dni,
                first_name=parsed.practitioner_first_name,
                last_name=parsed.practitioner_last_name,
                license_number=parsed.practitioner_license,
            )
            new_services = 0
            new_medications = 0
            new_observations = 0
            for resource in parsed.service_requests:
                _, created = save_imported_service_request(
                    resource=resource, source_system=source,
                    patient=patient, requester=practitioner,
                )
                new_services += created
            for resource in parsed.medication_requests:
                _, created = save_imported_medication_request(
                    resource=resource, source_system=source,
                    patient=patient, requester=practitioner,
                )
                new_medications += created
            for resource in parsed.observations:
                new_observations += _save_observation(
                    resource=resource, source=source,
                    patient=patient, practitioner=practitioner,
                )
            summary = {
                "patient": {"dni": patient.dni, "created": patient_created,
                            "is_active": patient.is_active, "is_external": patient.is_external},
                "practitioner": {"dni": practitioner.dni, "created": practitioner_created,
                                 "is_active": practitioner.is_active,
                                 "is_external": practitioner.is_external},
                "service_request_count": len(parsed.service_requests),
                "new_service_request_count": new_services,
                "medication_request_count": len(parsed.medication_requests),
                "new_medication_request_count": new_medications,
                "observation_count": len(parsed.observations),
                "new_observation_count": new_observations,
            }
            batch = JsonImportBatch.objects.create(
                patient=patient, practitioner=practitioner, submitted_by=submitter,
                source_system=source, bundle_identifier=parsed.bundle_identifier,
                request_key=request_key, input_digest=digest,
                raw_json=raw_json, summary=summary,
            )
            return JsonImportResult(batch, True)
    except (ExternalIdentityConflict, ImportedRequestConflict) as error:
        raise JsonImportConflict(str(error)) from error
    except ValidationError as error:
        raise JsonImportError("; ".join(error.messages)) from error
    except IntegrityError as error:
        replay = JsonImportBatch.objects.filter(source_system=source, input_digest=digest).first()
        if replay is not None:
            return JsonImportResult(replay, False)
        raise JsonImportConflict("Concurrent import conflicts with existing clinical data.") from error
