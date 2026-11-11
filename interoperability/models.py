"""Immutable provenance for bounded external FHIR clinical exchange."""

from __future__ import annotations

import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone

from patients.models import Patient
from professionals.models import Professional


class ImportBatch(models.Model):
    """One accepted FHIR file, retained privately with its receipt provenance."""

    identifier = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="external_import_batches"
    )
    submitted_by = models.ForeignKey(
        Professional, on_delete=models.PROTECT, related_name="submitted_import_batches"
    )
    received_at = models.DateTimeField(default=timezone.now, editable=False)
    source_system = models.URLField(max_length=500)
    bundle_identifier = models.CharField(max_length=500)
    input_digest = models.CharField(max_length=64, editable=False)
    request_key = models.UUIDField(editable=False)
    raw_xml = models.BinaryField(editable=False)
    summary = models.JSONField(editable=False)
    records = models.ManyToManyField(
        "ExternalClinicalRecord",
        through="ImportBatchRecord",
        related_name="import_batches",
    )  # type: ignore[var-annotated]

    class Meta:
        ordering = ("-received_at", "-id")
        constraints = (
            models.UniqueConstraint(
                fields=("submitted_by", "patient", "request_key"),
                name="interop_batch_submitter_patient_request_key_unique",
            ),
            models.UniqueConstraint(
                fields=("patient", "source_system", "input_digest"),
                name="interop_batch_patient_source_digest_unique",
            ),
            models.CheckConstraint(
                condition=~Q(input_digest=""),
                name="interop_batch_digest_not_blank",
            ),
            models.CheckConstraint(
                condition=~Q(bundle_identifier=""),
                name="interop_batch_identifier_not_blank",
            ),
        )

    def __str__(self) -> str:
        return f"Import {self.identifier}"


class ExternalClinicalRecord(models.Model):
    """A normalized, externally asserted clinical resource; never a local event."""

    KIND_OBSERVATION = "observation"
    KIND_MEDICATION_REQUEST = "medication-request"
    KIND_CHOICES = (
        (KIND_OBSERVATION, "Observation"),
        (KIND_MEDICATION_REQUEST, "Medication request"),
    )

    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="external_clinical_records"
    )
    source_system = models.URLField(max_length=500)
    resource_type = models.CharField(max_length=40)
    external_identifier = models.CharField(max_length=255)
    kind = models.CharField(max_length=30, choices=KIND_CHOICES)
    source_recorded_at = models.DateTimeField()
    external_author = models.JSONField(editable=False)
    content = models.JSONField(editable=False)
    content_digest = models.CharField(max_length=64, editable=False)
    received_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ("-source_recorded_at", "-id")
        constraints = (
            models.UniqueConstraint(
                fields=("source_system", "resource_type", "external_identifier"),
                name="interop_external_source_resource_identifier_unique",
            ),
            models.CheckConstraint(
                condition=~Q(external_identifier=""),
                name="interop_external_identifier_not_blank",
            ),
            models.CheckConstraint(
                condition=~Q(content_digest=""),
                name="interop_external_digest_not_blank",
            ),
        )

    def __str__(self) -> str:
        return f"{self.resource_type} {self.external_identifier}"


class ImportBatchRecord(models.Model):
    """Membership preserves which resources were represented by one file."""

    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT)
    record = models.ForeignKey(ExternalClinicalRecord, on_delete=models.PROTECT)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("batch", "record"),
                name="interop_batch_record_unique",
            ),
        )

    def __str__(self) -> str:
        return f"{self.batch_id}:{self.record_id}"


class ImportedServiceRequest(models.Model):
    """A requested procedure received from FHIR, never a performed procedure."""

    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="imported_service_requests"
    )
    requester = models.ForeignKey(
        Professional, on_delete=models.PROTECT, related_name="imported_service_requests"
    )
    source_system = models.URLField(max_length=500)
    external_identifier = models.CharField(max_length=255)
    content_digest = models.CharField(max_length=64, editable=False)
    code_system = models.URLField(max_length=500)
    code = models.CharField(max_length=100)
    description = models.CharField(max_length=500)
    status = models.CharField(max_length=30)
    intent = models.CharField(max_length=30)
    authored_on = models.CharField(max_length=32)
    received_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ("-authored_on", "-id")
        constraints = (
            models.UniqueConstraint(
                fields=("source_system", "external_identifier"),
                name="interop_service_source_identifier_unique",
            ),
        )

    def __str__(self) -> str:
        return f"ServiceRequest {self.external_identifier}"


class ImportedMedicationRequest(models.Model):
    """A received medication order, separate from locally issued prescriptions."""

    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="imported_medication_requests"
    )
    requester = models.ForeignKey(
        Professional,
        on_delete=models.PROTECT,
        related_name="imported_medication_requests",
    )
    source_system = models.URLField(max_length=500)
    external_identifier = models.CharField(max_length=255)
    content_digest = models.CharField(max_length=64, editable=False)
    medication_display = models.CharField(max_length=500)
    medication_code_system = models.URLField(max_length=500, blank=True)
    medication_code = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=30)
    intent = models.CharField(max_length=30)
    authored_on = models.CharField(max_length=32)
    dosage_instructions = models.JSONField()
    dispense_quantity = models.JSONField(null=True, blank=True)
    notes = models.JSONField(default=list)
    received_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ("-authored_on", "-id")
        constraints = (
            models.UniqueConstraint(
                fields=("source_system", "external_identifier"),
                name="interop_medication_source_identifier_unique",
            ),
        )

    def __str__(self) -> str:
        return f"MedicationRequest {self.external_identifier}"


class JsonImportBatch(models.Model):
    """A privately retained FHIR JSON file and its transactional import result."""

    identifier = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="json_import_batches"
    )
    practitioner = models.ForeignKey(
        Professional, on_delete=models.PROTECT, related_name="json_import_batches"
    )
    submitted_by = models.ForeignKey(
        Professional,
        on_delete=models.PROTECT,
        related_name="submitted_json_import_batches",
    )
    source_system = models.URLField(max_length=500)
    bundle_identifier = models.CharField(max_length=500)
    request_key = models.UUIDField(editable=False)
    input_digest = models.CharField(max_length=64, editable=False)
    raw_json = models.BinaryField(editable=False)
    summary = models.JSONField(editable=False)
    received_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ("-received_at", "-id")
        constraints = (
            models.UniqueConstraint(
                fields=("submitted_by", "request_key"),
                name="interop_json_submitter_request_key_unique",
            ),
            models.UniqueConstraint(
                fields=("source_system", "input_digest"),
                name="interop_json_source_digest_unique",
            ),
        )

    def __str__(self) -> str:
        return f"JSON import {self.identifier}"
