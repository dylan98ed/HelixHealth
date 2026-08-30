from collections.abc import Iterable
from typing import Any

from django.db import models
from django.db.models import Q

from patients.identifiers import generate_clinical_record_number
from patients.validators import (
    validate_date_of_birth,
    validate_not_blank,
    validate_patient_dni,
    validate_phone,
)


class ActivePatientManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class Patient(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    dni = models.CharField(max_length=8, validators=[validate_patient_dni])
    clinical_record_number = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
    )
    first_name = models.CharField(max_length=150, validators=[validate_not_blank])
    last_name = models.CharField(max_length=150, validators=[validate_not_blank])
    date_of_birth = models.DateField(validators=[validate_date_of_birth])
    sex = models.CharField(max_length=20, validators=[validate_not_blank])
    phone = models.CharField(max_length=32, validators=[validate_phone])
    email = models.EmailField()
    address = models.TextField(validators=[validate_not_blank])
    health_insurer = models.CharField(
        max_length=150,
        validators=[validate_not_blank],
    )
    is_active = models.BooleanField(default=True)

    objects = ActivePatientManager()
    all_objects = models.Manager()  # noqa: DJ012 - both declarations are managers.

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
        base_manager_name = "all_objects"
        default_manager_name = "objects"

    def __str__(self) -> str:
        return f"{self.last_name}, {self.first_name} ({self.dni})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self._state.adding and not self.clinical_record_number:
            self.clinical_record_number = generate_clinical_record_number()
        super().save(*args, **kwargs)

    def full_clean(
        self,
        exclude: Iterable[str] | None = None,
        validate_unique: bool = True,
        validate_constraints: bool = True,
    ) -> None:
        excluded_fields = set(exclude or ())
        if self._state.adding and not self.clinical_record_number:
            excluded_fields.add("clinical_record_number")
        super().full_clean(
            exclude=excluded_fields,
            validate_unique=validate_unique,
            validate_constraints=validate_constraints,
        )
