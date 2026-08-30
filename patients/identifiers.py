from typing import Final

from django.db import connection

CLINICAL_RECORD_PREFIX: Final = "HC-"
CLINICAL_RECORD_MIN_DIGITS: Final = 8
CLINICAL_RECORD_SEQUENCE: Final = "patients_clinical_record_number_seq"


def generate_clinical_record_number() -> str:
    """Return a unique clinical record number from PostgreSQL's atomic sequence."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval(%s::regclass)", [CLINICAL_RECORD_SEQUENCE])
        row = cursor.fetchone()

    if row is None or not isinstance(row[0], int):
        raise RuntimeError(
            "PostgreSQL did not return a clinical record sequence value."
        )

    return f"{CLINICAL_RECORD_PREFIX}{row[0]:0{CLINICAL_RECORD_MIN_DIGITS}d}"
