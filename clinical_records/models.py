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
