"""Read-only, deterministic FHIR R4 JSON export of selected clinical requests."""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid5

from django.http import Http404

from clinical_records.models import Admission
from interoperability.json_importing import JsonImportError, parse_json_bundle
from interoperability.limits import MAX_BUNDLE_BYTES, MAX_BUNDLE_ENTRIES
from interoperability.models import (
    ExternalClinicalRecord,
    ImportedMedicationRequest,
    ImportedServiceRequest,
)
from patients.models import Patient
from prescriptions.models import Prescription
from professionals.models import Professional

EXPORT_NAMESPACE = UUID("b00c4aaa-beba-4728-a95d-cd62ee78f44b")
IDENTIFIER_SYSTEM = "https://helixhealth.local/interoperability/json-export"
DNI_SYSTEM = "https://helixhealth.local/interoperability/identifiers/dni"


class JsonExportSelectionError(ValueError):
    """The selection cannot form a single supported patient/practitioner Bundle."""


def _id(kind: str, stable_key: str) -> str:
    return str(uuid5(EXPORT_NAMESPACE, f"{kind}:{stable_key}"))


def _entry(resource: dict[str, Any]) -> dict[str, Any]:
    return {"fullUrl": f"urn:uuid:{resource['id']}", "resource": resource}


def json_export_filename(raw: bytes, *, student_last_name: str) -> str:
    """Name a validated export using its identities and the exporting student's surname."""
    parsed = parse_json_bundle(raw)
    surname = "".join(
        character
        for character in unicodedata.normalize("NFKD", student_last_name)
        if character.isascii() and character.isalnum()
    )
    if not surname:
        raise JsonExportSelectionError("The exporting professional needs a surname for the file name.")
    return f"FHIR_{parsed.patient_dni}_{parsed.practitioner_dni}_{surname}.json"


def _selected(model: Any, patient: Patient, identifiers: tuple[Any, ...], **lookups: Any) -> tuple[Any, ...]:
    rows = tuple(model.objects.filter(patient=patient, **lookups))
    if len(rows) != len(identifiers):
        raise Http404("A selected record does not belong to this patient.")
    return rows


def _patient_resource(patient: Patient) -> dict[str, Any]:
    gender = {
        "m": "male", "male": "male", "masculino": "male",
        "f": "female", "female": "female", "femenino": "female",
        "o": "other", "other": "other", "otro": "other",
        "u": "unknown", "unknown": "unknown", "unspecified": "unknown",
    }.get(patient.sex.strip().lower())
    if gender is None or not patient.dni or not patient.date_of_birth:
        raise JsonExportSelectionError("The patient needs DNI, birth date and supported gender.")
    return {
        "resourceType": "Patient", "id": _id("Patient", patient.dni),
        "identifier": [{"system": DNI_SYSTEM, "value": patient.dni}],
        "name": [{"family": patient.last_name, "given": [patient.first_name]}],
        "gender": gender, "birthDate": patient.date_of_birth.isoformat(),
    }


def _practitioner_resource(professional: Professional) -> dict[str, Any]:
    if not professional.dni or not professional.license_number:
        raise JsonExportSelectionError("The requester needs DNI and license number.")
    return {
        "resourceType": "Practitioner", "id": _id("Practitioner", professional.dni),
        "identifier": [{"system": DNI_SYSTEM, "value": professional.dni}],
        "name": [{"family": professional.last_name, "given": [professional.first_name]}],
        "qualification": [{"identifier": [{"value": professional.license_number}],
                           "code": {"text": "Professional license"}}],
    }


def _service_resource(row: ImportedServiceRequest, patient_ref: str, practitioner_ref: str) -> dict[str, Any]:
    return {
        "resourceType": "ServiceRequest", "id": _id("ServiceRequest", f"{row.source_system}:{row.external_identifier}"),
        "identifier": [{"system": row.source_system, "value": row.external_identifier}],
        "status": row.status, "intent": row.intent,
        "code": {"coding": [{"system": row.code_system, "code": row.code, "display": row.description}],
                 "text": row.description},
        "subject": {"reference": patient_ref}, "requester": {"reference": practitioner_ref},
        "authoredOn": row.authored_on,
    }


