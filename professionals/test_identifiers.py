from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection

from professionals.identifiers import generate_registration_number
from professionals.models import Professional


def assert_registration_number_format(value: str) -> None:
    numeric_part = value.removeprefix("PR-")
    assert value.startswith("PR-")
    assert len(numeric_part) >= 8
    assert numeric_part.isascii()
    assert numeric_part.isdigit()


def generate_on_dedicated_connection(_index: int) -> str:
    close_old_connections()
    try:
        return generate_registration_number()
    finally:
        connection.close()


@pytest.mark.django_db
def test_repeated_generation_produces_unique_registration_numbers():
    numbers = [generate_registration_number() for _ in range(100)]
    assert len(numbers) == len(set(numbers))
    for number in numbers:
        assert_registration_number_format(number)


@pytest.mark.django_db(transaction=True)
def test_concurrent_generation_produces_unique_registration_numbers():
    barrier = Barrier(8)

    def generate_concurrently(index: int) -> str:
        barrier.wait()
        return generate_on_dedicated_connection(index)

    with ThreadPoolExecutor(max_workers=8) as executor:
        numbers = list(executor.map(generate_concurrently, range(64)))

    assert len(numbers) == len(set(numbers))
    for number in numbers:
        assert_registration_number_format(number)


@pytest.mark.django_db
def test_incomplete_or_invalid_profiles_do_not_allocate_registration_numbers():
    incomplete = Professional.objects.create(
        user=get_user_model().objects.create_user(
            username="incomplete", password="test-pass"
        )
    )
    invalid = Professional(
        user=get_user_model().objects.create_user(
            username="invalid", password="test-pass"
        ),
        dni="12.345.678",
    )

    assert incomplete.registration_number is None
    with pytest.raises(ValidationError):
        invalid.full_clean()
    assert invalid.registration_number is None


@pytest.mark.django_db
def test_an_existing_registration_number_is_preserved():
    professional = Professional.objects.create(
        user=get_user_model().objects.create_user(
            username="numbered", password="test-pass"
        ),
        registration_number="PR-00000042",
    )

    professional.is_active = False
    professional.save()
    professional.refresh_from_db()

    assert professional.registration_number == "PR-00000042"
