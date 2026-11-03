"""Contract checks for the independently authored FHIR JSON example."""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from interoperability.json_importing import JsonImportError, parse_json_bundle

FIXTURE = Path("docs/interoperability/fhir-r4/json-v2/fixtures/independent-valid-bundle.json")


@pytest.mark.parametrize("name", ["invalid-unresolved-reference.json", "invalid-ambiguous-dni.json"])
def test_independent_invalid_examples_are_rejected(name: str) -> None:
    with pytest.raises(JsonImportError):
        parse_json_bundle(FIXTURE.with_name(name).read_bytes())


def test_independent_bundle_parses() -> None:
    parsed = parse_json_bundle(FIXTURE.read_bytes())
    assert parsed.patient_dni == "12345678"
    assert parsed.practitioner_dni == "23456789"
    assert len(parsed.service_requests) == len(parsed.medication_requests) == 1


def test_optional_vital_sign_parses() -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["entry"].append({
        "fullUrl": f"urn:uuid:{uuid4()}",
        "resource": {
            "resourceType": "Observation", "id": "pulse-1", "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
            "subject": {"reference": "Patient/patient-1"},
            "effectiveDateTime": "2026-10-27T14:30:00Z",
            "valueQuantity": {"value": 72, "system": "http://unitsofmeasure.org", "code": "/min"},
        },
    })
    document["entry"][-1]["resource"]["subject"] = document["entry"][2]["resource"]["subject"]
    assert len(parse_json_bundle(json.dumps(document).encode()).observations) == 1


@pytest.mark.parametrize("mutation", ["broken_reference", "missing_medication", "duplicate_key", "oversized"])
def test_rejects_invalid_bundle(mutation: str) -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if mutation == "broken_reference":
        document["entry"][2]["resource"]["subject"]["reference"] = "Patient/missing"
    elif mutation == "missing_medication":
        document["entry"] = [
            entry for entry in document["entry"]
            if entry["resource"]["resourceType"] != "MedicationRequest"
        ]
    elif mutation == "duplicate_key":
        with pytest.raises(JsonImportError, match="Duplicate JSON key"):
            parse_json_bundle(b'{"resourceType":"Bundle","resourceType":"Bundle"}')
        return
    elif mutation == "oversized":
        with pytest.raises(JsonImportError, match="2 MiB"):
            parse_json_bundle(b"x" * (2 * 1024 * 1024 + 1))
        return
    with pytest.raises(JsonImportError):
        parse_json_bundle(json.dumps(document).encode())
