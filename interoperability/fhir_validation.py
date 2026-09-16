"""Offline, defensive baseline validation for the supported FHIR R4 bundle."""

from functools import cache
from pathlib import Path
from xml.etree.ElementTree import ParseError

from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]
from defusedxml.ElementTree import fromstring  # type: ignore[import-untyped]
from fhir.resources.bundle import Bundle  # type: ignore[import-untyped]
from lxml import etree  # type: ignore[import-untyped]
from pydantic import ValidationError

FHIR_R4_ASSETS_DIR = Path(__file__).parent / "validation_assets" / "fhir-r4"
FHIR_R4_SCHEMA_PATH = FHIR_R4_ASSETS_DIR / "fhir-all.xsd"


class FhirValidationError(ValueError):
    """A submitted bundle cannot be accepted by the local R4 validation stack."""


FHIR_NAMESPACE = "http://hl7.org/fhir"
NS = {"f": FHIR_NAMESPACE}
SUPPORTED_RESOURCE_TYPES = frozenset(
    {"Patient", "Practitioner", "Organization", "Observation", "MedicationRequest"}
)
VITAL_CODES = {
    "85354-9": ("8480-6", "8462-4"),
    "8867-4": (),
    "8310-5": (),
}
VITAL_UNITS = {"85354-9": "mm[Hg]", "8867-4": "/min", "8310-5": "Cel"}


@cache
def fhir_r4_schema() -> etree.XMLSchema:
    """Load the checked-in R4 schema and its local imports without a network fetch."""
    parser = etree.XMLParser(no_network=True, resolve_entities=False, load_dtd=False)
    return etree.XMLSchema(etree.parse(str(FHIR_R4_SCHEMA_PATH), parser=parser))


