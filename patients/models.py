from django.db import models
from django.db.models import Q


class Patient(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    dni = models.CharField(max_length=8)
    clinical_record_number = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField()
    sex = models.CharField(max_length=20)
    phone = models.CharField(max_length=32)
    email = models.EmailField()
    address = models.TextField()
    health_insurer = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=Q(dni__regex=r"^[0-9]{7,8}$"),
                name="patient_dni_canonical_format",
            ),
            models.CheckConstraint(
                condition=~Q(clinical_record_number=""),
                name="patient_clinical_record_not_empty",
            ),
            models.UniqueConstraint(
                fields=("dni",),
                condition=Q(is_active=True),
                name="unique_active_patient_dni",
            ),
        )
        ordering = ("last_name", "first_name", "id")

    def __str__(self) -> str:
        return f"{self.last_name}, {self.first_name} ({self.dni})"
