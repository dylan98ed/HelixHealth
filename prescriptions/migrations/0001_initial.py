import uuid
from typing import ClassVar

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    initial = True

    dependencies: ClassVar = [
        ("catalogs", "0001_add_reference_catalog_entries"),
        ("patients", "0003_defer_clinical_record_generation"),
        ("professionals", "0007_specialty_unique_specialty_name_case_insensitive"),
    ]

    operations: ClassVar = [
        migrations.CreateModel(
            name="Prescription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "identifier",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                (
                    "issued_at",
                    models.DateTimeField(default=timezone.now, editable=False),
                ),
                ("request_key", models.UUIDField(editable=False)),
                ("input_digest", models.CharField(editable=False, max_length=64)),
                ("snapshot", models.JSONField(editable=False)),
                ("fhir_xml", models.BinaryField(editable=False)),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="prescriptions",
                        to="patients.patient",
                    ),
                ),
                (
                    "prescriber",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="prescriptions",
                        to="professionals.professional",
                    ),
                ),
                (
                    "reason_entry",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="prescription_reasons",
                        to="catalogs.terminologyentry",
                    ),
                ),
            ],
            options={"ordering": ("-issued_at", "-id")},
        ),
        migrations.CreateModel(
            name="PrescriptionItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("sequence", models.PositiveSmallIntegerField()),
                ("snapshot", models.JSONField(editable=False)),
                ("dose_value", models.DecimalField(decimal_places=4, max_digits=12)),
                ("dose_unit", models.CharField(max_length=100)),
                ("route", models.CharField(max_length=100)),
                ("frequency", models.CharField(max_length=500)),
                ("duration_days", models.PositiveSmallIntegerField()),
                ("instructions", models.TextField(blank=True, max_length=2000)),
                (
                    "medication",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="prescription_items",
                        to="catalogs.medicationentry",
                    ),
                ),
                (
                    "prescription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="items",
                        to="prescriptions.prescription",
                    ),
                ),
            ],
            options={"ordering": ("sequence", "id")},
        ),
        migrations.AddConstraint(
            model_name="prescription",
            constraint=models.UniqueConstraint(
                fields=("prescriber", "patient", "request_key"),
                name="prescription_prescriber_patient_request_key_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="prescription",
            constraint=models.CheckConstraint(
                condition=models.Q(("input_digest", ""), _negated=True),
                name="prescription_input_digest_not_blank",
            ),
        ),
        migrations.AddConstraint(
            model_name="prescriptionitem",
            constraint=models.UniqueConstraint(
                fields=("prescription", "sequence"),
                name="prescription_item_sequence_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="prescriptionitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("dose_value__gt", 0)),
                name="prescription_item_dose_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="prescriptionitem",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("duration_days__gte", 1), ("duration_days__lte", 365)
                ),
                name="prescription_item_duration_in_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="prescriptionitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("dose_unit__regex", r".*\S.*")),
                name="prescription_item_dose_unit_not_blank",
            ),
        ),
        migrations.AddConstraint(
            model_name="prescriptionitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("route__regex", r".*\S.*")),
                name="prescription_item_route_not_blank",
            ),
        ),
        migrations.AddConstraint(
            model_name="prescriptionitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("frequency__regex", r".*\S.*")),
                name="prescription_item_frequency_not_blank",
            ),
        ),
    ]
