"""Append-only clinical terminology and medication catalog entries."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class SourceVersionedEntry(models.Model):
    """A catalog identity supplied by a named source and immutable version."""

    system = models.URLField(max_length=500)
    version = models.CharField(max_length=100)
    code = models.CharField(max_length=255)
    source_label = models.CharField(max_length=200)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)s_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        abstract = True
        constraints = (
            models.CheckConstraint(
                condition=Q(system__regex=r".*\S.*"),
                name="%(app_label)s_%(class)s_system_not_blank",
            ),
            models.CheckConstraint(
                condition=Q(version__regex=r".*\S.*"),
                name="%(app_label)s_%(class)s_version_not_blank",
            ),
            models.CheckConstraint(
                condition=Q(code__regex=r".*\S.*"),
                name="%(app_label)s_%(class)s_code_not_blank",
            ),
            models.CheckConstraint(
                condition=Q(source_label__regex=r".*\S.*"),
                name="%(app_label)s_%(class)s_source_label_not_blank",
            ),
            models.UniqueConstraint(
                fields=("system", "version", "code"),
                name="%(app_label)s_%(class)s_source_version_code_unique",
            ),
        )

    def clean(self) -> None:
        super().clean()
        fields = ("system", "version", "code", "source_label")
        errors = {
            field: "This field cannot be blank."
            for field in fields
            if not str(getattr(self, field)).strip()
        }
        if errors:
            raise ValidationError(errors)


class TerminologyEntry(SourceVersionedEntry):
    display = models.CharField(max_length=500)

    class Meta(SourceVersionedEntry.Meta):
        ordering = ("display", "id")
        constraints = SourceVersionedEntry.Meta.constraints + (  # type: ignore[assignment]
            models.CheckConstraint(
                condition=Q(display__regex=r".*\S.*"),
                name="catalogs_terminologyentry_display_not_blank",
            ),
        )

    def __str__(self) -> str:
        return f"{self.code} — {self.display} ({self.version})"

    def clean(self) -> None:
        super().clean()
        if not self.display.strip():
            raise ValidationError({"display": "This field cannot be blank."})


class MedicationEntry(SourceVersionedEntry):
    name = models.CharField(max_length=500)
    presentation = models.CharField(max_length=500)
    terminology_entry = models.ForeignKey(
        TerminologyEntry,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="medications",
    )

    class Meta(SourceVersionedEntry.Meta):
        ordering = ("name", "id")
        constraints = SourceVersionedEntry.Meta.constraints + (  # type: ignore[assignment]
            models.CheckConstraint(
                condition=Q(name__regex=r".*\S.*"),
                name="catalogs_medicationentry_name_not_blank",
            ),
            models.CheckConstraint(
                condition=Q(presentation__regex=r".*\S.*"),
                name="catalogs_medicationentry_presentation_not_blank",
            ),
        )

    def __str__(self) -> str:
        return f"{self.code} — {self.name} ({self.version})"

    def clean(self) -> None:
        super().clean()
        errors = {
            field: "This field cannot be blank."
            for field in ("name", "presentation")
            if not str(getattr(self, field)).strip()
        }
        if errors:
            raise ValidationError(errors)