def _imported_medication_resource(
    row: ImportedMedicationRequest, patient_ref: str, practitioner_ref: str,
) -> dict[str, Any]:
    concept: dict[str, Any] = {"text": row.medication_display}
    if row.medication_code_system and row.medication_code:
        concept["coding"] = [{"system": row.medication_code_system,
                              "code": row.medication_code, "display": row.medication_display}]
    resource: dict[str, Any] = {
        "resourceType": "MedicationRequest",
        "id": _id("MedicationRequest", f"{row.source_system}:{row.external_identifier}"),
        "identifier": [{"system": row.source_system, "value": row.external_identifier}],
        "status": row.status, "intent": row.intent, "medicationCodeableConcept": concept,
        "subject": {"reference": patient_ref}, "requester": {"reference": practitioner_ref},
        "authoredOn": row.authored_on, "dosageInstruction": row.dosage_instructions,
    }
    if row.dispense_quantity:
        resource["dispenseRequest"] = {"quantity": row.dispense_quantity}
    if row.notes:
        resource["note"] = row.notes
    return resource


def _local_medication_resources(
    prescription: Prescription, patient_ref: str, practitioner_ref: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in prescription.items.all():
        snapshot = item.snapshot
        medication = snapshot["medication"]
        directions = snapshot.get("instructions") or snapshot["frequency"]
        result.append({
            "resourceType": "MedicationRequest", "id": snapshot["identifier"],
            "identifier": [{"system": IDENTIFIER_SYSTEM, "value": snapshot["identifier"]}],
            "status": "active", "intent": "order",
            "medicationCodeableConcept": {
                "coding": [{"system": medication["system"], "code": medication["code"],
                            "display": medication["display"]}],
                "text": medication["display"],
            },
            "subject": {"reference": patient_ref}, "requester": {"reference": practitioner_ref},
            "authoredOn": prescription.issued_at.isoformat(),
            "dosageInstruction": [{
                "text": directions, "route": {"text": snapshot["route"]},
                "doseAndRate": [{"doseQuantity": {
                    "value": float(snapshot["dose_value"]), "unit": snapshot["dose_unit"],
                }}],
            }],
        })
    if not result:
        raise JsonExportSelectionError("An issued prescription has no medication items.")
    return result


def _observation_resource(
    record: ExternalClinicalRecord, patient_ref: str, practitioner_ref: str,
) -> dict[str, Any]:
    content = record.content
    if not isinstance(content, dict) or content.get("resourceType") != "Observation":
        raise JsonExportSelectionError("Only FHIR JSON vital sign observations can be exported.")
    resource = dict(content)
    resource["id"] = _id("Observation", f"{record.source_system}:{record.external_identifier}")
    resource["subject"] = {"reference": patient_ref}
    if resource.get("performer"):
        resource["performer"] = [{"reference": practitioner_ref}]
    return resource


def _local_observation_resources(
    admission: Admission, patient_ref: str, practitioner_ref: str,
) -> list[dict[str, Any]]:
    recorded_at = admission.created_at.astimezone(UTC).isoformat()
    shared = {
        "resourceType": "Observation", "status": "final",
        "category": [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "vital-signs", "display": "Vital Signs",
        }]}],
        "subject": {"reference": patient_ref},
        "performer": [{"reference": practitioner_ref}],
        "effectiveDateTime": recorded_at,
    }

    def quantity(value: int | float, unit: str) -> dict[str, Any]:
        return {"value": value, "unit": unit,
                "system": "http://unitsofmeasure.org", "code": unit}

    bp = {
        **shared, "id": _id("Observation", f"admission-{admission.pk}-blood-pressure"),
        "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9",
                            "display": "Blood pressure panel"}]},
        "component": [
            {"code": {"coding": [{"system": "http://loinc.org", "code": "8480-6"}]},
             "valueQuantity": quantity(admission.systolic_blood_pressure, "mm[Hg]")},
            {"code": {"coding": [{"system": "http://loinc.org", "code": "8462-4"}]},
             "valueQuantity": quantity(admission.diastolic_blood_pressure, "mm[Hg]")},
        ],
    }
    heart_rate = {
        **shared, "id": _id("Observation", f"admission-{admission.pk}-heart-rate"),
        "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4",
                            "display": "Heart rate"}]},
        "valueQuantity": quantity(admission.heart_rate, "/min"),
    }
    temperature = {
        **shared, "id": _id("Observation", f"admission-{admission.pk}-temperature"),
        "code": {"coding": [{"system": "http://loinc.org", "code": "8310-5",
                            "display": "Body temperature"}]},
        "valueQuantity": quantity(float(admission.temperature), "Cel"),
    }
    return [bp, heart_rate, temperature]


