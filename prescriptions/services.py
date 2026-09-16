"""Transactional issuance of immutable prescriptions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid5

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from access_control.actors import ActorContext
from catalogs.models import MedicationEntry, TerminologyEntry
from clinical_records.services import active_professional_for_actor
from interoperability.fhir_export import (
    CodingSnapshot,
    PatientSnapshot,
    PractitionerSnapshot,
    PrescriptionItemSnapshot,
    PrescriptionSnapshot,
    serialize_prescription_bundle,
)
from patients.models import Patient
from prescriptions.models import Prescription, PrescriptionItem
from professionals.models import Professional


class PrescriptionConflictError(ValueError):
    """A request key was already used for a different issuance."""


class PrescriptionInputError(ValidationError):
    """The requested prescription has invalid directions or references."""


@dataclass(frozen=True)
class IssuanceResult:
    prescription: Prescription
    created: bool


def _text(value: object, field: str, maximum: int) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise PrescriptionInputError({field: ["This field is required."]})
    if len(cleaned) > maximum:
        raise PrescriptionInputError(
            {field: [f"Ensure this value has at most {maximum} characters."]}
        )
    return cleaned


def _canonical_payload(reason_id: int | None, items: list[dict[str, Any]]) -> str:
    return json.dumps(
        {"reason_entry_id": reason_id, "items": items},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _snapshot(
    *,
    patient: Patient,
    professional: Professional,
    reason: TerminologyEntry | None,
    items: list[dict[str, Any]],
    issued_at: datetime,
) -> dict[str, Any]:
    return {
        "patient": {
            "identifier": patient.clinical_record_number,
            "dni": patient.dni,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth.isoformat(),
        },
        "prescriber": {
            "identifier": professional.registration_number,
            "dni": professional.dni,
            "first_name": professional.first_name,
            "last_name": professional.last_name,
            "license_number": professional.license_number,
            "registration_number": professional.registration_number,
        },
        "institution": {
            "system": str(settings.INTEROPERABILITY_INSTITUTION_SYSTEM),  # type: ignore[misc]
            "code": str(settings.INTEROPERABILITY_INSTITUTION_CODE),  # type: ignore[misc]
            "name": str(settings.INTEROPERABILITY_INSTITUTION_NAME),  # type: ignore[misc]
        },
        "reason": None
        if reason is None
        else {
            "system": reason.system,
            "version": reason.version,
            "code": reason.code,
            "display": reason.display,
        },
        "issued_at": issued_at.isoformat(),
        "items": items,
    }


def _fhir_snapshot(identifier: UUID, snapshot: dict[str, Any]) -> PrescriptionSnapshot:
    patient = snapshot["patient"]
    prescriber = snapshot["prescriber"]
    reason = snapshot["reason"]
    return PrescriptionSnapshot(
        identifier=identifier,
        patient=PatientSnapshot(
            identifier=patient["identifier"],
            dni=patient["dni"],
            first_name=patient["first_name"],
            last_name=patient["last_name"],
            date_of_birth=datetime.fromisoformat(patient["date_of_birth"]).date(),
        ),
        prescriber=PractitionerSnapshot(
            identifier=prescriber["identifier"],
            first_name=prescriber["first_name"],
            last_name=prescriber["last_name"],
            registration_number=prescriber["registration_number"],
        ),
        issued_at=datetime.fromisoformat(snapshot["issued_at"]),
        reason=None if reason is None else CodingSnapshot(**reason),
        items=tuple(
            PrescriptionItemSnapshot(
                identifier=item["identifier"],
                medication=CodingSnapshot(**item["medication"]),
                dose_value=Decimal(item["dose_value"]),
                dose_unit=item["dose_unit"],
                route=item["route"],
                frequency=item["frequency"],
                duration_days=item["duration_days"],
                instructions=item["instructions"],
            )
            for item in snapshot["items"]
        ),
    )


@transaction.atomic
def issue_prescription(
    *,
    actor: ActorContext | None,
    patient: Patient,
    request_key: UUID,
    reason_entry_id: int | None,
    items: list[dict[str, Any]],
) -> IssuanceResult:
    """Validate and save a complete issuance, or return its exact replay."""
    professional = active_professional_for_actor(actor)
    professional = Professional.objects.select_for_update().get(pk=professional.pk)
    locked_patient = (
        Patient.all_objects.select_for_update().filter(pk=patient.pk).first()
    )
    if locked_patient is None or not locked_patient.is_active:
        raise PrescriptionInputError(
            {"patient": ["Prescriptions require an active patient."]}
        )
    # Recheck after taking the locks so deactivation/role changes cannot race issuance.
    professional = active_professional_for_actor(actor)
    if not items or len(items) > 50:
        raise PrescriptionInputError(
            {"items": ["Provide between 1 and 50 medication items."]}
        )
    reason = None
    if reason_entry_id is not None:
        reason = TerminologyEntry.objects.filter(pk=reason_entry_id).first()
        if reason is None:
            raise PrescriptionInputError(
                {"reason_entry_id": ["Unknown nomenclature entry."]}
            )

    medication_ids: list[int] = []
    normalized_items: list[dict[str, Any]] = []
    errors: dict[str, list[str]] = {}
    for index, raw in enumerate(items):
        prefix = f"items.{index}"
        try:
            medication_id = int(raw.get("medication_id", 0))
            dose = Decimal(str(raw.get("dose_value", "")))
            if not dose.is_finite() or dose <= 0:
                raise ValueError
            duration = int(raw.get("duration_days", 0))
            if not 1 <= duration <= 365:
                raise ValueError
            medication_ids.append(medication_id)
            normalized_items.append(
                {
                    "medication_id": medication_id,
                    "dose_value": format(dose, "f"),
                    "dose_unit": _text(
                        raw.get("dose_unit"), f"{prefix}.dose_unit", 100
                    ),
                    "route": _text(raw.get("route"), f"{prefix}.route", 100),
                    "frequency": _text(
                        raw.get("frequency"), f"{prefix}.frequency", 500
                    ),
                    "duration_days": duration,
                    "instructions": str(raw.get("instructions") or "").strip(),
                }
            )
            if len(normalized_items[-1]["instructions"]) > 2000:
                errors[f"{prefix}.instructions"] = [
                    "Ensure this value has at most 2000 characters."
                ]
        except (ArithmeticError, TypeError, ValueError, PrescriptionInputError):
            errors[prefix] = [
                "Enter a known medication, positive dose, and duration from 1 to 365 days."
            ]
    if errors:
        raise PrescriptionInputError(errors)
    medications = {
        entry.pk: entry
        for entry in MedicationEntry.objects.filter(pk__in=medication_ids)
    }
    missing = sorted(set(medication_ids) - set(medications))
    if missing:
        raise PrescriptionInputError(
            {"items": ["One or more medications are unknown."]}
        )

    canonical = _canonical_payload(reason_entry_id, normalized_items)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    existing = Prescription.objects.filter(
        prescriber=professional, patient=locked_patient, request_key=request_key
    ).first()
    if existing is not None:
        if existing.input_digest != digest:
            raise PrescriptionConflictError(
                "This request key has already been used with different content."
            )
        return IssuanceResult(existing, False)

    identifier = Prescription._meta.get_field("identifier").get_default()
    snapshot_items: list[dict[str, Any]] = []
    for sequence, item in enumerate(normalized_items, start=1):
        medication = medications[item["medication_id"]]
        snapshot_items.append(
            {
                "identifier": str(uuid5(identifier, f"item-{sequence}")),
                "medication": {
                    "system": medication.system,
                    "version": medication.version,
                    "code": medication.code,
                    "display": medication.name,
                },
                **{key: value for key, value in item.items() if key != "medication_id"},
                "presentation": medication.presentation,
            }
        )
    issued_at = timezone.now()
    snapshot = _snapshot(
        patient=locked_patient,
        professional=professional,
        reason=reason,
        items=snapshot_items,
        issued_at=issued_at,
    )
    xml = serialize_prescription_bundle(_fhir_snapshot(identifier, snapshot))
    prescription = Prescription(
        identifier=identifier,
        patient=locked_patient,
        prescriber=professional,
        issued_at=issued_at,
        request_key=request_key,
        input_digest=digest,
        reason_entry=reason,
        snapshot=snapshot,
        fhir_xml=xml,
    )
    prescription.full_clean()
    try:
        with transaction.atomic():
            prescription.save(force_insert=True)
    except IntegrityError as error:
        existing = Prescription.objects.filter(
            prescriber=professional, patient=locked_patient, request_key=request_key
        ).first()
        if existing is not None and existing.input_digest == digest:
            return IssuanceResult(existing, False)
        raise PrescriptionConflictError(
            "This request key has already been used with different content."
        ) from error
    PrescriptionItem.objects.bulk_create(
        [
            PrescriptionItem(
                prescription=prescription,
                sequence=sequence,
                medication=medications[item["medication_id"]],
                snapshot=snapshot_items[sequence - 1],
                dose_value=Decimal(item["dose_value"]),
                dose_unit=item["dose_unit"],
                route=item["route"],
                frequency=item["frequency"],
                duration_days=item["duration_days"],
                instructions=item["instructions"],
            )
            for sequence, item in enumerate(normalized_items, start=1)
        ]
    )
    return IssuanceResult(prescription, True)
