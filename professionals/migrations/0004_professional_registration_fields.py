from typing import ClassVar

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q

import professionals.validators


class Migration(migrations.Migration):
    dependencies: ClassVar = [("professionals", "0003_professional_admission_identity")]

    operations: ClassVar = [
        migrations.AddField(
            model_name="professional",
            name="date_of_birth",
            field=models.DateField(
                blank=True,
                null=True,
                validators=[
                    professionals.validators.validate_professional_date_of_birth
                ],
            ),
        ),
        migrations.AddField(
            model_name="professional",
            name="dni",
            field=models.CharField(
                blank=True,
                max_length=8,
                null=True,
                validators=[professionals.validators.validate_professional_dni],
            ),
        ),
        migrations.AddField(
            model_name="professional",
            name="first_name",
            field=models.CharField(
                blank=True,
                max_length=150,
                null=True,
                validators=[professionals.validators.validate_professional_name],
            ),
        ),
        migrations.AddField(
            model_name="professional",
            name="hospital_service",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="professionals",
                to="professionals.hospitalservice",
            ),
        ),
        migrations.AddField(
            model_name="professional",
            name="last_name",
            field=models.CharField(
                blank=True,
                max_length=150,
                null=True,
                validators=[professionals.validators.validate_professional_name],
            ),
        ),
        migrations.AddField(
            model_name="professional",
            name="registration_completed_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="professional",
            name="registration_number",
            field=models.CharField(
                blank=True, editable=False, max_length=32, null=True, unique=True
            ),
        ),
        migrations.AddField(
            model_name="professional",
            name="specialty",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="professionals",
                to="professionals.specialty",
            ),
        ),
        migrations.AddConstraint(
            model_name="professional",
            constraint=models.CheckConstraint(
                condition=Q(("dni__isnull", True)) | Q(("dni__regex", "^[0-9]{7,8}$")),
                name="professional_dni_canonical_format",
            ),
        ),
        migrations.AddConstraint(
            model_name="professional",
            constraint=models.CheckConstraint(
                condition=Q(("registration_number__isnull", True))
                | ~Q(("registration_number", "")),
                name="professional_registration_number_not_empty",
            ),
        ),
        migrations.AddConstraint(
            model_name="professional",
            constraint=models.CheckConstraint(
                condition=Q(("registration_completed_at__isnull", True))
                | (
                    Q(("dni__isnull", False))
                    & Q(("registration_number__isnull", False))
                    & ~Q(("registration_number", ""))
                    & Q(("first_name__isnull", False))
                    & ~Q(("first_name", ""))
                    & Q(("last_name__isnull", False))
                    & ~Q(("last_name", ""))
                    & Q(("date_of_birth__isnull", False))
                    & Q(("specialty__isnull", False))
                    & Q(("hospital_service__isnull", False))
                ),
                name="professional_completed_profile_fields_present",
            ),
        ),
        migrations.AddConstraint(
            model_name="professional",
            constraint=models.UniqueConstraint(
                condition=Q(("dni__isnull", False), ("is_active", True)),
                fields=("dni",),
                name="unique_active_professional_dni",
            ),
        ),
    ]
