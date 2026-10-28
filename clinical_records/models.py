from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from clinical_records.vital_signs import validate_vital_signs
from patients.models import Patient
from professionals.models import Professional


class Admission(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="admissions",
    )
    professional = models.ForeignKey(
        Professional,
        on_delete=models.PROTECT,
        related_name="admissions",
        null=True,
        blank=True,
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_admissions",
        null=True,
        blank=True,
    )
    consultation_reason = models.TextField()
    systolic_blood_pressure = models.PositiveSmallIntegerField()
    diastolic_blood_pressure = models.PositiveSmallIntegerField()
    heart_rate = models.PositiveSmallIntegerField()
    temperature = models.DecimalField(max_digits=4, decimal_places=1)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = (
            models.CheckConstraint(
                condition=Q(professional__isnull=False) | Q(recorded_by__isnull=False),
                name="admission_has_recorder",
            ),
            models.CheckConstraint(
                condition=~Q(consultation_reason=""),
                name="admission_reason_not_empty",
            ),
            models.CheckConstraint(
                condition=Q(systolic_blood_pressure__gt=0),
                name="admission_systolic_positive",
            ),
            models.CheckConstraint(
                condition=Q(diastolic_blood_pressure__gt=0),
                name="admission_diastolic_positive",
            ),
            models.CheckConstraint(
                condition=Q(heart_rate__gt=0),
                name="admission_heart_rate_positive",
            ),
            models.CheckConstraint(
                condition=Q(temperature__gt=0),
                name="admission_temperature_positive",
            ),
        )

    def __str__(self) -> str:
        return f"Admission {self.pk} for {self.patient}"

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        if not self.consultation_reason.strip():
            errors["consultation_reason"] = "Consultation reason is required."
        try:
            validate_vital_signs(
                {
                    "systolic_blood_pressure": self.systolic_blood_pressure,
                    "diastolic_blood_pressure": self.diastolic_blood_pressure,
                    "heart_rate": self.heart_rate,
                    "temperature": self.temperature,
                }
            )
        except ValidationError as error:
            errors.update(
                {
                    field_name: messages[0]
                    for field_name, messages in error.message_dict.items()
                }
            )
        if errors:
            raise ValidationError(errors)


class CareRelationship(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="care_relationships"
    )
    professional = models.ForeignKey(
        Professional, on_delete=models.PROTECT, related_name="care_relationships"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="care_assignments",
    )
    assigned_at = models.DateTimeField(auto_now_add=True, editable=False)
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="care_revocations",
    )

    class Meta:
        ordering = ("-assigned_at", "-id")
        constraints = (
            models.UniqueConstraint(
                fields=("patient", "professional"),
                condition=Q(is_active=True),
                name="unique_active_care_pair",
            ),
            models.CheckConstraint(
                condition=(
                    Q(is_active=True, revoked_at__isnull=True, revoked_by__isnull=True)
                    | Q(
                        is_active=False,
                        revoked_at__isnull=False,
                        revoked_by__isnull=False,
                    )
                ),
                name="care_revocation_consistent",
            ),
        )

    def __str__(self) -> str:
        return f"Care assignment {self.pk} for patient {self.patient_id}"
