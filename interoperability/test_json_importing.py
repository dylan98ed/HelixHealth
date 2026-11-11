"""Contract checks for the independently authored FHIR JSON example."""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from interoperability.json_importing import JsonImportError, parse_json_bundle

FIXTURE = Path(
    "docs/interoperability/fhir-r4/json-v2/fixtures/independent-valid-bundle.json"
)


@pytest.mark.parametrize(
    "name", ["invalid-unresolved-reference.json", "invalid-ambiguous-dni.json"]
)
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
    document["entry"].append(
        {
            "fullUrl": f"urn:uuid:{uuid4()}",
            "resource": {
                "resourceType": "Observation",
                "id": "pulse-1",
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
                "subject": {"reference": "Patient/patient-1"},
                "effectiveDateTime": "2026-10-27T14:30:00Z",
                "valueQuantity": {
                    "value": 72,
                    "system": "http://unitsofmeasure.org",
                    "code": "/min",
                },
            },
        }
    )
    document["entry"][-1]["resource"]["subject"] = document["entry"][2]["resource"][
        "subject"
    ]
    assert len(parse_json_bundle(json.dumps(document).encode()).observations) == 1


@pytest.mark.parametrize("include_medication", [False, True])
def test_vital_sign_bundle_without_service_request_parses(
    include_medication: bool,
) -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    patient_reference = document["entry"][2]["resource"]["subject"]
    document["entry"] = [
        entry
        for entry in document["entry"]
        if entry["resource"]["resourceType"] != "ServiceRequest"
        and (
            include_medication
            or entry["resource"]["resourceType"] != "MedicationRequest"
        )
    ]
    document["entry"].append(
        {
            "fullUrl": f"urn:uuid:{uuid4()}",
            "resource": {
                "resourceType": "Observation",
                "id": "local-pulse",
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
                "subject": patient_reference,
                "effectiveDateTime": "2026-10-27T14:30:00Z",
                "valueQuantity": {
                    "value": 72,
                    "system": "http://unitsofmeasure.org",
                    "code": "/min",
                },
            },
        }
    )
    parsed = parse_json_bundle(json.dumps(document).encode())
    assert len(parsed.observations) == 1
    assert len(parsed.service_requests) == 0
    assert len(parsed.medication_requests) == int(include_medication)


@pytest.mark.parametrize(
    "mutation", ["broken_reference", "missing_medication", "duplicate_key", "oversized"]
)
def test_rejects_invalid_bundle(mutation: str) -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if mutation == "broken_reference":
        document["entry"][2]["resource"]["subject"]["reference"] = "Patient/missing"
    elif mutation == "missing_medication":
        document["entry"] = [
            entry
            for entry in document["entry"]
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


@pytest.mark.parametrize(
    "mutation",
    [
        "service_code",
        "service_date",
        "medication_date",
        "patient_date",
        "entry_limit",
        "depth_limit",
        "duplicate_full_url",
        "unsupported_type",
    ],
)
def test_rejects_profile_codes_dates_and_limits(mutation: str) -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if mutation == "service_code":
        document["entry"][2]["resource"]["code"]["coding"][0]["system"] = ""
    elif mutation == "service_date":
        document["entry"][2]["resource"]["authoredOn"] = "2026-13-40"
    elif mutation == "medication_date":
        document["entry"][3]["resource"]["authoredOn"] = "2026-10-27T14:30:00"
    elif mutation == "patient_date":
        document["entry"][0]["resource"]["birthDate"] = "1990-02-30"
    elif mutation == "entry_limit":
        document["entry"] = document["entry"] * 126
    elif mutation == "depth_limit":
        nested: object = "x"
        for _ in range(65):
            nested = {"child": nested}
        document["extra"] = nested
    elif mutation == "duplicate_full_url":
        document["entry"][3]["fullUrl"] = document["entry"][2]["fullUrl"]
    elif mutation == "unsupported_type":
        document["entry"][3]["resource"]["resourceType"] = "Encounter"
    with pytest.raises(JsonImportError):
        parse_json_bundle(json.dumps(document).encode())


def test_rejects_wrong_observation_unit() -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["entry"].append(
        {
            "fullUrl": f"urn:uuid:{uuid4()}",
            "resource": {
                "resourceType": "Observation",
                "id": "pulse-bad-unit",
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
                "subject": document["entry"][2]["resource"]["subject"],
                "effectiveDateTime": "2026-10-27T14:30:00Z",
                "valueQuantity": {
                    "value": 72,
                    "system": "http://unitsofmeasure.org",
                    "code": "Cel",
                },
            },
        }
    )
    with pytest.raises(JsonImportError, match="UCUM"):
        parse_json_bundle(json.dumps(document).encode())


def test_rejects_blood_pressure_component_with_empty_coding() -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["entry"].append(
        {
            "fullUrl": f"urn:uuid:{uuid4()}",
            "resource": {
                "resourceType": "Observation",
                "id": "blood-pressure-empty-coding",
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9"}]},
                "subject": document["entry"][2]["resource"]["subject"],
                "effectiveDateTime": "2026-10-27T14:30:00Z",
                "component": [
                    {"code": {"coding": []}, "valueQuantity": {"value": 120}},
                    {
                        "code": {"coding": [{"code": "8462-4"}]},
                        "valueQuantity": {"value": 80},
                    },
                ],
            },
        }
    )
    with pytest.raises(JsonImportError, match="Blood pressure requires"):
        parse_json_bundle(json.dumps(document).encode())
