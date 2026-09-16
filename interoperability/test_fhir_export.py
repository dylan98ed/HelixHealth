from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from django.contrib.auth import get_user_model
from lxml import etree

from clinical_records.models import Admission
from interoperability.fhir_export import (
    FHIR_XML_MEDIA_TYPE,
    CodingSnapshot,
    PatientSnapshot,
    PractitionerSnapshot,
    PrescriptionItemSnapshot,
    PrescriptionSnapshot,
    serialize_admission_bundle,
    serialize_prescription_bundle,
)
from interoperability.fhir_validation import (
    FhirValidationError,
    validate_helixhealth_profile,
)
from patients.models import Patient
from professionals.models import HospitalService, Professional, Specialty

FIXTURES_DIR = Path("docs/interoperability/fhir-r4/fixtures")
NS = {"f": "http://hl7.org/fhir"}


def _patient() -> Patient:
    return Patient.objects.create(
        dni="12345678",
        clinical_record_number="HC-FHIR-01",
        first_name="Ana & Bea",
        last_name="García <Test>",
        date_of_birth=date(1980, 4, 20),
        sex="unspecified",
        phone="+54 11 5555-0101",
        email="ana@example.test",
        address="Test address",
        health_insurer="Test insurer",
    )


def _professional() -> Professional:
    user = get_user_model().objects.create_user(
        username="fhir-professional", password="fhir-test-password"
    )
    specialty = Specialty.objects.create(code="fhir", name="FHIR")
    service = HospitalService.objects.create(code="fhir", name="FHIR")
    return Professional.objects.create(
        user=user,
        dni="70123456",
        registration_number="PR-FHIR-0001",
        license_number="MN 000001",
        first_name="Eva",
        last_name="Médica",
        date_of_birth=date(1985, 1, 1),
        specialty=specialty,
        hospital_service=service,
        registration_completed_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def _admission(patient: Patient, professional: Professional) -> Admission:
    admission = Admission.objects.create(
        patient=patient,
        professional=professional,
        consultation_reason="FHIR export",
        systolic_blood_pressure=120,
        diastolic_blood_pressure=80,
        heart_rate=72,
        temperature=Decimal("36.7"),
    )
    Admission.objects.filter(pk=admission.pk).update(
        created_at=datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
    )
    admission.refresh_from_db()
    return admission


def test_independent_profile_fixtures_cover_acceptance_and_rejection() -> None:
    valid = (FIXTURES_DIR / "independent-valid-observation.xml").read_bytes()
    validate_helixhealth_profile(valid)

    invalid = (FIXTURES_DIR / "invalid-wrong-unit.xml").read_bytes()
    with pytest.raises(FhirValidationError, match="UCUM unit"):
        validate_helixhealth_profile(invalid)

    for source, expected in (
        (valid.replace(b"8867-4", b"9999-9"), "Unsupported Observation code"),
        (
            b"urn:uuid:99999999-9999-4999-8999-999999999999".join(
                valid.rsplit(b"urn:uuid:30000000-0000-4000-8000-000000000001", 1)
            ),
            "must resolve",
        ),
        (
            valid.replace(b"<Observation>", b"<Condition>").replace(
                b"</Observation>", b"</Condition>"
            ),
            "Element",
        ),
    ):
        with pytest.raises(FhirValidationError, match=expected):
            validate_helixhealth_profile(source)


@pytest.mark.django_db
def test_admission_export_is_valid_escaped_stable_and_does_not_write() -> None:
    patient = _patient()
    professional = _professional()
    admission = _admission(patient, professional)
    count_before = Admission.objects.count()

    xml = serialize_admission_bundle([admission])
    repeated_xml = serialize_admission_bundle([admission])
    document = etree.fromstring(xml)

    assert xml.startswith(b"<?xml version='1.0' encoding='UTF-8'?>")
    assert FHIR_XML_MEDIA_TYPE == "application/fhir+xml; charset=utf-8"
    assert b"Ana &amp; Bea" in xml
    assert b"Garc\xc3\xada &lt;Test&gt;" in xml
    assert Admission.objects.count() == count_before
    assert (
        document.xpath(
            "string(f:entry[4]/f:resource/f:Observation/f:effectiveDateTime/@value)",
            namespaces=NS,
        )
        == "2026-09-15T12:00:00Z"
    )
    assert (
        document.xpath(
            "string(f:entry[4]/f:resource/f:Observation/f:component[1]/f:valueQuantity/f:unit/@value)",
            namespaces=NS,
        )
        == "mm[Hg]"
    )
    assert document.xpath("string(f:id/@value)", namespaces=NS) == etree.fromstring(
        repeated_xml
    ).xpath("string(f:id/@value)", namespaces=NS)
    validate_helixhealth_profile(xml)


def test_prescription_snapshot_export_preserves_every_supplied_value() -> None:
    patient = PatientSnapshot(
        identifier="HC-FHIR-01",
        dni="12345678",
        first_name="Ana",
        last_name="García",
        date_of_birth=date(1980, 4, 20),
    )
    prescriber = PractitionerSnapshot(
        identifier="PR-FHIR-0001",
        first_name="Eva",
        last_name="Médica",
        registration_number="PR-FHIR-0001",
    )
    prescription = PrescriptionSnapshot(
        identifier=UUID("50000000-0000-4000-8000-000000000001"),
        patient=patient,
        prescriber=prescriber,
        issued_at=datetime(2026, 9, 15, 13, 0, tzinfo=UTC),
        reason=CodingSnapshot(
            "http://snomed.info/sct", "20250901", "25064002", "Headache"
        ),
        items=(
            PrescriptionItemSnapshot(
                identifier="item-1",
                medication=CodingSnapshot(
                    "https://catalog.example/medications",
                    "2025",
                    "MED-1",
                    "Ibuprofen 400 mg",
                ),
                dose_value=Decimal("400"),
                dose_unit="mg",
                route="oral",
                frequency="every 8 hours",
                duration_days=5,
                instructions="with food",
            ),
            PrescriptionItemSnapshot(
                identifier="item-2",
                medication=CodingSnapshot(
                    "https://catalog.example/medications",
                    "2025",
                    "MED-2",
                    "Paracetamol 500 mg",
                ),
                dose_value=Decimal("500"),
                dose_unit="mg",
                route="oral",
                frequency="every 12 hours",
                duration_days=3,
            ),
        ),
    )

    xml = serialize_prescription_bundle(prescription)
    document = etree.fromstring(xml)
    requests = document.xpath("f:entry/f:resource/f:MedicationRequest", namespaces=NS)

    assert len(requests) == 2
    assert document.xpath("//f:Patient/f:identifier/f:value/@value", namespaces=NS) == [
        "12345678"
    ]
    assert document.xpath(
        "//f:Practitioner/f:identifier/f:value/@value", namespaces=NS
    ) == ["PR-FHIR-0001"]
    assert document.xpath(
        "//f:MedicationRequest/f:medicationCodeableConcept/f:coding/f:code/@value",
        namespaces=NS,
    ) == ["MED-1", "MED-2"]
    assert (
        document.xpath(
            "//f:MedicationRequest/f:groupIdentifier/f:value/@value", namespaces=NS
        )
        == [str(prescription.identifier)] * 2
    )
    assert document.xpath(
        "//f:MedicationRequest/f:reasonCode/f:coding/f:code/@value", namespaces=NS
    ) == ["25064002", "25064002"]
    assert document.xpath(
        "//f:MedicationRequest/f:dosageInstruction/f:doseAndRate/f:doseQuantity/f:value/@value",
        namespaces=NS,
    ) == ["400", "500"]
    validate_helixhealth_profile(xml)
