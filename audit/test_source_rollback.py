"""An audit failure after the insert must unwind all clinical source rows."""

from uuid import uuid4

import pytest
from django.db.models.signals import post_save

from audit.models import ClinicalAuditEvent
from clinical_records.models import Admission
from clinical_records.services import create_admission
from clinical_records.test_admissions import admission_data
from interoperability.json_services import import_json_bundle
from interoperability.models import (
    ExternalClinicalRecord,
    ImportBatch,
    ImportBatchRecord,
    ImportedMedicationRequest,
    ImportedServiceRequest,
    JsonImportBatch,
)
from interoperability.services import import_external_bundle
from interoperability.test_importing import (
    FIXTURE,
    SOURCE_SYSTEM,
    actor,
    patient,
    professional,
)
from interoperability.test_json_services import _bundle, _raw
from patients.models import Patient
from prescriptions.models import Prescription, PrescriptionItem
from prescriptions.services import issue_prescription
from prescriptions.test_prescriptions import data, medication

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("operation", ["admission", "prescription", "xml", "json"])
def test_source_and_audit_rollback_together(user_factory, operation):
    user, _ = professional(user_factory)
    target = patient()
    if operation == "json":
        # Let the JSON bundle provision its own patient so rollback covers identity too.
        target.dni = "87654320"
        target.save(update_fields=["dni"])
    submitted = actor(user)
    events = []

    def fail(sender, instance, **kwargs):
        events.append(instance.source_type)
        if operation != "json" or len(events) == 2:
            raise RuntimeError("forced audit failure")

    post_save.connect(fail, sender=ClinicalAuditEvent)
    try:
        with pytest.raises(RuntimeError, match="forced audit failure"):
            if operation == "admission":
                create_admission(actor=submitted, patient=target, **admission_data())
            elif operation == "prescription":
                items = data(medication(user)) * 2
                issue_prescription(
                    actor=submitted,
                    patient=target,
                    request_key=uuid4(),
                    reason_entry_id=None,
                    items=items,
                )
            elif operation == "xml":
                import_external_bundle(
                    actor=submitted,
                    patient=target,
                    request_key=uuid4(),
                    source_system=SOURCE_SYSTEM,
                    xml=FIXTURE.read_bytes(),
                )
            else:
                import_json_bundle(
                    actor=submitted,
                    request_key=uuid4(),
                    source_system=SOURCE_SYSTEM,
                    raw_json=_raw(_bundle()),
                )
    finally:
        post_save.disconnect(fail, sender=ClinicalAuditEvent)
    assert events
    assert list(Patient.all_objects.values_list("pk", flat=True)) == [target.pk]
    for model in (
        ClinicalAuditEvent,
        Admission,
        Prescription,
        PrescriptionItem,
        ExternalClinicalRecord,
        ImportedMedicationRequest,
        ImportedServiceRequest,
        ImportBatch,
        ImportBatchRecord,
        JsonImportBatch,
    ):
        assert not model.objects.exists(), model._meta.label
