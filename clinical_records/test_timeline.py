from datetime import UTC, datetime
from uuid import uuid4

from django.urls import reverse

from clinical_records.care_services import assign_care_relationship
from clinical_records.models import Admission
from clinical_records.test_admissions import admission_data
from clinical_records.test_care_relationships import care_context as care_context
from clinical_records.timeline import chart_timeline
from interoperability.models import (
    ExternalClinicalRecord,
    ImportedMedicationRequest,
    ImportedServiceRequest,
)
from patients.models import Patient
from prescriptions.models import Prescription


def test_global_timeline_pages_order_clinical_dates_and_merge_only_matching_identities(
    care_context, client
):
    admin, medical, doctor, patient, coordinator = care_context
    assign_care_relationship(
        actor=coordinator, patient=patient, professional_dni=doctor.dni
    )
    moment = datetime(2026, 3, 2, 1, tzinfo=UTC)  # March 1 at 22:00 in the clinic.
    local = Admission.objects.create(
        patient=patient, recorded_by=admin, **admission_data()
    )
    Admission.objects.filter(pk=local.pk).update(created_at=moment)
    rx = Prescription.objects.create(
        patient=patient,
        prescriber=doctor,
        issued_at=moment,
        request_key=uuid4(),
        input_digest="a" * 64,
        snapshot={
            "items": [
                {
                    "medication": {"display": "Local tablet"},
                    "dose_value": "2",
                    "dose_unit": "mg",
                }
            ]
        },
        fhir_xml=b"",
    )

    def order(identifier, authored):
        return ImportedServiceRequest.objects.create(
            patient=patient,
            requester=doctor,
            source_system="https://partner.test",
            external_identifier=identifier,
            description=identifier,
            authored_on=authored,
        )

    date_only = order("Chest imaging", "2026-03-01")
    offset = order("Later instant", "2026-03-02T02:30:00+01:00")
    undated = order("Undated order", "")
    shared = dict(
        patient=patient,
        source_system="https://partner.test",
        external_identifier="shared",
    )
    earlier = datetime(2025, 2, 1, tzinfo=UTC)
    xml = dict(
        resource_type="MedicationRequest",
        kind="medication-request",
        source_recorded_at=earlier,
        external_author={},
        content={"medication": {"display": "External tablet"}},
        content_digest="b" * 64,
    )
    original = ExternalClinicalRecord.objects.create(**shared, **xml)
    separate = ExternalClinicalRecord.objects.create(
        **{**shared, "source_system": "https://other.test"}, **xml
    )
    medication = ImportedMedicationRequest.objects.create(
        **shared,
        requester=doctor,
        authored_on="2025-01-31",
        dosage_instructions=[{"text": "Original directions"}],
        medication_display="External tablet",
    )
    other = Patient.objects.create(
        dni="20121900",
        first_name="Other",
        last_name="Patient",
        date_of_birth=patient.date_of_birth,
    )
    foreign = ImportedServiceRequest.objects.create(
        patient=other, requester=doctor, description="Another patient's request"
    )
    entries = [
        entry
        for n in range(1, 5)
        for entry in chart_timeline(patient, str(n), page_size=2)
    ]
    assert [(e["kind"], e["pk"]) for e in entries] == [
        ("procedure", offset.pk),
        ("admission", local.pk),
        ("prescription", rx.pk),
        ("procedure", date_only.pk),
        ("external", separate.pk),
        ("medication", medication.pk),
        ("procedure", undated.pk),
    ]
    assert (
        entries[3]["date"] == "2026-03-01" and entries[-1]["date"] == "Date unavailable"
    )
    assert entries[1]["recorder"] == admin.username and not entries[1]["author"]
    assert (
        entries[2]["summary"] == "Local tablet"
        and entries[2]["author"] == doctor.display_name
    )
    client.force_login(medical)
    assert (
        client.get(
            reverse(
                "clinical_records:timeline-source",
                args=[patient.pk, "external", original.pk],
            )
        ).status_code
        == 200
    )
    for entry in entries:
        response = client.get(entry["url"])
        assert response.status_code == 200
        assert b"Another patient's request" not in response.content
    assert b"2 mg" in client.get(entries[2]["url"]).content
    assert b"Original directions" in client.get(entries[5]["url"]).content
    assert (
        client.get(
            reverse(
                "clinical_records:timeline-source",
                args=[patient.pk, "procedure", foreign.pk],
            )
        ).status_code
        == 404
    )
    assert (
        client.get(
            reverse(
                "clinical_records:timeline-source",
                args=[other.pk, "procedure", foreign.pk],
            )
        ).status_code
        == 403
    )
