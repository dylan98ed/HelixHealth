import pytest

from helixhealth.identity import DNIValidationError, normalize_dni


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("12345678", "12345678"),
        ("12.345.678", "12345678"),
        ("12-345-678", "12345678"),
        ("1.234.567", "1234567"),
    ],
)
def test_normalize_dni_accepts_digits_and_common_punctuation(value, expected):
    assert normalize_dni(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        " 12 345 678 ",
        "\t12.345.678\n",
        "12\u00a0345\u00a0678",
    ],
)
def test_normalize_dni_ignores_whitespace(value):
    assert normalize_dni(value) == "12345678"


@pytest.mark.parametrize(
    "value",
    [
        "12A34567",
        "12/345/678",
        "12_345_678",
        "+12345678",
        "１２３４５６７８",
    ],
)
def test_normalize_dni_rejects_invalid_characters(value):
    with pytest.raises(DNIValidationError, match="only ASCII digits"):
        normalize_dni(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        " . - ",
        "123456",
        "123456789",
    ],
)
def test_normalize_dni_rejects_invalid_digit_lengths(value):
    with pytest.raises(DNIValidationError, match="7 or 8 digits"):
        normalize_dni(value)


def test_formatted_dni_values_share_one_canonical_value():
    equivalent_values = {
        "12345678",
        "12.345.678",
        "12-345-678",
        " 12 345 678 ",
    }

    assert {normalize_dni(value) for value in equivalent_values} == {"12345678"}


def test_normalize_dni_requires_a_string():
    with pytest.raises(TypeError, match="provided as a string"):
        normalize_dni(12345678)  # type: ignore[arg-type]
