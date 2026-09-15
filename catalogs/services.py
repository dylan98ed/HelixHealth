"""Transactional catalog lifecycle and append-only ingestion services."""

import json
from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from access_control.actors import ActorContext
from access_control.policies import ADMINISTRATIVE_POLICY
from catalogs.models import MedicationEntry, TerminologyEntry
from professionals.models import Professional, Specialty

MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_IMPORT_ROWS = 500

CatalogModel = type[TerminologyEntry] | type[MedicationEntry]


class CatalogConflictError(ValueError):
    """A requested catalog change conflicts with immutable persisted data."""


class CatalogInputError(ValueError):
    """Normalized import input errors, including per-row field failures."""

    def __init__(self, errors: dict[str, object]) -> None:
        super().__init__("Catalog import contains invalid entries.")
        self.errors = errors


@dataclass(frozen=True)
class ImportResult:
    created: int
    unchanged: int


def require_administrative_actor(actor: ActorContext | None) -> ActorContext:
    """Require a currently active account in the administrative role."""
    authorized = ADMINISTRATIVE_POLICY.require(actor)
    if (
        not get_user_model()
        .objects.filter(
            pk=authorized.user_id,
            is_active=True,
            groups__name=ADMINISTRATIVE_POLICY.required_role.value,
        )
        .exists()
    ):
        raise PermissionDenied("An active administrative account is required.")
    return authorized


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not (result := value.strip()):
        raise ValidationError({field: "This field is required."})
    return result


def _specialty_validation_error(
    error: ValidationError,
) -> CatalogConflictError | ValidationError:
    if {"code", "name"} & set(error.message_dict):
        return CatalogConflictError("Specialty code and name must be unique.")
    return error


def _specialty_conflict(*, code: str, name: str, exclude_pk: int | None = None) -> bool:
    specialties = Specialty.objects.filter(code=code) | Specialty.objects.filter(
        name__iexact=name
    )
    if exclude_pk is not None:
        specialties = specialties.exclude(pk=exclude_pk)
    return specialties.exists()


@transaction.atomic
def create_specialty(
    *, actor: ActorContext | None, code: object, name: object
) -> Specialty:
    require_administrative_actor(actor)
    specialty = Specialty(code=_text(code, "code"), name=_text(name, "name"))
    if _specialty_conflict(code=specialty.code, name=specialty.name):
        raise CatalogConflictError("Specialty code and name must be unique.")
    try:
        specialty.full_clean()
        specialty.save(force_insert=True)
    except ValidationError as error:
        raise _specialty_validation_error(error) from error
    except IntegrityError as error:
        raise CatalogConflictError("Specialty code and name must be unique.") from error
    return specialty


@transaction.atomic
def update_specialty(
    *, actor: ActorContext | None, specialty: Specialty, name: object, is_active: object
) -> Specialty:
    require_administrative_actor(actor)
    locked = Specialty.objects.select_for_update().get(pk=specialty.pk)
    locked.name = _text(name, "name")
    if not isinstance(is_active, bool):
        raise ValidationError({"is_active": "Must be a boolean."})
    locked.is_active = is_active
    if _specialty_conflict(code=locked.code, name=locked.name, exclude_pk=locked.pk):
        raise CatalogConflictError("Specialty code and name must be unique.")
    try:
        locked.full_clean()
        locked.save(update_fields=("name", "is_active"))
    except ValidationError as error:
        raise _specialty_validation_error(error) from error
    except IntegrityError as error:
        raise CatalogConflictError("Specialty name must be unique.") from error
    return locked


@transaction.atomic
def retire_specialty(*, actor: ActorContext | None, specialty: Specialty) -> Specialty:
    require_administrative_actor(actor)
    locked = Specialty.objects.select_for_update().get(pk=specialty.pk)
    if locked.is_active:
        locked.is_active = False
        locked.save(update_fields=("is_active",))
    return locked


@transaction.atomic
def delete_specialty(*, actor: ActorContext | None, specialty: Specialty) -> None:
    require_administrative_actor(actor)
    # Registration locks this same row before assigning it, so no new link can
    # appear between the reference check and deletion.
    locked = Specialty.objects.select_for_update().get(pk=specialty.pk)
    if Professional.objects.filter(specialty=locked).exists():
        raise CatalogConflictError(
            "Assigned specialties cannot be deleted; retire the specialty instead."
        )
    locked.delete()


def _normalized_row(
    row: object, *, medication: bool, source_label: str
) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValidationError({"entries": "Each entry must be an object."})
    fields = (
        ("system", "version", "code", "name", "presentation")
        if medication
        else ("system", "version", "code", "display")
    )
    allowed = set(fields)
    if medication:
        allowed.add("terminology_entry_id")
    unexpected = set(row) - allowed
    if unexpected:
        raise ValidationError(
            {field: "This field is not allowed." for field in sorted(unexpected)}
        )
    normalized: dict[str, Any] = {
        field: _text(row.get(field), field) for field in fields
    }
    normalized["source_label"] = source_label
    if medication and "terminology_entry_id" in row:
        value = row["terminology_entry_id"]
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValidationError({"terminology_entry_id": "Must be an integer."})
        normalized["terminology_entry_id"] = value
    return normalized


