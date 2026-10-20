from django.db import models

from patients.models import Patient
from professionals.models import Professional


class AnonymizedImage(models.Model):
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="anonymized_images"
    )
    created_by = models.ForeignKey(
        Professional, on_delete=models.PROTECT, related_name="anonymized_images"
    )
    source_format = models.CharField(max_length=5)
    birth_year = models.PositiveSmallIntegerField(null=True, blank=True)
    study_year = models.PositiveSmallIntegerField(null=True, blank=True)
    sex = models.CharField(max_length=1, blank=True)
    dicom_bytes = models.BinaryField()
    preview_png = models.BinaryField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self) -> str:
        return f"Anonymized image {self.pk} for {self.patient}"
