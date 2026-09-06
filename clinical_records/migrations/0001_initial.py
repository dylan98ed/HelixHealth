from typing import ClassVar

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies: ClassVar = [
        ("patients", "0003_defer_clinical_record_generation"),
        ("professionals", "0003_professional_admission_identity"),
    ]

    operations: ClassVar = [
        migrations.CreateModel(
            name="Admission",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("consultation_reason", models.TextField()),
                ("systolic_blood_pressure", models.PositiveSmallIntegerField()),
                ("diastolic_blood_pressure", models.PositiveSmallIntegerField()),
                ("heart_rate", models.PositiveSmallIntegerField()),
                (
                    "temperature",
                    models.DecimalField(decimal_places=1, max_digits=4),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, editable=False),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="admissions",
                        to="patients.patient",
                    ),
                ),
                (
                    "professional",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="admissions",
                        to="professionals.professional",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "-id"),
                "constraints": (
                    models.CheckConstraint(
                        condition=models.Q(
                            ("consultation_reason", ""),
                            _negated=True,
                        ),
                        name="admission_reason_not_empty",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("systolic_blood_pressure__gt", 0)),
                        name="admission_systolic_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("diastolic_blood_pressure__gt", 0)),
                        name="admission_diastolic_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("heart_rate__gt", 0)),
                        name="admission_heart_rate_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("temperature__gt", 0)),
                        name="admission_temperature_positive",
                    ),
                ),
            },
        ),
    ]
