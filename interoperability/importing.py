"""Bounded, side-effect-free parsing of the documented external FHIR subset."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from lxml import etree  # type: ignore[import-untyped]

from interoperability.fhir_validation import (
    FHIR_NAMESPACE,
    FhirValidationError,
    validate_helixhealth_profile,
)
from interoperability.limits import MAX_BUNDLE_BYTES, MAX_BUNDLE_ENTRIES

NS = {"f": FHIR_NAMESPACE}
MAX_IMPORT_BYTES = MAX_BUNDLE_BYTES
MAX_IMPORT_ENTRIES = MAX_BUNDLE_ENTRIES
MAX_IMPORT_DEPTH = 64


class ExternalImportError(ValueError):
    """The supplied external file is outside the documented input contract."""


@dataclass(frozen=True)
class ParsedExternalRecord:
    resource_type: str
    external_identifier: str
    kind: str
    source_recorded_at: datetime
    external_author: dict[str, str]
    content: dict[str, object]

    @property
    def content_digest(self) -> str:
        """Hash every immutable value retained for one external record."""
        encoded = json.dumps(
            {
                "resource_type": self.resource_type,
                "kind": self.kind,
                "source_recorded_at": self.source_recorded_at.isoformat(),
                "external_author": self.external_author,
                "content": self.content,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ParsedBundle:
    bundle_identifier: str
    records: tuple[ParsedExternalRecord, ...]


def _primitive(element: etree._Element, path: str, label: str) -> str:
    found = element.find(path, NS)
    value = None if found is None else found.get("value")
    if not value:
        raise ExternalImportError(f"{label} is required.")
    return value


def _optional(element: etree._Element, path: str) -> str | None:
    found = element.find(path, NS)
    return None if found is None else found.get("value")


def _timestamp(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ExternalImportError(f"{label} must be an ISO-8601 timestamp.") from error
    if parsed.tzinfo is None:
        raise ExternalImportError(f"{label} must include a timezone.")
    return parsed


def _depth(root: etree._Element) -> int:
    return max((len(node.xpath("ancestor::*")) + 1 for node in root.iter()), default=0)


def _safe_root(xml: bytes) -> etree._Element:
    if not xml or len(xml) > MAX_IMPORT_BYTES:
        raise ExternalImportError("FHIR XML files must be between 1 byte and 2 MiB.")
    if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        raise ExternalImportError("DTD and entity declarations are not permitted.")
    try:
        root = etree.fromstring(
            xml,
            parser=etree.XMLParser(
                no_network=True, resolve_entities=False, load_dtd=False, huge_tree=False
            ),
        )
    except etree.XMLSyntaxError as error:
        raise ExternalImportError("FHIR XML is malformed.") from error
    if _depth(root) > MAX_IMPORT_DEPTH:
        raise ExternalImportError(
            f"FHIR XML nesting must not exceed {MAX_IMPORT_DEPTH}."
        )
    if len(root.findall("f:entry", NS)) > MAX_IMPORT_ENTRIES:
        raise ExternalImportError(
            f"FHIR files may contain at most {MAX_IMPORT_ENTRIES} entries."
        )
    if root.xpath(".//f:extension | .//f:modifierExtension", namespaces=NS):
        raise ExternalImportError(
            "Extensions are not supported by this exchange profile."
        )
    return root


def _coding(resource: etree._Element, path: str, label: str) -> dict[str, str]:
    coding = resource.find(path, NS)
    if coding is None:
        raise ExternalImportError(f"{label} is required.")
    return {
        "system": _primitive(coding, "f:system", f"{label} system"),
        "version": _optional(coding, "f:version") or "",
        "code": _primitive(coding, "f:code", f"{label} code"),
        "display": _optional(coding, "f:display") or "",
    }


def _author(practitioner: etree._Element) -> dict[str, str]:
    return {
        "identifier": _primitive(practitioner, "f:id", "Practitioner.id"),
        "identifier_system": _optional(practitioner, "f:identifier/f:system") or "",
        "identifier_value": _primitive(
            practitioner, "f:identifier/f:value", "Practitioner identifier"
        ),
        "family": _optional(practitioner, "f:name/f:family") or "",
        "given": _optional(practitioner, "f:name/f:given") or "",
    }


def _patient_dni(patient: etree._Element) -> str:
    system = str(settings.INTEROPERABILITY_PATIENT_DNI_SYSTEM)  # type: ignore[misc]
    identifiers = [
        identifier
        for identifier in patient.findall("f:identifier", NS)
        if _optional(identifier, "f:system") == system
    ]
    if len(identifiers) != 1:
        raise ExternalImportError(
            "The Bundle Patient must contain exactly one DNI identifier "
            f"using {system}."
        )
    return _primitive(identifiers[0], "f:value", "Patient DNI")


def parse_external_bundle(xml: bytes, *, source_system: str) -> ParsedBundle:
    """Validate and normalize a complete external file without any database access."""
    root = _safe_root(xml)
    try:
        validate_helixhealth_profile(xml)
    except FhirValidationError as error:
        raise ExternalImportError(str(error)) from error
    entries = root.findall("f:entry", NS)
    resources: dict[str, etree._Element] = {}
    full_urls: dict[str, etree._Element] = {}
    for entry in entries:
        full_url = _primitive(entry, "f:fullUrl", "Bundle entry fullUrl")
        holder = entry.find("f:resource", NS)
        resource = None if holder is None else next(iter(holder), None)
        if resource is None:
            raise ExternalImportError("Each Bundle entry requires one resource.")
        resource_id = _primitive(resource, "f:id", "Resource.id")
        if resource_id in resources:
            raise ExternalImportError(
                "Resource identifiers must be unique within a file."
            )
        resources[resource_id] = resource
        full_urls[full_url] = resource

    patient = next(
        resource
        for resource in resources.values()
        if etree.QName(resource).localname == "Patient"
    )
    _patient_dni(patient)
    organization = next(
        resource
        for resource in resources.values()
        if etree.QName(resource).localname == "Organization"
    )
    practitioner = next(
        resource
        for resource in resources.values()
        if etree.QName(resource).localname == "Practitioner"
    )
    if (
        _primitive(
            organization, "f:identifier/f:system", "Organization identifier system"
        )
        != source_system
    ):
        raise ExternalImportError(
            "The declared source system must match the Organization identifier system."
        )
    patient_url = next(
        url for url, resource in full_urls.items() if resource is patient
    )
    practitioner_url = next(
        url for url, resource in full_urls.items() if resource is practitioner
    )
    author = _author(practitioner)
    parsed: list[ParsedExternalRecord] = []
    for resource in resources.values():
        resource_type = etree.QName(resource).localname
        if resource_type not in {"Observation", "MedicationRequest"}:
            continue
        subject = _primitive(
            resource, "f:subject/f:reference", f"{resource_type}.subject"
        )
        author_ref = _primitive(
            resource,
            "f:performer/f:reference"
            if resource_type == "Observation"
            else "f:requester/f:reference",
            f"{resource_type} author reference",
        )
        if subject != patient_url or author_ref != practitioner_url:
            raise ExternalImportError(
                f"{resource_type} references must target the bundle Patient and Practitioner."
            )
        identifier = _primitive(resource, "f:id", f"{resource_type}.id")
        if resource_type == "Observation":
            code = _coding(resource, "f:code/f:coding", "Observation coding")
            components = [
                {
                    "coding": _coding(
                        component, "f:code/f:coding", "Observation component"
                    ),
                    "value": _primitive(
                        component,
                        "f:valueQuantity/f:value",
                        "Observation component value",
                    ),
                    "unit": _primitive(
                        component,
                        "f:valueQuantity/f:unit",
                        "Observation component unit",
                    ),
                }
                for component in resource.findall("f:component", NS)
            ]
            content: dict[str, object] = {
                "resource_type": resource_type,
                "coding": code,
                "effective_at": _primitive(
                    resource, "f:effectiveDateTime", "Observation effective time"
                ),
                "value": _optional(resource, "f:valueQuantity/f:value"),
                "unit": _optional(resource, "f:valueQuantity/f:unit"),
                "components": components,
            }
            occurred = _timestamp(
                str(content["effective_at"]), "Observation effective time"
            )
            kind = "observation"
        else:
            dosage = resource.find("f:dosageInstruction", NS)
            if dosage is None:
                raise ExternalImportError(
                    "MedicationRequest dosageInstruction is required."
                )
            content = {
                "resource_type": resource_type,
                "medication": _coding(
                    resource,
                    "f:medicationCodeableConcept/f:coding",
                    "Medication coding",
                ),
                "authored_at": _primitive(
                    resource, "f:authoredOn", "MedicationRequest.authoredOn"
                ),
                "group_identifier": _primitive(
                    resource,
                    "f:groupIdentifier/f:value",
                    "MedicationRequest group identifier",
                ),
                "directions": {
                    "text": _primitive(dosage, "f:text", "Medication directions"),
                    "dose_value": _primitive(
                        dosage,
                        "f:doseAndRate/f:doseQuantity/f:value",
                        "Medication dose",
                    ),
                    "dose_unit": _optional(
                        dosage, "f:doseAndRate/f:doseQuantity/f:unit"
                    )
                    or "",
                    "route": _primitive(dosage, "f:route/f:text", "Medication route"),
                    "frequency": _primitive(
                        dosage, "f:timing/f:code/f:text", "Medication frequency"
                    ),
                    "duration_days": _primitive(
                        dosage,
                        "f:timing/f:repeat/f:boundsDuration/f:value",
                        "Medication duration",
                    ),
                },
            }
            occurred = _timestamp(
                str(content["authored_at"]), "MedicationRequest.authoredOn"
            )
            kind = "medication-request"
        parsed.append(
            ParsedExternalRecord(
                resource_type=resource_type,
                external_identifier=identifier,
                kind=kind,
                source_recorded_at=occurred,
                external_author=author,
                content=content,
            )
        )
    if not parsed:
        raise ExternalImportError("The Bundle contains no supported clinical records.")
    bundle_identifier = _primitive(root, "f:identifier/f:value", "Bundle identifier")
    return ParsedBundle(bundle_identifier=bundle_identifier, records=tuple(parsed))


def patient_identity(xml: bytes) -> tuple[str, str]:
    """Return the DNI and birth date from a previously validated file."""
    root = _safe_root(xml)
    patient = root.find("f:entry/f:resource/f:Patient", NS)
    if patient is None:
        raise ExternalImportError("The Bundle requires one Patient.")
    return (
        _patient_dni(patient),
        _primitive(patient, "f:birthDate", "Patient birth date"),
    )
