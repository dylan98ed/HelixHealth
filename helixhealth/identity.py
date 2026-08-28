from typing import Final

DNI_MIN_DIGITS: Final = 7
DNI_MAX_DIGITS: Final = 8
_DNI_SEPARATORS: Final = frozenset({".", "-"})


class DNIValidationError(ValueError):
    """Raised when a DNI cannot be converted to the canonical format."""


def normalize_dni(value: str) -> str:
    """Validate a DNI and return its canonical ASCII-digits-only value."""
    if not isinstance(value, str):
        raise TypeError("DNI must be provided as a string.")

    digits: list[str] = []
    for character in value:
        if "0" <= character <= "9":
            digits.append(character)
        elif character in _DNI_SEPARATORS or character.isspace():
            continue
        else:
            raise DNIValidationError(
                "DNI may contain only ASCII digits, periods, hyphens, and whitespace."
            )

    normalized = "".join(digits)
    if not DNI_MIN_DIGITS <= len(normalized) <= DNI_MAX_DIGITS:
        raise DNIValidationError(
            f"DNI must contain {DNI_MIN_DIGITS} or {DNI_MAX_DIGITS} digits."
        )

    return normalized
