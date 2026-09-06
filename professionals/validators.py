"""Validation and normalization for professional registration input."""

from datetime import date

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from helixhealth.identity import DNIValidationError, validate_dni
from patients.validators import validate_date_of_birth


def canonicalize_professional_dni(value: str) -> str:
    """Trim form/API whitespace and return a canonical professional DNI."""
    if not isinstance(value, str):
        raise ValidationError(_("DNI must be provided as text."), code="invalid_dni")

    canonical_value = value.strip()
    try:
        return validate_dni(canonical_value)
    except DNIValidationError as error:
        raise ValidationError(str(error), code="invalid_dni") from error


def validate_professional_dni(value: str) -> None:
    """Validate a DNI accepted at professional form and API boundaries."""
    canonicalize_professional_dni(value)


def normalize_required_name(value: str) -> str:
    """Return a trimmed, nonblank professional name no longer than 150 chars."""
    if not isinstance(value, str):
        raise ValidationError(_("Enter a valid name."), code="invalid_name")

    normalized_value = value.strip()
    if not normalized_value:
        raise ValidationError(_("This field cannot be blank."), code="blank")
    if len(normalized_value) > 150:
        raise ValidationError(
            _("Ensure this value has at most 150 characters."),
            code="max_length",
        )
    return normalized_value


def validate_professional_name(value: str) -> None:
    normalize_required_name(value)


def validate_professional_date_of_birth(value: date) -> None:
    """Reuse the patient date rule for professional registrations."""
    validate_date_of_birth(value)


def validate_active_reference(value: object, *, field_name: str) -> None:
    """Reject a retired specialty or hospital service selected for assignment."""
    if value is None or not getattr(value, "is_active", False):
        raise ValidationError(
            _("Select an active %(field_name)s.") % {"field_name": field_name},
            code="inactive_reference",
        )
