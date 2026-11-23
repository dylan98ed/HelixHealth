from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone

from access_control.actors import actor_context_from_user
from appointments.availability import lock_schedule
from clinical_records.care_services import (
    assign_care_relationship,
    revoke_care_relationship,
)
from clinical_records.chart_access import chart_assignment, chart_assignments
from clinical_records.models import Admission
from clinical_records.services import create_admission
from clinical_records.test_admissions import admission_data
from clinical_records.test_care_relationships import care_context as care_context
from interoperability.models import ExternalClinicalRecord, JsonImportBatch
from patients.models import Patient
from professionals.models import Professional


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("workflow", ["booking", "chart"])
def test_locked_identity_allows_another_patients_admission(care_context, workflow):
    _, medical, doctor, patient, coordinator = care_context
    actor = actor_context_from_user(medical)
    assign_care_relationship(
        actor=coordinator, patient=patient, professional_dni=doctor.dni
    )
    other = Patient.objects.create(
        dni="12345677",
        first_name="Other",
        last_name="Patient",
        date_of_birth=patient.date_of_birth,
    )

    def record_other_admission():
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '3s'")
                return create_admission(
                    actor=actor, patient=other, **admission_data()
                ).pk
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            if workflow == "booking":
                lock_schedule(medical.pk, {doctor.pk})
            else:
                chart_assignment(actor, patient.pk, for_update=True)
            admission_pk = pool.submit(record_other_admission).result(timeout=10)
    assert Admission.objects.filter(
        pk=admission_pk, patient=other, recorded_by=medical
    ).exists()


def test_revocation_removes_fhir_history_including_files_retries_and_exports(
    care_context, client
):
    _, medical, doctor, patient, coordinator = care_context
    assignment, _ = assign_care_relationship(
        actor=coordinator, patient=patient, professional_dni=doctor.dni
    )
    batch = JsonImportBatch.objects.create(
        patient=patient,
        practitioner=doctor,
        submitted_by=doctor,
        source_system="https://exchange.test",
        request_key=uuid4(),
        input_digest="a" * 64,
        raw_json=b"{}",
        summary={},
    )
    client.force_login(medical)
    form = reverse("interoperability:json-import-upload")
    detail = reverse("interoperability:json-import-detail", args=[batch.identifier])
    raw = reverse("interoperability:json-import-file", args=[batch.identifier])
    assert str(batch.identifier).encode() in client.get(form).content
    assert client.get(detail).status_code == client.get(raw).status_code == 200
    revoke_care_relationship(
        actor=coordinator, patient=patient, relationship=assignment, confirmed=True
    )
    assert str(batch.identifier).encode() not in client.get(form).content
    assert client.get(form, {"retry": batch.identifier}).status_code == 404
    assert client.get(detail).status_code == client.get(raw).status_code == 404
    for route in ("prescriptions:api-list", "interoperability:api-imports"):
        assert client.get(reverse(route, args=[patient.pk])).status_code == 403
    for route, payload in [
        ("interoperability:api-export", {"admission_ids": [1]}),
        ("interoperability:api-json-export", {"observation_ids": [1]}),
    ]:
        assert (
            client.post(
                reverse(route, args=[patient.pk]),
                payload,
                content_type="application/json",
            ).status_code
            == 403
        )


def test_chart_with_only_external_history(care_context, client):
    _, medical, doctor, patient, coordinator = care_context
    assign_care_relationship(
        actor=coordinator, patient=patient, professional_dni=doctor.dni
    )
    ExternalClinicalRecord.objects.create(
        patient=patient,
        source_system="https://lab.example.test",
        resource_type="Observation",
        external_identifier="pulse-1",
        kind="observation",
        source_recorded_at=timezone.now(),
        external_author={"given": "Lab"},
        content_digest="a" * 64,
        content={"coding": {"display": "Pulse rate"}, "value": "68", "unit": "bpm"},
    )
    client.force_login(medical)
    result = client.get(reverse("clinical_records:chart", args=[patient.pk]))
    assert b"Pulse rate" in result.content and b"68 bpm" in result.content
    assert b"No clinical records" not in result.content


def test_chart_directory_scopes_partial_search_and_detail_to_patient(
    care_context, client
):
    admin, medical, doctor, patient, coordinator = care_context
    other = Patient.objects.create(
        dni="12345677",
        first_name="Unassigned",
        last_name="Patient",
        date_of_birth=patient.date_of_birth,
    )
    foreign = Admission.objects.create(
        patient=other, recorded_by=admin, **admission_data()
    )
    directory = reverse("clinical_records:assigned-charts")
    chart = reverse("clinical_records:chart", args=[patient.pk])
    assert client.get(chart).status_code == 302
    client.force_login(medical)
    assign_care_relationship(
        actor=coordinator, patient=patient, professional_dni=doctor.dni
    )
    partial = client.get(
        directory,
        {"q": "Patient"},
        headers={"HX-Request": "true", "HX-Target": "patient-directory"},
    )
    assert (
        patient.dni.encode() in partial.content
        and other.dni.encode() not in partial.content
    )
    assert "no-store" in partial.headers["Cache-Control"]
    assert (
        client.get(reverse("clinical_records:chart", args=[other.pk])).status_code
        == 403
    )
    assert (
        client.get(
            reverse("clinical_records:chart-admission", args=[patient.pk, foreign.pk])
        ).status_code
        == 404
    )
    own = Admission.objects.create(
        patient=patient, recorded_by=admin, **admission_data()
    )
    assert own.consultation_reason.encode() in client.get(chart).content
    assert (
        client.get(
            reverse("clinical_records:chart-admission", args=[patient.pk, own.pk])
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "change",
    [
        "revoke",
        "remove_role",
        "inactive_profile",
        "incomplete_profile",
        "inactive_patient",
        "inactive_account",
    ],
)
def test_chart_reads_and_write_guard_recheck_eligibility(care_context, client, change):
    _, medical, doctor, patient, coordinator = care_context
    assignment, _ = assign_care_relationship(
        actor=coordinator, patient=patient, professional_dni=doctor.dni
    )
    actor = actor_context_from_user(medical)
    client.force_login(medical)
    with transaction.atomic():
        assert chart_assignment(actor, patient.pk, for_update=True).pk == assignment.pk
    if change == "revoke":
        revoke_care_relationship(
            actor=coordinator, patient=patient, relationship=assignment, confirmed=True
        )
    elif change == "remove_role":
        medical.groups.clear()
    elif change == "inactive_profile":
        Professional.objects.filter(pk=doctor.pk).update(is_active=False)
    elif change == "incomplete_profile":
        Professional.objects.filter(pk=doctor.pk).update(registration_completed_at=None)
    elif change == "inactive_patient":
        Patient.objects.filter(pk=patient.pk).update(is_active=False)
    else:
        medical.is_active = False
        medical.save(update_fields=["is_active"])
    assert not chart_assignments(actor).exists()
    with pytest.raises(PermissionDenied), transaction.atomic():
        chart_assignment(actor, patient.pk, for_update=True)
    response = client.get(reverse("clinical_records:chart", args=[patient.pk]))
    assert response.status_code == (302 if change == "inactive_account" else 403)
    assert patient.clinical_record_number.encode() not in response.content
