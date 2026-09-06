from django.conf import settings
from django.db import models
from django.db.models import Q

from professionals.validators import (
    validate_professional_date_of_birth,
    validate_professional_dni,
    validate_professional_name,
)


class ActiveReferenceData(models.Model):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Specialty(ActiveReferenceData):
    class Meta(ActiveReferenceData.Meta):
        verbose_name_plural = "specialties"


class HospitalService(ActiveReferenceData):
    pass


class Professional(models.Model):
    """An identity which may be an incomplete legacy professional profile."""

    id = models.BigAutoField(primary_key=True, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="professional_profile",
    )
    is_active = models.BooleanField(default=True)
    dni = models.CharField(  # noqa: DJ001 - legacy identities require NULL.
        max_length=8,
        null=True,
        blank=True,
        validators=[validate_professional_dni],
    )
    registration_number = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )
    first_name = models.CharField(  # noqa: DJ001 - legacy identities require NULL.
        max_length=150,
        null=True,
        blank=True,
        validators=[validate_professional_name],
    )
    last_name = models.CharField(  # noqa: DJ001 - legacy identities require NULL.
        max_length=150,
        null=True,
        blank=True,
        validators=[validate_professional_name],
    )
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        validators=[validate_professional_date_of_birth],
    )
    specialty = models.ForeignKey(
        Specialty,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="professionals",
    )
    hospital_service = models.ForeignKey(
        HospitalService,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="professionals",
    )
    registration_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )

    class Meta:
        ordering = ("id",)
        constraints = (
            models.CheckConstraint(
                condition=Q(dni__isnull=True) | Q(dni__regex=r"^[0-9]{7,8}$"),
                name="professional_dni_canonical_format",
            ),
            models.CheckConstraint(
                condition=Q(registration_number__isnull=True)
                | ~Q(registration_number=""),
                name="professional_registration_number_not_empty",
            ),
            models.CheckConstraint(
                condition=Q(registration_completed_at__isnull=True)
                | (
                    Q(dni__isnull=False)
                    & Q(registration_number__isnull=False)
                    & ~Q(registration_number="")
                    & Q(first_name__isnull=False)
                    & ~Q(first_name="")
                    & Q(last_name__isnull=False)
                    & ~Q(last_name="")
                    & Q(date_of_birth__isnull=False)
                    & Q(specialty__isnull=False)
                    & Q(hospital_service__isnull=False)
                ),
                name="professional_completed_profile_fields_present",
            ),
            models.UniqueConstraint(
                fields=("dni",),
                condition=Q(is_active=True, dni__isnull=False),
                name="unique_active_professional_dni",
            ),
        )

    def __str__(self) -> str:
        return self.display_name

    @property
    def is_registration_complete(self) -> bool:
        """Whether every required registration value was persisted."""
        return bool(
            self.registration_completed_at
            and self.dni
            and self.registration_number
            and self.first_name
            and self.last_name
            and self.date_of_birth
            and self.specialty_id
            and self.hospital_service_id
        )

    @property
    def display_name(self) -> str:
        """A safe list label for complete and incomplete legacy profiles."""
        if self.first_name and self.last_name:
            return f"{self.last_name}, {self.first_name}"
        return self.user.get_username()

    @property
    def registration_status(self) -> str:
        if not self.is_registration_complete:
            return "incomplete"
        return "active" if self.is_active else "inactive"
