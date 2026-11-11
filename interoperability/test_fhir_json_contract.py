"""Check the independent JSON contract fixture against the FHIR R4 model."""

import json
from pathlib import Path

from fhir.resources.bundle import Bundle

FIXTURES = Path("docs/interoperability/fhir-r4/json-v2/fixtures")


def _entries(name: str) -> list[dict]:
    bundle = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    Bundle.parse_obj(bundle)  # Independent FHIR R4 structural validation.
    return bundle["entry"]


def test_independent_json_bundle_is_r4_and_has_required_resources() -> None:
    entries = _entries("independent-valid-bundle.json")
    resources = [entry["resource"] for entry in entries]
    assert [resource["resourceType"] for resource in resources] == [
        "Patient",
        "Practitioner",
        "ServiceRequest",
        "MedicationRequest",
    ]
    assert all(entry["fullUrl"].startswith("urn:uuid:") for entry in entries)
    targets = {
        entry["fullUrl"]: resource
        for entry, resource in zip(entries, resources, strict=True)
    }
    targets.update(
        {
            f"{resource['resourceType']}/{resource['id']}": resource
            for resource in resources
        }
    )
    for resource in resources[2:]:
        assert targets[resource["subject"]["reference"]]["resourceType"] == "Patient"
        assert (
            targets[resource["requester"]["reference"]]["resourceType"]
            == "Practitioner"
        )


def test_unresolved_reference_fixture_is_r4_but_violates_local_contract() -> None:
    entries = _entries("invalid-unresolved-reference.json")
    assert entries[2]["resource"]["subject"]["reference"] == "Patient/missing"
    assert all(entry["resource"]["id"] != "missing" for entry in entries)


def test_ambiguous_dni_fixture_is_r4_but_violates_local_contract() -> None:
    entries = _entries("invalid-ambiguous-dni.json")
    patient = entries[0]["resource"]
    assert (
        sum(identifier["value"] == "12345678" for identifier in patient["identifier"])
        == 2
    )
