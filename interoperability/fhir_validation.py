"""Offline, defensive baseline validation for the supported FHIR R4 bundle."""

from functools import cache
from pathlib import Path

from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]
from defusedxml.ElementTree import fromstring  # type: ignore[import-untyped]
from fhir.resources.bundle import Bundle  # type: ignore[import-untyped]
from lxml import etree  # type: ignore[import-untyped]
from pydantic import ValidationError

FHIR_R4_ASSETS_DIR = Path(__file__).parent / "validation_assets" / "fhir-r4"
FHIR_R4_SCHEMA_PATH = FHIR_R4_ASSETS_DIR / "fhir-all.xsd"


class FhirValidationError(ValueError):
    """A submitted bundle cannot be accepted by the local R4 validation stack."""


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
        etree.DocumentInvalid,
        etree.XMLSyntaxError,
        ValidationError,
        ValueError,
    ) as error:
        raise FhirValidationError(str(error)) from error
