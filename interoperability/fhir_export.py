"""FHIR R4 XML serialization for HelixHealth's bounded clinical exchange."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from django.conf import settings
from lxml import etree  # type: ignore[import-untyped]

from clinical_records.models import Admission
from interoperability.fhir_validation import validate_helixhealth_profile
from patients.models import Patient
from professionals.models import Professional

FHIR_NAMESPACE = "http://hl7.org/fhir"
FHIR_XML_MEDIA_TYPE = "application/fhir+xml; charset=utf-8"
UCUM_SYSTEM = "http://unitsofmeasure.org"
LOINC_SYSTEM = "http://loinc.org"
VITAL_SIGNS_SYSTEM = "http://terminology.hl7.org/CodeSystem/observation-category"


def _setting(name: str) -> str:
    return str(getattr(settings, name))


BASE_URI = _setting("INTEROPERABILITY_BASE_URI")
INSTITUTION_SYSTEM = _setting("INTEROPERABILITY_INSTITUTION_SYSTEM")
INSTITUTION_CODE = _setting("INTEROPERABILITY_INSTITUTION_CODE")
INSTITUTION_NAME = _setting("INTEROPERABILITY_INSTITUTION_NAME")


class FhirExportError(ValueError):
    """The supplied local snapshots cannot form a supported exchange bundle."""


@dataclass(frozen=True)
class CodingSnapshot:
    system: str
    version: str
    code: str
    display: str


@dataclass(frozen=True)
class PrescriptionItemSnapshot:
    identifier: str
    medication: CodingSnapshot
    dose_value: Decimal
    dose_unit: str
    route: str
    frequency: str
    duration_days: int
    instructions: str = ""


@dataclass(frozen=True)
class PrescriptionSnapshot:
    identifier: UUID
    patient: PatientSnapshot
    prescriber: PractitionerSnapshot
    issued_at: datetime
    items: tuple[PrescriptionItemSnapshot, ...]
    reason: CodingSnapshot | None = None


@dataclass(frozen=True)
class PatientSnapshot:
    identifier: str
    dni: str
    first_name: str
    last_name: str
    date_of_birth: date


@dataclass(frozen=True)
class PractitionerSnapshot:
    identifier: str
    first_name: str
    last_name: str
    registration_number: str


def _element(
    parent: etree._Element, name: str, value: object | None = None
) -> etree._Element:
    child = etree.SubElement(parent, f"{{{FHIR_NAMESPACE}}}{name}")
    if value is not None:
        child.set("value", str(value))
    return child


def _resource_id(kind: str, stable_value: object) -> str:
    return str(uuid5(NAMESPACE_URL, f"{BASE_URI}/{kind}/{stable_value}"))


def _reference(resource_id: str) -> str:
    return f"urn:uuid:{resource_id}"


def _iso_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise FhirExportError("FHIR clinical timestamps must be timezone-aware.")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def patient_snapshot(patient: Patient) -> PatientSnapshot:
    return PatientSnapshot(
        identifier=patient.clinical_record_number,
        dni=patient.dni,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
    )


def practitioner_snapshot(professional: Professional) -> PractitionerSnapshot:
    if not professional.registration_number:
        raise FhirExportError("A FHIR practitioner requires a registration number.")
    return PractitionerSnapshot(
        identifier=professional.registration_number,
        first_name=professional.first_name or "",
        last_name=professional.last_name or "",
        registration_number=professional.registration_number,
    )


def _add_entry(
    bundle: etree._Element, resource: etree._Element, resource_id: str
) -> None:
    entry = _element(bundle, "entry")
    _element(entry, "fullUrl", _reference(resource_id))
    resource_holder = _element(entry, "resource")
    resource_holder.append(resource)


def _profile(resource: etree._Element, canonical: str) -> None:
    meta = _element(resource, "meta")
    _element(meta, "profile", canonical)


def _patient_resource(snapshot: PatientSnapshot) -> tuple[etree._Element, str]:
    resource_id = _resource_id("Patient", snapshot.identifier)
    patient = etree.Element(f"{{{FHIR_NAMESPACE}}}Patient")
    _element(patient, "id", resource_id)
    _profile(patient, f"{BASE_URI}/StructureDefinition/patient")
    identifier = _element(patient, "identifier")
    _element(identifier, "system", f"{BASE_URI}/identifiers/dni")
    _element(identifier, "value", snapshot.dni)
    name = _element(patient, "name")
    _element(name, "family", snapshot.last_name)
    _element(name, "given", snapshot.first_name)
    _element(patient, "birthDate", snapshot.date_of_birth.isoformat())
    return patient, resource_id


def _organization_resource() -> tuple[etree._Element, str]:
    resource_id = _resource_id("Organization", INSTITUTION_CODE)
    organization = etree.Element(f"{{{FHIR_NAMESPACE}}}Organization")
    _element(organization, "id", resource_id)
    _profile(
        organization,
        f"{BASE_URI}/StructureDefinition/organization",
    )
    identifier = _element(organization, "identifier")
    _element(identifier, "system", INSTITUTION_SYSTEM)
    _element(identifier, "value", INSTITUTION_CODE)
    _element(organization, "name", INSTITUTION_NAME)
    return organization, resource_id


def _practitioner_resource(
    snapshot: PractitionerSnapshot,
) -> tuple[etree._Element, str]:
    resource_id = _resource_id("Practitioner", snapshot.identifier)
    practitioner = etree.Element(f"{{{FHIR_NAMESPACE}}}Practitioner")
    _element(practitioner, "id", resource_id)
    _profile(
        practitioner,
        f"{BASE_URI}/StructureDefinition/practitioner",
    )
    identifier = _element(practitioner, "identifier")
    _element(
        identifier,
        "system",
        f"{BASE_URI}/identifiers/professional-registration",
    )
    _element(identifier, "value", snapshot.registration_number)
    name = _element(practitioner, "name")
    _element(name, "family", snapshot.last_name)
    _element(name, "given", snapshot.first_name)
    return practitioner, resource_id


def _coding(parent: etree._Element, coding: CodingSnapshot) -> None:
    coded = _element(parent, "coding")
    _element(coded, "system", coding.system)
    _element(coded, "version", coding.version)
    _element(coded, "code", coding.code)
    _element(coded, "display", coding.display)


def _reference_element(parent: etree._Element, name: str, resource_id: str) -> None:
    reference = _element(parent, name)
    _element(reference, "reference", _reference(resource_id))


def _observation_resource(
    *,
    identifier: str,
    code: CodingSnapshot,
    patient_id: str,
    practitioner_id: str,
    recorded_at: datetime,
    quantity: tuple[object, str],
    components: Sequence[tuple[CodingSnapshot, object, str]] = (),
) -> tuple[etree._Element, str]:
    resource_id = _resource_id("Observation", identifier)
    observation = etree.Element(f"{{{FHIR_NAMESPACE}}}Observation")
    _element(observation, "id", resource_id)
    _profile(
        observation,
        f"{BASE_URI}/StructureDefinition/vital-sign-observation",
    )
    _element(observation, "status", "final")
    category = _element(observation, "category")
    _coding(
        category, CodingSnapshot(VITAL_SIGNS_SYSTEM, "R4", "vital-signs", "Vital Signs")
    )
    codeable = _element(observation, "code")
    _coding(codeable, code)
    _reference_element(observation, "subject", patient_id)
    _element(observation, "effectiveDateTime", _iso_datetime(recorded_at))
    _element(observation, "issued", _iso_datetime(recorded_at))
    _reference_element(observation, "performer", practitioner_id)
    if components:
        for component_code, value, unit in components:
            component = _element(observation, "component")
            component_codeable = _element(component, "code")
            _coding(component_codeable, component_code)
            quantity_element = _element(component, "valueQuantity")
            _element(quantity_element, "value", value)
            _element(quantity_element, "unit", unit)
            _element(quantity_element, "system", UCUM_SYSTEM)
            _element(quantity_element, "code", unit)
    else:
        quantity_element = _element(observation, "valueQuantity")
        _element(quantity_element, "value", quantity[0])
        _element(quantity_element, "unit", quantity[1])
        _element(quantity_element, "system", UCUM_SYSTEM)
        _element(quantity_element, "code", quantity[1])
    return observation, resource_id


def _medication_request_resource(
    *,
    prescription: PrescriptionSnapshot,
    item: PrescriptionItemSnapshot,
    patient_id: str,
    practitioner_id: str,
) -> tuple[etree._Element, str]:
    resource_id = _resource_id("MedicationRequest", item.identifier)
    request = etree.Element(f"{{{FHIR_NAMESPACE}}}MedicationRequest")
    _element(request, "id", resource_id)
    _profile(
        request,
        f"{BASE_URI}/StructureDefinition/medication-request",
    )
    _element(request, "status", "active")
    _element(request, "intent", "order")
    medication = _element(request, "medicationCodeableConcept")
    _coding(medication, item.medication)
    _reference_element(request, "subject", patient_id)
    _element(request, "authoredOn", _iso_datetime(prescription.issued_at))
    _reference_element(request, "requester", practitioner_id)
    if prescription.reason is not None:
        reason = _element(request, "reasonCode")
        _coding(reason, prescription.reason)
    group = _element(request, "groupIdentifier")
    _element(
        group,
        "system",
        f"{BASE_URI}/identifiers/prescription-group",
    )
    _element(group, "value", prescription.identifier)
    dosage = _element(request, "dosageInstruction")
    directions = " ".join(
        part
        for part in (
            f"{item.dose_value} {item.dose_unit}",
            item.route,
            item.frequency,
            f"for {item.duration_days} days",
            item.instructions.strip(),
        )
        if part
    )
    _element(dosage, "text", directions)
    timing = _element(dosage, "timing")
    repeat = _element(timing, "repeat")
    bounds = _element(repeat, "boundsDuration")
    _element(bounds, "value", item.duration_days)
    _element(bounds, "unit", "days")
    _element(bounds, "system", UCUM_SYSTEM)
    _element(bounds, "code", "d")
    timing_code = _element(timing, "code")
    _element(timing_code, "text", item.frequency)
    route = _element(dosage, "route")
    _element(route, "text", item.route)
    dose_and_rate = _element(dosage, "doseAndRate")
    dose = _element(dose_and_rate, "doseQuantity")
    _element(dose, "value", item.dose_value)
    _element(dose, "unit", item.dose_unit)
    return request, resource_id


def _bundle_root(identifier: str, timestamp: datetime) -> etree._Element:
    bundle = etree.Element(f"{{{FHIR_NAMESPACE}}}Bundle", nsmap={None: FHIR_NAMESPACE})
    _element(bundle, "id", _resource_id("Bundle", identifier))
    _profile(
        bundle,
        f"{BASE_URI}/StructureDefinition/clinical-exchange-bundle",
    )
    bundle_identifier = _element(bundle, "identifier")
    _element(
        bundle_identifier,
        "system",
        f"{BASE_URI}/identifiers/bundle",
    )
    _element(bundle_identifier, "value", identifier)
    _element(bundle, "type", "collection")
    _element(bundle, "timestamp", _iso_datetime(timestamp))
    return bundle


def serialize_admission_bundle(admissions: Iterable[Admission]) -> bytes:
    """Serialize saved admissions without modifying any domain record."""
    selected = tuple(admissions)
    if not selected:
        raise FhirExportError("Select at least one admission for export.")
    patient = selected[0].patient
    if any(admission.patient_id != patient.pk for admission in selected):
        raise FhirExportError("All selected admissions must belong to one patient.")
    professional = selected[0].professional
    if any(admission.professional_id != professional.pk for admission in selected):
        raise FhirExportError(
            "Admissions with different authors require separate exports."
        )

    patient_data = patient_snapshot(patient)
    professional_data = practitioner_snapshot(professional)
    bundle = _bundle_root(
        "admissions-" + "-".join(str(admission.pk) for admission in selected),
        max(admission.created_at for admission in selected),
    )
    patient_resource, patient_id = _patient_resource(patient_data)
    organization_resource, organization_id = _organization_resource()
    practitioner_resource, practitioner_id = _practitioner_resource(professional_data)
    _add_entry(bundle, patient_resource, patient_id)
    _add_entry(bundle, organization_resource, organization_id)
    _add_entry(bundle, practitioner_resource, practitioner_id)
    for admission in selected:
        bp, _ = _observation_resource(
            identifier=f"admission-{admission.pk}-blood-pressure",
            code=CodingSnapshot(
                LOINC_SYSTEM, "2.77", "85354-9", "Blood pressure panel"
            ),
            quantity=(admission.systolic_blood_pressure, "mm[Hg]"),
            components=(
                (
                    CodingSnapshot(
                        LOINC_SYSTEM, "2.77", "8480-6", "Systolic blood pressure"
                    ),
                    admission.systolic_blood_pressure,
                    "mm[Hg]",
                ),
                (
                    CodingSnapshot(
                        LOINC_SYSTEM, "2.77", "8462-4", "Diastolic blood pressure"
                    ),
                    admission.diastolic_blood_pressure,
                    "mm[Hg]",
                ),
            ),
            patient_id=patient_id,
            practitioner_id=practitioner_id,
            recorded_at=admission.created_at,
        )
        heart_rate, _ = _observation_resource(
            identifier=f"admission-{admission.pk}-heart-rate",
            code=CodingSnapshot(LOINC_SYSTEM, "2.77", "8867-4", "Heart rate"),
            quantity=(admission.heart_rate, "/min"),
            patient_id=patient_id,
            practitioner_id=practitioner_id,
            recorded_at=admission.created_at,
        )
        temperature, _ = _observation_resource(
            identifier=f"admission-{admission.pk}-temperature",
            code=CodingSnapshot(LOINC_SYSTEM, "2.77", "8310-5", "Body temperature"),
            quantity=(admission.temperature, "Cel"),
            patient_id=patient_id,
            practitioner_id=practitioner_id,
            recorded_at=admission.created_at,
        )
        _add_entry(
            bundle,
            bp,
            _resource_id("Observation", f"admission-{admission.pk}-blood-pressure"),
        )
        _add_entry(
            bundle,
            heart_rate,
            _resource_id("Observation", f"admission-{admission.pk}-heart-rate"),
        )
        _add_entry(
            bundle,
            temperature,
            _resource_id("Observation", f"admission-{admission.pk}-temperature"),
        )
    xml = etree.tostring(bundle, encoding="UTF-8", xml_declaration=True)
    validate_helixhealth_profile(xml)
    return xml


def serialize_prescription_bundle(prescription: PrescriptionSnapshot) -> bytes:
    """Serialize an immutable issuance snapshot into one MedicationRequest per item."""
    if not prescription.items:
        raise FhirExportError("A prescription export requires at least one item.")
    bundle = _bundle_root(
        f"prescription-{prescription.identifier}", prescription.issued_at
    )
    patient_resource, patient_id = _patient_resource(prescription.patient)
    organization_resource, organization_id = _organization_resource()
    practitioner_resource, practitioner_id = _practitioner_resource(
        prescription.prescriber
    )
    _add_entry(bundle, patient_resource, patient_id)
    _add_entry(bundle, organization_resource, organization_id)
    _add_entry(bundle, practitioner_resource, practitioner_id)
    for item in prescription.items:
        request, request_id = _medication_request_resource(
            prescription=prescription,
            item=item,
            patient_id=patient_id,
            practitioner_id=practitioner_id,
        )
        _add_entry(bundle, request, request_id)
    xml = etree.tostring(bundle, encoding="UTF-8", xml_declaration=True)
    validate_helixhealth_profile(xml)
    return xml
