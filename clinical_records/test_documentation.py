from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, connections, transaction
from django.urls import reverse
from django.utils import timezone

from access_control.actors import actor_context_from_user
from audit.models import ClinicalAuditEvent
from clinical_records.care_services import (
    assign_care_relationship,
    revoke_care_relationship,
)
from clinical_records.documentation import (
    DocumentationConflict,
    add_progress_note,
    save_consultation,
    save_history,
)
from clinical_records.models import (
    Consultation,
    HistoryEntry,
    HistoryRevision,
    ProgressNote,
)
from clinical_records.test_care_relationships import care_context as care_context
from patients.models import Patient


@pytest.fixture
def assigned(care_context):
    _, user, doctor, patient, coordinator = care_context
    team, _ = assign_care_relationship(
        actor=coordinator, patient=patient, professional_dni=doctor.dni
    )
    return dict(actor=actor_context_from_user(user), patient_pk=patient.pk), team


def test_consultation_and_note_retries_validation_and_revocation(
    assigned, care_context, client
):
    scope, team = assigned
    _, user, doctor, patient, coordinator = care_context
    client.force_login(user)
    values = dict(
        operation_key=uuid4(),
        visited_at=timezone.now(),
        reason="Review",
        initial_evolution="Initial report",
    )
    with pytest.raises(ValidationError):
        save_consultation(**scope, **{**values, "reason": " "})
    assert not Consultation.objects.exists() and not ClinicalAuditEvent.objects.exists()
    url = reverse("clinical_records:new-consultation", args=[patient.pk])
    posted = {
        **values,
        "visited_at": "2026-03-04T11:32",
        "author": user.pk + 1,
        "patient_pk": patient.pk + 1,
    }
    for _ in range(2):
        assert client.post(url, posted).status_code == 302
    visit = Consultation.objects.get()
    assert (
        visit.author == doctor
        and visit.patient == patient
        and visit.visited_at.hour == 14
    )
    note_values = dict(
        consultation_pk=visit.pk, operation_key=uuid4(), text="Follow-up"
    )
    note = add_progress_note(**scope, **note_values)
    assert add_progress_note(**scope, **note_values) == note
    assert ProgressNote.objects.get() == note and note.author == doctor
    with pytest.raises(DocumentationConflict):
        add_progress_note(**scope, **{**note_values, "text": "Changed retry"})
    with pytest.raises(ValidationError):
        add_progress_note(**scope, **{**note_values, "text": " "})
    with pytest.raises(IntegrityError, match="append-only"), transaction.atomic():
        ProgressNote.objects.update(text="Replacement")
    assert set(
        ClinicalAuditEvent.objects.values_list(
            "source_type", "source_key", "actor_id", "patient_id"
        )
    ) == {
        ("clinical_records.consultation", str(visit.pk), user.pk, patient.pk),
        ("clinical_records.progressnote", str(note.pk), user.pk, patient.pk),
    }
    revoke_care_relationship(
        actor=coordinator, patient=patient, relationship=team, confirmed=True
    )
    with pytest.raises(PermissionDenied):
        add_progress_note(**scope, **note_values)
    assert client.post(url, posted).status_code == 403


def test_history_revision_scope_replay_and_immutable_evidence(
    assigned, care_context, client
):
    scope, team = assigned
    _, user, doctor, patient, coordinator = care_context
    values = dict(
        category="family",
        relationship="Mother",
        description="Original",
        expected_version=0,
        operation_key=uuid4(),
    )
    with pytest.raises(ValidationError):
        save_history(**scope, **{**values, "relationship": ""})
    entry = save_history(**scope, **values)
    assert save_history(**scope, **values) == entry
    correction = {
        **values,
        "description": "Corrected",
        "relationship": "Sister",
        "entry_pk": entry.pk,
        "operation_key": uuid4(),
        "expected_version": 1,
    }
    save_history(**scope, **correction)
    assert save_history(**scope, **correction) == entry
    with pytest.raises(ValidationError):
        save_history(**scope, **{**correction, "description": " "})
    with pytest.raises(DocumentationConflict):
        save_history(**scope, **{**correction, "operation_key": uuid4()})
    current, previous = entry.revisions.all()
    assert (previous.description, previous.relationship, previous.author) == (
        "Original",
        "Mother",
        doctor,
    )
    assert (current.description, current.relationship, current.author) == (
        "Corrected",
        "Sister",
        doctor,
    )
    event = ClinicalAuditEvent.objects.get(operation="revise")
    assert event.before == {"revision_id": previous.pk} and event.after == {
        "revision_id": current.pk
    }
    with pytest.raises(IntegrityError, match="append-only"), transaction.atomic():
        HistoryRevision.objects.filter(pk=previous.pk).update(description="Rewrite")
    other = Patient.objects.create(
        dni="12345679",
        first_name="Other",
        last_name="Patient",
        date_of_birth=patient.date_of_birth,
    )
    assign_care_relationship(
        actor=coordinator, patient=other, professional_dni=doctor.dni
    )
    client.force_login(user)
    wrong = reverse(
        "clinical_records:edit-history", args=[other.pk, "family", entry.pk]
    )
    assert (
        client.get(wrong).status_code
        == client.post(wrong, correction).status_code
        == 404
    )
    assert HistoryEntry.objects.count() == 1 and ClinicalAuditEvent.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_two_postgresql_editors_can_commit_only_one_revision(assigned):
    scope, _ = assigned
    values = dict(
        category="personal",
        relationship="",
        description="Original",
        expected_version=0,
        operation_key=uuid4(),
    )
    entry = save_history(**scope, **values)
    start = Barrier(2, timeout=15)

    def edit(description):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                (backend,) = cursor.fetchone()
            start.wait()
            try:
                save_history(
                    **scope,
                    **{
                        **values,
                        "entry_pk": entry.pk,
                        "description": description,
                        "expected_version": 1,
                        "operation_key": uuid4(),
                    },
                )
            except DocumentationConflict:
                return backend, None
            return backend, description
        finally:
            connections.close_all()

    with ThreadPoolExecutor(2) as pool:
        first, second = pool.map(edit, ["First editor", "Second editor"])
    assert first[0] != second[0]
    assert [value for _, value in (first, second) if value] == [
        entry.revisions.get(version=2).description
    ]
    assert entry.revisions.count() == ClinicalAuditEvent.objects.count() == 2
