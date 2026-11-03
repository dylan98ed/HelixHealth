"""Offline validation of the documented FHIR R4 JSON exchange profile."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

from django.core.exceptions import ValidationError
from fhir.resources.bundle import Bundle  # type: ignore[import-untyped]
from pydantic import ValidationError as PydanticValidationError

from interoperability.clinical_requests import (
    validate_medication_request_resource,
    validate_service_request_resource,
)
from interoperability.fhir_validation import VITAL_CODES, VITAL_UNITS
from interoperability.limits import MAX_BUNDLE_BYTES, MAX_BUNDLE_ENTRIES

MAX_JSON_DEPTH = 64
UCUM_SYSTEM = "http://unitsofmeasure.org"
LOINC_SYSTEM = "http://loinc.org"
ALLOWED_TYPES = {"Patient", "Practitioner", "ServiceRequest", "MedicationRequest", "Observation", "Organization"}


class JsonImportError(ValueError):
    """The supplied JSON is invalid or outside the local exchange profile."""


@dataclass(frozen=True)
class ParsedJsonBundle:
    bundle_identifier: str
    patient: dict[str, Any]
    practitioner: dict[str, Any]
    patient_dni: str
    patient_first_name: str
    patient_last_name: str
    patient_birth_date: date
    patient_gender: str
    practitioner_dni: str
    practitioner_first_name: str
    practitioner_last_name: str
    practitioner_license: str
    service_requests: tuple[dict[str, Any], ...]
    medication_requests: tuple[dict[str, Any], ...]
    observations: tuple[dict[str, Any], ...]


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise JsonImportError(f"Duplicate JSON key: {key}.")
        result[key] = value
    return result


def _depth(value: Any) -> int:
    pending = [(value, 1)]
    maximum = 0
    while pending:
        item, depth = pending.pop()
        maximum = max(maximum, depth)
        if maximum > MAX_JSON_DEPTH:
            break
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
    return maximum


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise JsonImportError(f"{label} is required.")
    return value.strip()


def _timestamp(value: Any, label: str) -> datetime:
    text = _text(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise JsonImportError(f"{label} must be a zoned date-time.") from error
    if parsed.tzinfo is None:
        raise JsonImportError(f"{label} must include a timezone.")
    return parsed


def _dni(resource: dict[str, Any], label: str) -> str:
    identifiers = resource.get("identifier")
    if not isinstance(identifiers, list):
        raise JsonImportError(f"{label}.identifier must contain one DNI.")
    values = [
        item.get("value") for item in identifiers
        if isinstance(item, dict) and isinstance(item.get("value"), str)
        and re.fullmatch(r"[0-9]{7,8}", item["value"])
    ]
    if len(values) != 1:
        raise JsonImportError(f"{label} must contain exactly one DNI.")
    return str(values[0])


def _name(resource: dict[str, Any], label: str) -> tuple[str, str]:
    names = resource.get("name")
    if not isinstance(names, list) or not names or not isinstance(names[0], dict):
        raise JsonImportError(f"{label}.name is required.")
    family = _text(names[0].get("family"), f"{label}.name.family")
    given = names[0].get("given")
    if not isinstance(given, list) or not given:
        raise JsonImportError(f"{label}.name.given is required.")
    return _text(given[0], f"{label}.name.given"), family


def _license(practitioner: dict[str, Any]) -> str:
    qualifications = practitioner.get("qualification") or []
    if not isinstance(qualifications, list):
        raise JsonImportError("Practitioner.qualification must be a list.")
    values = [
        identifier.get("value")
        for qualification in qualifications if isinstance(qualification, dict)
        for identifier in (qualification.get("identifier") or [])
        if isinstance(identifier, dict) and isinstance(identifier.get("value"), str)
        and identifier["value"].strip()
    ]
    if len(values) != 1:
        raise JsonImportError("Practitioner must contain exactly one license identifier.")
    return str(values[0]).strip()


def _observation(resource: dict[str, Any]) -> None:
    if resource.get("status") != "final":
        raise JsonImportError("Observation.status must be final.")
    coding = (resource.get("code") or {}).get("coding") or []
    if len(coding) != 1 or coding[0].get("system") != LOINC_SYSTEM:
        raise JsonImportError("Observation requires one LOINC code.")
    code = coding[0].get("code")
    if code not in VITAL_CODES:
        raise JsonImportError("Unsupported Observation vital-sign code.")
    _timestamp(resource.get("effectiveDateTime"), "Observation.effectiveDateTime")
    if code == "85354-9":
        components = resource.get("component") or []
        if sorted((item.get("code") or {}).get("coding", [{}])[0].get("code") for item in components) != sorted(VITAL_CODES[code]):
            raise JsonImportError("Blood pressure requires systolic and diastolic components.")
        quantities = [item.get("valueQuantity") for item in components]
    else:
        if resource.get("component"):
            raise JsonImportError("This Observation cannot contain components.")
        quantities = [resource.get("valueQuantity")]
    for quantity in quantities:
        if not isinstance(quantity, dict) or quantity.get("value") is None:
            raise JsonImportError("Observation requires a valueQuantity.")
        if quantity.get("system") != UCUM_SYSTEM or quantity.get("code") != VITAL_UNITS[code]:
            raise JsonImportError("Observation requires the documented UCUM unit.")


def parse_json_bundle(raw: bytes) -> ParsedJsonBundle:
    """Validate bytes, R4 structure, identities, references and supported content."""
    if not raw or len(raw) > MAX_BUNDLE_BYTES:
        raise JsonImportError("FHIR JSON files must be between 1 byte and 2 MiB.")
    try:
        bundle = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_object_no_duplicates)
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        if isinstance(error, JsonImportError):
            raise
        raise JsonImportError("FHIR JSON is malformed or too deeply nested.") from error
    if not isinstance(bundle, dict) or _depth(bundle) > MAX_JSON_DEPTH:
        raise JsonImportError(f"FHIR JSON nesting must not exceed {MAX_JSON_DEPTH}.")
    if bundle.get("resourceType") != "Bundle" or bundle.get("type") != "collection":
        raise JsonImportError("A FHIR collection Bundle is required.")
    entries = bundle.get("entry")
    if not isinstance(entries, list) or not entries or len(entries) > MAX_BUNDLE_ENTRIES:
        raise JsonImportError(f"Bundle must contain 1 to {MAX_BUNDLE_ENTRIES} entries.")
    try:
        Bundle.parse_obj(bundle)
    except (PydanticValidationError, ValueError) as error:
        raise JsonImportError("FHIR R4 structural validation failed.") from error
    identifier = bundle.get("identifier") or {}
    bundle_identifier = _text(identifier.get("value"), "Bundle.identifier.value")
    _text(identifier.get("system"), "Bundle.identifier.system")
    _timestamp(bundle.get("timestamp"), "Bundle.timestamp")

    by_type: dict[str, list[dict[str, Any]]] = {}
    references: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or any(key in entry for key in ("request", "search", "response")):
            raise JsonImportError("Bundle entries cannot contain request, search or response.")
        resource = entry.get("resource")
        if not isinstance(resource, dict) or resource.get("resourceType") not in ALLOWED_TYPES:
            raise JsonImportError("Bundle contains an unsupported resource type.")
        kind = resource["resourceType"]
        identifier_value = _text(resource.get("id"), f"{kind}.id")
        full_url = _text(entry.get("fullUrl"), "Bundle.entry.fullUrl")
        if not full_url.startswith("urn:uuid:"):
            raise JsonImportError("Bundle.entry.fullUrl must be urn:uuid.")
        try:
            UUID(full_url.removeprefix("urn:uuid:"))
        except ValueError as error:
            raise JsonImportError("Bundle.entry.fullUrl must contain a UUID.") from error
        for reference in (full_url, f"{kind}/{identifier_value}"):
            if reference in references:
                raise JsonImportError("Bundle entry identities must be unique.")
            references[reference] = resource
        by_type.setdefault(kind, []).append(resource)
    if len(by_type.get("Patient", [])) != 1 or len(by_type.get("Practitioner", [])) != 1:
        raise JsonImportError("Bundle requires exactly one Patient and Practitioner.")
    if not by_type.get("ServiceRequest") or not by_type.get("MedicationRequest"):
        raise JsonImportError("Bundle requires ServiceRequest and MedicationRequest.")
    if len(by_type.get("Organization", [])) > 1:
        raise JsonImportError("Bundle allows at most one Organization.")
    patient = by_type["Patient"][0]
    practitioner = by_type["Practitioner"][0]
    patient_dni = _dni(patient, "Patient")
    practitioner_dni = _dni(practitioner, "Practitioner")
    patient_first, patient_last = _name(patient, "Patient")
    practitioner_first, practitioner_last = _name(practitioner, "Practitioner")
    birth_date_text = _text(patient.get("birthDate"), "Patient.birthDate")
    try:
        birth_date = date.fromisoformat(birth_date_text)
    except ValueError as error:
        raise JsonImportError("Patient.birthDate must be a date.") from error
    gender = _text(patient.get("gender"), "Patient.gender")
    if gender not in {"male", "female", "other", "unknown"}:
        raise JsonImportError("Unsupported Patient.gender.")
    license_number = _license(practitioner)

    def target(resource: dict[str, Any], field: str, expected: dict[str, Any]) -> None:
        reference = (resource.get(field) or {}).get("reference")
        if not isinstance(reference, str) or references.get(reference) is not expected:
            raise JsonImportError(f"{resource['resourceType']}.{field} must reference the Bundle {expected['resourceType']}.")

    for resource in by_type.get("ServiceRequest", []):
        target(resource, "subject", patient)
        target(resource, "requester", practitioner)
        try:
            validate_service_request_resource(resource)
        except ValidationError as error:
            raise JsonImportError("Invalid ServiceRequest: " + "; ".join(error.messages)) from error
    for resource in by_type.get("MedicationRequest", []):
        target(resource, "subject", patient)
        target(resource, "requester", practitioner)
        try:
            validate_medication_request_resource(resource)
        except ValidationError as error:
            raise JsonImportError("Invalid MedicationRequest: " + "; ".join(error.messages)) from error
    for resource in by_type.get("Observation", []):
        target(resource, "subject", patient)
        if resource.get("performer"):
            for performer in resource["performer"]:
                target({"resourceType": "Observation", "performer": performer}, "performer", practitioner)
        _observation(resource)
    return ParsedJsonBundle(
        bundle_identifier=bundle_identifier,
        patient=patient, practitioner=practitioner,
        patient_dni=patient_dni, patient_first_name=patient_first,
        patient_last_name=patient_last, patient_birth_date=birth_date,
        patient_gender=gender, practitioner_dni=practitioner_dni,
        practitioner_first_name=practitioner_first,
        practitioner_last_name=practitioner_last,
        practitioner_license=license_number,
        service_requests=tuple(by_type.get("ServiceRequest", [])),
        medication_requests=tuple(by_type.get("MedicationRequest", [])),
        observations=tuple(by_type.get("Observation", [])),
    )