def _identity(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["system"], row["version"], row["code"]


def _content_fields(model: CatalogModel) -> tuple[str, ...]:
    if model is MedicationEntry:
        return (
            "system",
            "version",
            "code",
            "name",
            "presentation",
            "terminology_entry_id",
            "source_label",
        )
    return ("system", "version", "code", "display", "source_label")


def _same_content(model: CatalogModel, entry: Any, row: dict[str, Any]) -> bool:
    return all(
        getattr(entry, field, None) == row.get(field)
        for field in _content_fields(model)
    )


def _validate_row(
    model: CatalogModel, actor: ActorContext, row: dict[str, Any]
) -> None:
    entry = model(created_by_id=actor.user_id, **row)
    entry.full_clean(validate_unique=False, validate_constraints=False)
    if model is MedicationEntry and row.get("terminology_entry_id") is not None:
        if not TerminologyEntry.objects.filter(pk=row["terminology_entry_id"]).exists():
            raise ValidationError(
                {"terminology_entry_id": "Unknown terminology entry."}
            )


def _insert_or_reuse(
    *, actor: ActorContext, model: CatalogModel, row: dict[str, Any]
) -> tuple[Any, bool]:
    identity = {field: row[field] for field in ("system", "version", "code")}
    existing = model.objects.select_for_update().filter(**identity).first()
    if existing is not None:
        if not _same_content(model, existing, row):
            raise CatalogConflictError(
                "An existing source identity has conflicting content."
            )
        return existing, False
    try:
        # A savepoint leaves the outer atomic import usable if another request
        # inserts the same identity between the lookup and insert.
        with transaction.atomic():
            entry = model.objects.create(created_by_id=actor.user_id, **row)
    except IntegrityError as error:
        existing = model.objects.select_for_update().filter(**identity).first()
        if existing is not None and _same_content(model, existing, row):
            return existing, False
        if existing is not None:
            raise CatalogConflictError(
                "An existing source identity has conflicting content."
            ) from error
        raise
    return entry, True


@transaction.atomic
def create_catalog_entry(
    *, actor: ActorContext | None, model: CatalogModel, values: dict[str, object]
) -> tuple[TerminologyEntry | MedicationEntry, bool]:
    """Create one immutable entry or reuse an exact pre-existing one."""
    authorized = require_administrative_actor(actor)
    medication = model is MedicationEntry
    source_label = _text(values.get("source_label"), "source_label")
    row = _normalized_row(
        {field: value for field, value in values.items() if field != "source_label"},
        medication=medication,
        source_label=source_label,
    )
    _validate_row(model, authorized, row)
    return _insert_or_reuse(actor=authorized, model=model, row=row)


@transaction.atomic
def import_entries(
    *, actor: ActorContext | None, model: CatalogModel, payload: bytes
) -> ImportResult:
    """Validate the complete normalized document before any catalog mutation."""
    authorized = require_administrative_actor(actor)
    if len(payload) > MAX_IMPORT_BYTES:
        raise ValidationError({"file": "The import must not exceed 2 MiB."})
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError({"file": "Provide valid UTF-8 JSON."}) from error
    if not isinstance(document, dict):
        raise ValidationError({"file": "Provide a JSON object."})
    unexpected = set(document) - {"source_label", "entries"}
    if unexpected:
        raise ValidationError(
            {field: "This field is not allowed." for field in sorted(unexpected)}
        )
    source_label = _text(document.get("source_label"), "source_label")
    rows = document.get("entries")
    if not isinstance(rows, list) or not rows:
        raise ValidationError({"entries": "Provide at least one entry."})
    if len(rows) > MAX_IMPORT_ROWS:
        raise ValidationError(
            {"entries": "The import must contain at most 500 entries."}
        )

    normalized: list[dict[str, Any]] = []
    errors: dict[str, object] = {}
    for index, row in enumerate(rows):
        try:
            normalized_row = _normalized_row(
                row, medication=model is MedicationEntry, source_label=source_label
            )
            _validate_row(model, authorized, normalized_row)
            normalized.append(normalized_row)
        except ValidationError as error:
            errors[str(index)] = error.message_dict
    if errors:
        raise CatalogInputError({"entries": errors})

    unique_rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    duplicate_count = 0
    for index, row in enumerate(normalized):
        identity = _identity(row)
        previous = unique_rows.get(identity)
        if previous is None:
            unique_rows[identity] = row
        elif previous == row:
            duplicate_count += 1
        else:
            errors[str(index)] = {"code": "Conflicts with an earlier row."}
    if errors:
        raise CatalogInputError({"entries": errors})

    created = 0
    unchanged = duplicate_count
    for row in unique_rows.values():
        _, was_created = _insert_or_reuse(actor=authorized, model=model, row=row)
        if was_created:
            created += 1
        else:
            unchanged += 1
    return ImportResult(created=created, unchanged=unchanged)
