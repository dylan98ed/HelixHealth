from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connection

from patients.identifiers import generate_clinical_record_number


def assert_clinical_record_number_format(value: str) -> None:
    numeric_part = value.removeprefix("HC-")

    assert value.startswith("HC-")
    assert len(numeric_part) >= 8
    assert numeric_part.isascii()
    assert numeric_part.isdigit()


def generate_on_dedicated_connection(_index: int) -> str:
    close_old_connections()
    try:
        return generate_clinical_record_number()
    finally:
        connection.close()


@pytest.mark.django_db
def test_repeated_generation_produces_unique_numbers():
    generated_numbers = [generate_clinical_record_number() for _ in range(100)]

    assert len(generated_numbers) == len(set(generated_numbers))
    for number in generated_numbers:
        assert_clinical_record_number_format(number)


@pytest.mark.django_db(transaction=True)
def test_concurrent_generation_produces_unique_numbers():
    worker_barrier = Barrier(8)

    def generate_concurrently(index: int) -> str:
        worker_barrier.wait()
        return generate_on_dedicated_connection(index)

    with ThreadPoolExecutor(max_workers=8) as executor:
        generated_numbers = list(executor.map(generate_concurrently, range(64)))

    assert len(generated_numbers) == len(set(generated_numbers))
    for number in generated_numbers:
        assert_clinical_record_number_format(number)
