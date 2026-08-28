from typing import Final

DNI_MIN_DIGITS: Final = 7
DNI_MAX_DIGITS: Final = 8


class DNIValidationError(ValueError):
    """Raised when a DNI is not in the canonical format."""


def validate_dni(value: str) -> str:
    """Return a DNI only when it already contains 7 or 8 ASCII digits."""
    if not isinstance(value, str):
        raise TypeError("DNI must be provided as a string.")

    if not all("0" <= character <= "9" for character in value):
        raise DNIValidationError("DNI must contain only ASCII digits.")

    if not DNI_MIN_DIGITS <= len(value) <= DNI_MAX_DIGITS:
        raise DNIValidationError(
            f"DNI must contain {DNI_MIN_DIGITS} or {DNI_MAX_DIGITS} digits."
        )

    return value
