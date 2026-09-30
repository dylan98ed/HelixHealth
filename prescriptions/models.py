"""Immutable medication prescription records."""

from __future__ import annotations

import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone

from catalogs.models import MedicationEntry, TerminologyEntry
from patients.models import Patient
from professionals.models import Professional


class Prescription(models.Model):
    """An issued prescription, including the content shown to recipients."""

    identifier = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="prescriptions"
    )
    prescriber = models.ForeignKey(
        Professional, on_delete=models.PROTECT, related_name="prescriptions"
    )
    issued_at = models.DateTimeField(default=timezone.now, editable=False)
    request_key = models.UUIDField(editable=False)
    input_digest = models.CharField(max_length=64, editable=False)
    reason_entry = models.ForeignKey(
        TerminologyEntry,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="prescription_reasons",
    )
    snapshot = models.JSONField(editable=False)
    fhir_xml = models.BinaryField(editable=False)

    class Meta:
        ordering = ("-issued_at", "-id")
        constraints = (
            models.UniqueConstraint(
                fields=("prescriber", "patient", "request_key"),
                name="prescription_prescriber_patient_request_key_unique",
            ),
            models.CheckConstraint(
                condition=~Q(input_digest=""),
                name="prescription_input_digest_not_blank",
            ),
        )

    def __str__(self) -> str:
        return f"Prescription {self.identifier}"


class PrescriptionItem(models.Model):
    """One immutable medication direction belonging to an issued prescription."""

    prescription = models.ForeignKey(
        Prescription, on_delete=models.PROTECT, related_name="items"
    )
    sequence = models.PositiveSmallIntegerField()
    medication = models.ForeignKey(
        MedicationEntry, on_delete=models.PROTECT, related_name="prescription_items"
    )
    snapshot = models.JSONField(editable=False)
    dose_value = models.DecimalField(max_digits=12, decimal_places=4)
    dose_unit = models.CharField(max_length=100)
    route = models.CharField(max_length=100)
    frequency = models.CharField(max_length=500)
    duration_days = models.PositiveSmallIntegerField()
    instructions = models.TextField(blank=True, max_length=2000)

    class Meta:
        ordering = ("sequence", "id")
        constraints = (
            models.UniqueConstraint(
                fields=("prescription", "sequence"),
                name="prescription_item_sequence_unique",
            ),
            models.CheckConstraint(
                condition=Q(dose_value__gt=0),
                name="prescription_item_dose_positive",
            ),
            models.CheckConstraint(
                condition=Q(duration_days__gte=1) & Q(duration_days__lte=365),
                name="prescription_item_duration_in_range",
            ),
            models.CheckConstraint(
                condition=Q(dose_unit__regex=r".*\S.*"),
                name="prescription_item_dose_unit_not_blank",
            ),
            models.CheckConstraint(
                condition=Q(route__regex=r".*\S.*"),
                name="prescription_item_route_not_blank",
            ),
            models.CheckConstraint(
                condition=Q(frequency__regex=r".*\S.*"),
                name="prescription_item_frequency_not_blank",
            ),
        )

    def __str__(self) -> str:
        return f"{self.prescription.identifier} item {self.sequence}"
