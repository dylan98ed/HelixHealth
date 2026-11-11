"""Persist validated FHIR requests without creating local clinical events."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction

from interoperability.models import ImportedMedicationRequest, ImportedServiceRequest
from patients.models import Patient
from professionals.models import Professional


class ImportedRequestConflict(ValueError):
    """A stable FHIR identity was reused for different clinical content."""


def validate_service_request_resource(resource: dict[str, Any]) -> None:
    """Validate the fields persisted by the service, without touching the DB."""
    _identity(resource, "https://validation.example", "ServiceRequest")
    _shared(resource, medication=False)
    _coding(resource.get("code"), "code", required=True)


def validate_medication_request_resource(resource: dict[str, Any]) -> None:
    """Validate medication directions before an import transaction begins."""
    _identity(resource, "https://validation.example", "MedicationRequest")
    _shared(resource, medication=True)
    _coding(
        resource.get("medicationCodeableConcept"),
        "medicationCodeableConcept",
        required=False,
    )
    instructions = resource.get("dosageInstruction")
    if (
        not isinstance(instructions, list)
        or not instructions
        or not all(
            isinstance(item, dict)
            and isinstance(item.get("text"), str)
            and item["text"].strip()
            for item in instructions
        )
    ):
        raise ValidationError("dosageInstruction requires text directions.")
    dispense = resource.get("dispenseRequest") or {}
    if not isinstance(dispense, dict) or (
        dispense.get("quantity") is not None
        and not isinstance(dispense["quantity"], dict)
    ):
        raise ValidationError("dispenseRequest.quantity must be an object.")
    notes = resource.get("note") or []
    if not isinstance(notes, list) or not all(
        isinstance(note, dict) and isinstance(note.get("text"), str) for note in notes
    ):
        raise ValidationError("note must be a list of text annotations.")


def _required_text(value: Any, field: str, *, limit: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValidationError(
            f"{field} is required and must be at most {limit} characters."
        )
    return value.strip()


def _authored_on(value: Any) -> str:
    text = _required_text(value, "authoredOn", limit=32)
    try:
        if len(text) == 10:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) is None:
                raise ValueError("Invalid date syntax")
            date.fromisoformat(text)
        else:
            if re.match(r"\d{4}-\d{2}-\d{2}T", text) is None:
                raise ValueError("Invalid date-time syntax")
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("Time zone required")
    except ValueError as error:
        raise ValidationError(
            "authoredOn must be an ISO date or zoned date-time."
        ) from error
    return text


def _identity(
    resource: dict[str, Any], source_system: str, expected_type: str
) -> tuple[str, str, str]:
    if resource.get("resourceType") != expected_type:
        raise ValidationError(f"Expected a {expected_type} resource.")
    source = _required_text(source_system, "source_system").rstrip("/")
    URLValidator()(source)
    identifier = _required_text(resource.get("id"), "id", limit=64)
    if re.fullmatch(r"[A-Za-z0-9.\-]{1,64}", identifier) is None:
        raise ValidationError("id must be a FHIR resource id.")
    digest = hashlib.sha256(
        json.dumps(
            resource, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    return source, identifier, digest


def _coding(concept: Any, field: str, *, required: bool) -> tuple[str, str, str]:
    if not isinstance(concept, dict):
        raise ValidationError(f"{field} must be a CodeableConcept.")
    codings = concept.get("coding") or []
    coding = codings[0] if isinstance(codings, list) and codings else {}
    if not isinstance(coding, dict):
        raise ValidationError(f"{field}.coding is invalid.")
    system = coding.get("system") or ""
    code = coding.get("code") or ""
    if required:
        system = _required_text(system, f"{field}.coding.system")
        URLValidator()(system)
        code = _required_text(code, f"{field}.coding.code", limit=100)
    elif system:
        URLValidator()(system)
    elif code:
        raise ValidationError(f"{field}.coding.system is required with a code.")
    display = concept.get("text") or coding.get("display") or ""
    display = _required_text(display, f"{field}.text")
    return system, code, display


def _shared(resource: dict[str, Any], *, medication: bool) -> tuple[str, str, str]:
    status = _required_text(resource.get("status"), "status", limit=30)
    intent = _required_text(resource.get("intent"), "intent", limit=30)
    statuses = {
        "draft",
        "active",
        "on-hold",
        "completed",
        "entered-in-error",
        "unknown",
    } | ({"cancelled", "stopped"} if medication else {"revoked"})
    if status not in statuses:
        raise ValidationError("Unsupported request status.")
    if intent not in {
        "proposal",
        "plan",
        "directive",
        "order",
        "original-order",
        "reflex-order",
        "filler-order",
        "instance-order",
        "option",
    }:
        raise ValidationError("Unsupported request intent.")
    return status, intent, _authored_on(resource.get("authoredOn"))


def _save_request(
    model: type[ImportedServiceRequest] | type[ImportedMedicationRequest],
    *,
    source: str,
    identifier: str,
    digest: str,
    patient: Patient,
    requester: Professional,
    values: dict[str, Any],
) -> tuple[Any, bool]:
    record, created = model.objects.get_or_create(
        source_system=source,
        external_identifier=identifier,
        defaults={
            "patient": patient,
            "requester": requester,
            "content_digest": digest,
            **values,
        },
    )
    if not created and (
        record.patient_id != patient.pk
        or record.requester_id != requester.pk
        or record.content_digest != digest
    ):
        raise ImportedRequestConflict(
            "This external request identifier already has different content or people."
        )
    return record, created


@transaction.atomic
def save_imported_service_request(
    *,
    resource: dict[str, Any],
    source_system: str,
    patient: Patient,
    requester: Professional,
) -> tuple[ImportedServiceRequest, bool]:
    """Keep the request and its original date precision; do not record performance."""
    source, identifier, digest = _identity(resource, source_system, "ServiceRequest")
    status, intent, authored_on = _shared(resource, medication=False)
    code_system, code, description = _coding(
        resource.get("code"), "code", required=True
    )
    return _save_request(
        ImportedServiceRequest,
        source=source,
        identifier=identifier,
        digest=digest,
        patient=patient,
        requester=requester,
        values={
            "status": status,
            "intent": intent,
            "authored_on": authored_on,
            "code_system": code_system,
            "code": code,
            "description": description,
        },
    )


@transaction.atomic
def save_imported_medication_request(
    *,
    resource: dict[str, Any],
    source_system: str,
    patient: Patient,
    requester: Professional,
) -> tuple[ImportedMedicationRequest, bool]:
    """Keep medication directions without local catalog, issue, or XML invariants."""
    source, identifier, digest = _identity(resource, source_system, "MedicationRequest")
    status, intent, authored_on = _shared(resource, medication=True)
    system, code, display = _coding(
        resource.get("medicationCodeableConcept"),
        "medicationCodeableConcept",
        required=False,
    )
    instructions = resource.get("dosageInstruction")
    if (
        not isinstance(instructions, list)
        or not instructions
        or not all(isinstance(item, dict) for item in instructions)
    ):
        raise ValidationError("dosageInstruction must contain at least one direction.")
    if not all(
        isinstance(item.get("text"), str) and item["text"].strip()
        for item in instructions
    ):
        raise ValidationError("Each dosageInstruction requires text.")
    dispense = resource.get("dispenseRequest") or {}
    if not isinstance(dispense, dict):
        raise ValidationError("dispenseRequest must be an object.")
    quantity = dispense.get("quantity")
    if quantity is not None and not isinstance(quantity, dict):
        raise ValidationError("dispenseRequest.quantity must be an object.")
    notes = resource.get("note") or []
    if not isinstance(notes, list) or not all(
        isinstance(note, dict) and isinstance(note.get("text"), str) for note in notes
    ):
        raise ValidationError("note must be a list of text annotations.")
    return _save_request(
        ImportedMedicationRequest,
        source=source,
        identifier=identifier,
        digest=digest,
        patient=patient,
        requester=requester,
        values={
            "status": status,
            "intent": intent,
            "authored_on": authored_on,
            "medication_display": display,
            "medication_code_system": system,
            "medication_code": code,
            "dosage_instructions": instructions,
            "dispense_quantity": quantity,
            "notes": notes,
        },
    )
