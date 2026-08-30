import re
from datetime import date

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from helixhealth.identity import DNIValidationError, validate_dni

PHONE_PATTERN = re.compile(r"^\+?[0-9 ()-]+$")
PHONE_MIN_DIGITS = 7
PHONE_MAX_DIGITS = 15


def validate_not_blank(value: str) -> None:
    if not value.strip():
        raise ValidationError(
            _("This field cannot be blank."),
            code="blank",
        )


def validate_patient_dni(value: str) -> None:
    try:
        validate_dni(value)
    except (DNIValidationError, TypeError) as error:
        raise ValidationError(str(error), code="invalid_dni") from error


def validate_date_of_birth(value: date) -> None:
    if value > date.today():
        raise ValidationError(
            _("Date of birth cannot be in the future."),
            code="future_date_of_birth",
        )


def validate_phone(value: str) -> None:
    if PHONE_PATTERN.fullmatch(value) is None:
        raise ValidationError(
            _("Enter a phone number using digits, spaces, parentheses, or hyphens."),
            code="invalid_phone",
        )

    digit_count = sum(character.isdigit() for character in value)
    if not PHONE_MIN_DIGITS <= digit_count <= PHONE_MAX_DIGITS:
        raise ValidationError(
            _("Enter a phone number containing between 7 and 15 digits."),
            code="invalid_phone_length",
        )
