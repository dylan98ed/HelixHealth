from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError

VITAL_SIGN_FIELDS = (
    "systolic_blood_pressure",
    "diastolic_blood_pressure",
    "heart_rate",
    "temperature",
)


@dataclass(frozen=True, slots=True)
class VitalSignDefinition:
    minimum: Decimal
    maximum: Decimal
    unit: str


def vital_sign_definitions() -> dict[str, VitalSignDefinition]:
    configured = settings.CLINICAL_VITAL_SIGN_RANGES  # type: ignore[misc]
    definitions: dict[str, VitalSignDefinition] = {}
    for field_name in VITAL_SIGN_FIELDS:
        try:
            values = configured[field_name]
            definition = VitalSignDefinition(
                minimum=Decimal(str(values["minimum"])),
                maximum=Decimal(str(values["maximum"])),
                unit=str(values["unit"]),
            )
        except (KeyError, InvalidOperation, TypeError) as error:
            raise ImproperlyConfigured(
                f"Invalid CLINICAL_VITAL_SIGN_RANGES entry for {field_name}."
            ) from error
        if definition.minimum > definition.maximum or not definition.unit.strip():
            raise ImproperlyConfigured(
                f"Invalid CLINICAL_VITAL_SIGN_RANGES entry for {field_name}."
            )
        definitions[field_name] = definition
    return definitions


def validate_vital_signs(values: dict[str, Any]) -> None:
    errors: dict[str, str] = {}
    for field_name, definition in vital_sign_definitions().items():
        value = values.get(field_name)
        if value is None:
            errors[field_name] = "This vital-sign value is required."
            continue
        try:
            numeric_value = Decimal(str(value))
        except InvalidOperation:
            errors[field_name] = "Enter a valid numeric value."
            continue
        if not definition.minimum <= numeric_value <= definition.maximum:
            errors[field_name] = (
                f"Enter a value from {definition.minimum} to "
                f"{definition.maximum} {definition.unit}."
            )
    if errors:
        raise ValidationError(errors)
