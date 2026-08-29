from typing import ClassVar

from django.db import migrations, models

import patients.validators


class Migration(migrations.Migration):
    initial = True

    dependencies: ClassVar = []

    operations: ClassVar = [
        migrations.CreateModel(
            name="Patient",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "dni",
                    models.CharField(
                        max_length=8,
                        validators=[patients.validators.validate_patient_dni],
                    ),
                ),
                (
                    "clinical_record_number",
                    models.CharField(editable=False, max_length=32, unique=True),
                ),
                (
                    "first_name",
                    models.CharField(
                        max_length=150,
                        validators=[patients.validators.validate_not_blank],
                    ),
                ),
                (
                    "last_name",
                    models.CharField(
                        max_length=150,
                        validators=[patients.validators.validate_not_blank],
                    ),
                ),
                (
                    "date_of_birth",
                    models.DateField(
                        validators=[patients.validators.validate_date_of_birth]
                    ),
                ),
                (
                    "sex",
                    models.CharField(
                        max_length=20,
                        validators=[patients.validators.validate_not_blank],
                    ),
                ),
                (
                    "phone",
                    models.CharField(
                        max_length=32,
                        validators=[patients.validators.validate_phone],
                    ),
                ),
                ("email", models.EmailField(max_length=254)),
                (
                    "address",
                    models.TextField(
                        validators=[patients.validators.validate_not_blank]
                    ),
                ),
                (
                    "health_insurer",
                    models.CharField(
                        max_length=150,
                        validators=[patients.validators.validate_not_blank],
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ("last_name", "first_name", "id"),
                "base_manager_name": "all_objects",
                "default_manager_name": "objects",
                "constraints": (
                    models.CheckConstraint(
                        condition=models.Q(("dni__regex", "^[0-9]{7,8}$")),
                        name="patient_dni_canonical_format",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("clinical_record_number", ""),
                            _negated=True,
                        ),
                        name="patient_clinical_record_not_empty",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("is_active", True)),
                        fields=("dni",),
                        name="unique_active_patient_dni",
                    ),
                ),
            },
            managers=[
                ("objects", models.Manager()),
                ("all_objects", models.Manager()),
            ],
        ),
    ]