def validate_fhir_r4_bundle(xml: bytes) -> Bundle:
    """Validate a FHIR R4 XML Bundle using only checked-in assets.

    This baseline combines explicit DTD/entity refusal, the official R4 XML
    schema, and an independent FHIR R4 resource model. The narrower project
    profile is intentionally added in the exchange implementation, not here.
    """
    try:
        fromstring(
            xml,
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
        document = etree.fromstring(
            xml,
            parser=etree.XMLParser(
                no_network=True,
                resolve_entities=False,
                load_dtd=False,
                huge_tree=False,
            ),
        )
        fhir_r4_schema().assertValid(document)
        return Bundle.parse_raw(xml, content_type="text/xml")
    except (
        DefusedXmlException,
        ParseError,
        etree.DocumentInvalid,
        etree.XMLSyntaxError,
        ValidationError,
        ValueError,
    ) as error:
        raise FhirValidationError(str(error)) from error


def _value(element: etree._Element, path: str) -> str | None:
    found = element.find(path, NS)
    return None if found is None else found.get("value")


def _required(element: etree._Element, path: str, label: str) -> str:
    value = _value(element, path)
    if not value:
        raise FhirValidationError(f"{label} is required by the HelixHealth v1 profile.")
    return value


def _resource_entries(
    root: etree._Element,
) -> list[tuple[etree._Element, etree._Element]]:
    entries: list[tuple[etree._Element, etree._Element]] = []
    for entry in root.findall("f:entry", NS):
        resource_holder = entry.find("f:resource", NS)
        resource = (
            None if resource_holder is None else next(iter(resource_holder), None)
        )
        if resource is None:
            raise FhirValidationError("Each Bundle entry must contain one resource.")
        entries.append((entry, resource))
    return entries


def _validate_reference(reference: str, full_urls: set[str]) -> None:
    if reference not in full_urls:
        raise FhirValidationError(
            f"Reference {reference!r} must resolve to an in-bundle fullUrl."
        )


def _validate_observation(resource: etree._Element, full_urls: set[str]) -> None:
    if _required(resource, "f:status", "Observation.status") != "final":
        raise FhirValidationError("Observation.status must be final.")
    category_code = _required(
        resource, "f:category/f:coding/f:code", "Observation.category code"
    )
    if category_code != "vital-signs":
        raise FhirValidationError("Observation.category must be vital-signs.")
    code = _required(resource, "f:code/f:coding/f:code", "Observation code")
    if code not in VITAL_CODES:
        raise FhirValidationError(f"Unsupported Observation code {code!r}.")
    _validate_reference(
        _required(resource, "f:subject/f:reference", "Observation.subject"), full_urls
    )
    _validate_reference(
        _required(resource, "f:performer/f:reference", "Observation.performer"),
        full_urls,
    )
    _required(resource, "f:effectiveDateTime", "Observation.effectiveDateTime")
    component_codes = tuple(
        component.find("f:code/f:coding/f:code", NS).get("value")
        for component in resource.findall("f:component", NS)
        if component.find("f:code/f:coding/f:code", NS) is not None
    )
    expected_components = VITAL_CODES[code]
    if expected_components:
        if component_codes != expected_components:
            raise FhirValidationError(
                f"Observation {code} must contain components {expected_components!r}."
            )
        quantities = resource.findall("f:component/f:valueQuantity", NS)
    else:
        if component_codes:
            raise FhirValidationError(
                f"Observation {code} must not contain components."
            )
        quantities = resource.findall("f:valueQuantity", NS)
    if not quantities:
        raise FhirValidationError(f"Observation {code} requires a value quantity.")
    for quantity in quantities:
        if (
            _required(quantity, "f:unit", "Observation quantity unit")
            != VITAL_UNITS[code]
        ):
            raise FhirValidationError(
                f"Observation {code} requires UCUM unit {VITAL_UNITS[code]!r}."
            )
        if (
            _required(quantity, "f:system", "Observation quantity system")
            != "http://unitsofmeasure.org"
        ):
            raise FhirValidationError(
                "Observation quantities must use the UCUM system."
            )


def _validate_medication_request(resource: etree._Element, full_urls: set[str]) -> None:
    if _required(resource, "f:status", "MedicationRequest.status") != "active":
        raise FhirValidationError("MedicationRequest.status must be active.")
    if _required(resource, "f:intent", "MedicationRequest.intent") != "order":
        raise FhirValidationError("MedicationRequest.intent must be order.")
    for path, label in (
        ("f:medicationCodeableConcept/f:coding/f:system", "Medication coding system"),
        ("f:medicationCodeableConcept/f:coding/f:code", "Medication coding code"),
        ("f:authoredOn", "MedicationRequest.authoredOn"),
        ("f:groupIdentifier/f:value", "MedicationRequest.groupIdentifier"),
        ("f:dosageInstruction/f:text", "MedicationRequest dosage text"),
        ("f:dosageInstruction/f:route/f:text", "MedicationRequest dosage route"),
        ("f:dosageInstruction/f:timing/f:code/f:text", "MedicationRequest frequency"),
        ("f:dosageInstruction/f:doseAndRate/f:doseQuantity/f:value", "Medication dose"),
    ):
        _required(resource, path, label)
    _validate_reference(
        _required(resource, "f:subject/f:reference", "MedicationRequest.subject"),
        full_urls,
    )
    _validate_reference(
        _required(resource, "f:requester/f:reference", "MedicationRequest.requester"),
        full_urls,
    )
    if (
        _required(
            resource,
            "f:dosageInstruction/f:timing/f:repeat/f:boundsDuration/f:code",
            "Medication duration unit",
        )
        != "d"
    ):
        raise FhirValidationError("Medication duration must be represented in days.")


def validate_helixhealth_profile(xml: bytes) -> Bundle:
    """Validate the official R4 XML schema plus HelixHealth's documented subset."""
    bundle = validate_fhir_r4_bundle(xml)
    try:
        root = etree.fromstring(
            xml,
            parser=etree.XMLParser(
                no_network=True, resolve_entities=False, load_dtd=False
            ),
        )
        if etree.QName(root).localname != "Bundle":
            raise FhirValidationError("The profile only accepts Bundle resources.")
        if _required(root, "f:type", "Bundle.type") != "collection":
            raise FhirValidationError("Bundle.type must be collection.")
        _required(root, "f:identifier/f:system", "Bundle identifier system")
        _required(root, "f:identifier/f:value", "Bundle identifier value")
        _required(root, "f:timestamp", "Bundle.timestamp")
        entries = _resource_entries(root)
        if not entries:
            raise FhirValidationError("The Bundle must contain at least one entry.")
        full_urls = {
            _required(entry, "f:fullUrl", "Bundle entry fullUrl")
            for entry, _ in entries
        }
        if len(full_urls) != len(entries) or any(
            not value.startswith("urn:uuid:") for value in full_urls
        ):
            raise FhirValidationError("Bundle fullUrl values must be unique UUID URNs.")
        resource_types = [etree.QName(resource).localname for _, resource in entries]
        unsupported = set(resource_types) - SUPPORTED_RESOURCE_TYPES
        if unsupported:
            raise FhirValidationError(
                f"Unsupported resource types: {sorted(unsupported)!r}."
            )
        if resource_types.count("Patient") != 1:
            raise FhirValidationError("The Bundle must contain exactly one Patient.")
        if (
            resource_types.count("Organization") != 1
            or resource_types.count("Practitioner") != 1
        ):
            raise FhirValidationError(
                "The Bundle requires one Organization and one Practitioner."
            )
        if not {"Observation", "MedicationRequest"}.intersection(resource_types):
            raise FhirValidationError(
                "The Bundle requires an Observation or MedicationRequest."
            )
        for _, resource in entries:
            resource_type = etree.QName(resource).localname
            _required(resource, "f:id", f"{resource_type}.id")
            if resource_type == "Patient":
                _required(
                    resource, "f:identifier/f:system", "Patient DNI identifier system"
                )
                _required(resource, "f:identifier/f:value", "Patient DNI")
                _required(resource, "f:birthDate", "Patient.birthDate")
            elif resource_type == "Organization":
                _required(
                    resource, "f:identifier/f:system", "Organization identifier system"
                )
                _required(resource, "f:identifier/f:value", "Organization identifier")
                _required(resource, "f:name", "Organization.name")
            elif resource_type == "Practitioner":
                _required(
                    resource,
                    "f:identifier/f:value",
                    "Practitioner registration identifier",
                )
            elif resource_type == "Observation":
                _validate_observation(resource, full_urls)
            elif resource_type == "MedicationRequest":
                _validate_medication_request(resource, full_urls)
    except (etree.XMLSyntaxError, ValueError) as error:
        if isinstance(error, FhirValidationError):
            raise
        raise FhirValidationError(str(error)) from error
    return bundle
