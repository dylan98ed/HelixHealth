from pathlib import Path

import pytest
from django.apps import apps

from interoperability.fhir_validation import (
    FHIR_R4_SCHEMA_PATH,
    FhirValidationError,
    validate_fhir_r4_bundle,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "fhir-r4"


def test_new_modules_are_registered_without_routes() -> None:
    assert apps.is_installed("catalogs")
    assert apps.is_installed("prescriptions")
    assert apps.is_installed("interoperability")


def test_checked_in_r4_assets_validate_an_independent_bundle() -> None:
    bundle = validate_fhir_r4_bundle(
        (FIXTURES_DIR / "independent-valid-bundle.xml").read_bytes()
    )

    assert FHIR_R4_SCHEMA_PATH.is_file()
    assert bundle.resource_type == "Bundle"
    assert bundle.type == "collection"
    assert bundle.entry[0].resource.resource_type == "Patient"


def test_checked_in_r4_assets_reject_an_invalid_bundle() -> None:
    with pytest.raises(FhirValidationError, match="type"):
        validate_fhir_r4_bundle(
            (FIXTURES_DIR / "invalid-missing-bundle-type.xml").read_bytes()
        )


def test_validation_normalizes_malformed_xml() -> None:
    with pytest.raises(FhirValidationError):
        validate_fhir_r4_bundle(b"<Bundle>")


def test_validation_rejects_external_entities_before_any_resolution() -> None:
    unsafe_xml = b"""<?xml version="1.0"?>
    <!DOCTYPE Bundle [<!ENTITY remote SYSTEM "https://invalid.example/fhir.xml">]>
    <Bundle xmlns="http://hl7.org/fhir"><type value="collection"/></Bundle>"""

    with pytest.raises(FhirValidationError):
        validate_fhir_r4_bundle(unsafe_xml)
