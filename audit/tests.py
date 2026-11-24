from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier

import pytest
from django.contrib import admin
from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, connections, transaction
from django.db.transaction import TransactionManagementError
from django.utils import timezone

from access_control.roles import ADMINISTRATIVE_GROUP
from audit.models import ClinicalAuditEvent
from audit.services import record_clinical_change
from clinical_records.models import Admission
from interoperability.models import ExternalClinicalRecord
from patients.models import Patient

pytestmark = pytest.mark.django_db(transaction=True, serialized_rollback=True)


@pytest.fixture
def recorder():
    user = User.objects.create_user("audit-recorder")
    user.groups.add(Group.objects.get_or_create(name=ADMINISTRATIVE_GROUP)[0])
    return user


@pytest.fixture
def patient():
    return Patient.objects.create(
        dni="16001234",
        first_name="Ari",
        last_name="Test",
        date_of_birth=date(1990, 1, 2),
    )


def admit(patient, recorder):
    return Admission.objects.create(
        recorded_by=recorder,
        patient=patient,
        consultation_reason="Follow-up",
        systolic_blood_pressure=118,
        diastolic_blood_pressure=78,
        heart_rate=68,
        temperature=Decimal("36.7"),
    )


def record_admission(source, recorder):
    return record_clinical_change(
        source=source,
        actor_id=recorder.pk,
        operation="create",
        operation_key="initial",
        after={"reason": source.consultation_reason, "temperature": source.temperature},
    )


def test_clinical_write_commits_with_attributed_event_and_exact_replay(
    patient, recorder
):
    start = timezone.now()
    with transaction.atomic():
        source = admit(patient, recorder)
        event = record_admission(source, recorder)
    event.refresh_from_db()
    assert Admission.objects.get(pk=source.pk).patient == event.patient == patient
    assert event.actor == recorder and start <= event.recorded_at <= timezone.now()
    assert (
        event.source_type,
        event.source_key,
        event.operation,
        event.operation_key,
    ) == ("clinical_records.admission", str(source.pk), "create", "initial")
    assert event.before == {} and event.after == {
        "reason": "Follow-up",
        "temperature": "36.7",
    }
    with transaction.atomic():
        assert record_admission(source, recorder).pk == event.pk
    with (
        pytest.raises(ValidationError, match="different audit event"),
        transaction.atomic(),
    ):
        source.consultation_reason = "Conflicting replay"
        source.save(update_fields=["consultation_reason"])
        record_admission(source, recorder)
    source.refresh_from_db()
    assert source.consultation_reason == "Follow-up"
    assert ClinicalAuditEvent.objects.count() == Admission.objects.count() == 1


@pytest.mark.parametrize("failure", ["audit", "clinical"])
def test_postgresql_rolls_back_both_sides(patient, recorder, failure):
    with pytest.raises(IntegrityError), transaction.atomic():
        source = admit(patient, recorder)
        if failure == "audit":
            # Deferred actor FK fails at commit, after both inserts succeeded.
            record_clinical_change(
                source=source,
                actor_id=-1,
                operation="create",
                operation_key="initial",
                after={"reason": "Follow-up"},
            )
        else:
            record_admission(source, recorder)
            Admission.objects.filter(pk=source.pk).update(heart_rate=0)
    assert not Admission.objects.exists()
    assert not ClinicalAuditEvent.objects.exists()


def test_distinct_source_operations_preserve_the_before_and_after_values(
    patient, recorder
):
    with transaction.atomic():
        first = admit(patient, recorder)
        original = record_admission(first, recorder)
        second = admit(patient, recorder)
        separate = record_admission(second, recorder)
    with transaction.atomic():
        previous_rate = first.heart_rate
        first.heart_rate = 72
        first.save(update_fields=["heart_rate"])
        correction = record_clinical_change(
            source=first,
            operation="correct",
            operation_key="revision-2",
            actor_id=recorder.pk,
            before={"heart_rate": previous_rate},
            after={"heart_rate": first.heart_rate},
        )
    correction.refresh_from_db()
    assert correction.before == {"heart_rate": 68}
    assert correction.after == {
        "heart_rate": Admission.objects.get(pk=first.pk).heart_rate
    }
    assert (
        original.operation_key == separate.operation_key
        and original.source_key != separate.source_key
    )
    assert ClinicalAuditEvent.objects.filter(source_key=str(first.pk)).count() == 2


def test_external_event_preserves_origin_and_immutable_version_references(patient):
    with transaction.atomic():
        source = ExternalClinicalRecord.objects.create(
            patient=patient,
            source_system="https://lab.example.test",
            resource_type="Observation",
            external_identifier="A17",
            kind="observation",
            source_recorded_at=timezone.now(),
            external_author={"name": "Example lab"},
            content={"value": "7"},
            content_digest="a" * 64,
        )
        event = record_clinical_change(
            source=source,
            operation="import",
            operation_key=source.content_digest,
            external_origin=source.source_system,
            after={"content_digest": source.content_digest},
        )
    event.refresh_from_db()
    assert event.actor_id is None and event.external_origin == source.source_system
    assert (
        event.source_type == "interoperability.externalclinicalrecord"
        and event.patient == patient
    )
    assert event.after == {"content_digest": source.content_digest}


def test_audit_requires_atomic_caller_attribution_and_evidence(patient, recorder):
    source = admit(patient, recorder)
    with pytest.raises(TransactionManagementError):
        record_admission(source, recorder)
    with pytest.raises(ValidationError, match="origin"), transaction.atomic():
        record_clinical_change(
            source=source,
            operation="create",
            operation_key="initial",
            after={"reason": "Follow-up"},
        )
    with pytest.raises(ValidationError, match="version"), transaction.atomic():
        record_clinical_change(
            source=source,
            operation="create",
            operation_key="initial",
            actor_id=recorder.pk,
        )
    assert not ClinicalAuditEvent.objects.exists()


def test_postgresql_rejects_instance_and_bulk_changes(patient, recorder):
    with transaction.atomic():
        event = record_admission(admit(patient, recorder), recorder)
    rows = ClinicalAuditEvent.objects.filter(pk=event.pk)
    event.operation = "replacement"
    for mutation in (
        event.save,
        lambda: rows.update(after={}),
        rows.delete,
        event.delete,
    ):
        with pytest.raises(IntegrityError, match="append-only"), transaction.atomic():
            mutation()
    event.refresh_from_db()
    assert event.operation == "create" and event.after["reason"] == "Follow-up"
    assert not admin.site.is_registered(ClinicalAuditEvent)
    assert not Permission.objects.filter(
        content_type__app_label="audit", content_type__model="clinicalauditevent"
    ).exists()


def test_concurrent_replays_get_one_event(patient, recorder):
    source = admit(patient, recorder)
    ready = Barrier(2, timeout=15)

    def append():
        try:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                (backend,) = cursor.fetchone()
                ready.wait()
                event = record_admission(source, recorder)
            return backend, event.pk
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        workers = [pool.submit(append) for _ in range(2)]
        first, second = (worker.result() for worker in workers)
    assert first[0] != second[0] and first[1] == second[1]
    assert ClinicalAuditEvent.objects.count() == 1
