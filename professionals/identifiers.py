from typing import Final

from django.db import connection

PROFESSIONAL_REGISTRATION_PREFIX: Final = "PR-"
PROFESSIONAL_REGISTRATION_MIN_DIGITS: Final = 8
PROFESSIONAL_REGISTRATION_SEQUENCE: Final = "professionals_registration_number_seq"


def generate_registration_number() -> str:
    """Return a unique professional registration number from a PG sequence.

    Lifecycle services call this only after all registration input has been
    accepted and the profile is about to be completed.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT nextval(%s::regclass)",
            [PROFESSIONAL_REGISTRATION_SEQUENCE],
        )
        row = cursor.fetchone()

    if row is None or not isinstance(row[0], int):
        raise RuntimeError("PostgreSQL did not return a professional sequence value.")

    return (
        f"{PROFESSIONAL_REGISTRATION_PREFIX}"
        f"{row[0]:0{PROFESSIONAL_REGISTRATION_MIN_DIGITS}d}"
    )
