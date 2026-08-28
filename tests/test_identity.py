import pytest

from helixhealth.identity import DNIValidationError, validate_dni


@pytest.mark.parametrize("value", ["1234567", "12345678"])
def test_validate_dni_accepts_canonical_ascii_digits(value):
    assert validate_dni(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "12.345.678",
        "12-345-678",
        "12 345 678",
        " 12345678",
        "12345678 ",
        "\t12345678",
        "12345678\n",
        "12\u00a0345678",
        "12A34567",
        "12/345/678",
        "12_345_678",
        "+12345678",
        "１２３４５６７８",
    ],
)
def test_validate_dni_rejects_noncanonical_characters(value):
    with pytest.raises(DNIValidationError, match="only ASCII digits"):
        validate_dni(value)


@pytest.mark.parametrize("value", ["", "123456", "123456789"])
def test_validate_dni_rejects_invalid_lengths(value):
    with pytest.raises(DNIValidationError, match="7 or 8 digits"):
        validate_dni(value)


def test_validate_dni_requires_a_string():
    with pytest.raises(TypeError, match="provided as a string"):
        validate_dni(12345678)  # type: ignore[arg-type]