def export_selected_json(
    *, patient: Patient, service_request_ids: Iterable[int],
    medication_request_ids: Iterable[int], prescription_ids: Iterable[UUID],
    observation_ids: Iterable[int] = (), admission_ids: Iterable[int] = (),
) -> bytes:
    """Export selected patient-owned requests without modifying clinical state."""
    service_ids = tuple(service_request_ids)
    medication_ids = tuple(medication_request_ids)
    prescription_keys = tuple(prescription_ids)
    observation_keys = tuple(observation_ids)
    admission_keys = tuple(admission_ids)
    services = _selected(ImportedServiceRequest, patient, service_ids, pk__in=service_ids)
    medications = _selected(ImportedMedicationRequest, patient, medication_ids, pk__in=medication_ids)
    prescriptions = _selected(Prescription, patient, prescription_keys, identifier__in=prescription_keys)
    observations = _selected(ExternalClinicalRecord, patient, observation_keys,
                             pk__in=observation_keys, resource_type="Observation")
    admissions = _selected(Admission, patient, admission_keys, pk__in=admission_keys)
    if (services and not (medications or prescriptions)) or (
        not services and not (admissions or observations)
    ):
        raise JsonExportSelectionError(
            "Select a requested procedure with medication, or at least one vital-sign observation."
        )
    professional_ids = {row.requester_id for row in (*services, *medications)}
    professional_ids.update(row.prescriber_id for row in prescriptions)
    if any(row.professional_id is None for row in admissions):
        raise JsonExportSelectionError(
            "Admissions recorded by administrators have no physician for FHIR observations."
        )
    professional_ids.update(
        row.professional_id for row in admissions if row.professional_id is not None
    )
    observation_authors = [row.external_author.get("professional_id") for row in observations]
    if any(not isinstance(author, int) for author in observation_authors):
        raise JsonExportSelectionError("Selected observations need a known practitioner.")
    professional_ids.update(observation_authors)
    if len(professional_ids) != 1:
        raise JsonExportSelectionError("All selected records must have the same practitioner.")
    professional = Professional.objects.get(pk=professional_ids.pop())
    if any(row.external_author.get("professional_id") != professional.pk for row in observations):
        raise JsonExportSelectionError("Selected observations must belong to the same practitioner.")
    patient_resource = _patient_resource(patient)
    practitioner_resource = _practitioner_resource(professional)
    patient_ref = f"Patient/{patient_resource['id']}"
    practitioner_ref = f"Practitioner/{practitioner_resource['id']}"
    resources = [patient_resource, practitioner_resource]
    resources.extend(_service_resource(row, patient_ref, practitioner_ref) for row in services)
    resources.extend(_imported_medication_resource(row, patient_ref, practitioner_ref) for row in medications)
    for prescription in prescriptions:
        resources.extend(_local_medication_resources(prescription, patient_ref, practitioner_ref))
    resources.extend(_observation_resource(row, patient_ref, practitioner_ref) for row in observations)
    for admission in admissions:
        resources.extend(_local_observation_resources(admission, patient_ref, practitioner_ref))
    if len(resources) > MAX_BUNDLE_ENTRIES:
        raise JsonExportSelectionError(f"A Bundle may contain at most {MAX_BUNDLE_ENTRIES} entries.")
    stable_selection = ":".join(sorted(f"{resource['resourceType']}/{resource['id']}" for resource in resources))
    bundle = {
        "resourceType": "Bundle", "id": _id("Bundle", stable_selection),
        "identifier": {"system": IDENTIFIER_SYSTEM, "value": _id("Bundle", stable_selection)},
        "type": "collection", "timestamp": datetime.now(UTC).isoformat(),
        "entry": [_entry(resource) for resource in resources],
    }
    raw = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(raw) > MAX_BUNDLE_BYTES:
        raise JsonExportSelectionError("FHIR JSON exports may not exceed 2 MiB.")
    try:
        parse_json_bundle(raw)
    except JsonImportError as error:
        raise JsonExportSelectionError(f"Selected records cannot form a valid FHIR JSON Bundle: {error}") from error
    return raw
