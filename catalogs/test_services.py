"""PostgreSQL coverage for catalog services and concurrent mutations."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection

from access_control.actors import ActorContext, ActorRole
from access_control.roles import ADMINISTRATIVE_GROUP, MEDICAL_PROFESSIONAL_GROUP
from catalogs.models import MedicationEntry, TerminologyEntry
from catalogs.services import (
    CatalogConflictError,
    CatalogInputError,
    create_catalog_entry,
    create_specialty,
    delete_specialty,
    import_entries,
    retire_specialty,
    update_specialty,
)
from professionals.models import HospitalService, Professional, Specialty
from professionals.services import register_professional


def administrative_actor(user) -> ActorContext:
    return ActorContext(user.pk, frozenset({ActorRole.ADMINISTRATIVE}))


def terminology_row(code="123"):
    return {
        "system": "https://snomed.example.test",
        "version": "2026-09",
        "code": code,
        "display": "Clinical finding",
    }


@pytest.fixture
def administrator(user_factory):
    user = user_factory(username="catalog-service-administrator")
    user.groups.add(Group.objects.get_or_create(name=ADMINISTRATIVE_GROUP)[0])
    return user


@pytest.mark.django_db
def test_specialty_lifecycle_normalizes_names_protects_codes_and_references(
    administrator,
    user_factory,
):
    actor = administrative_actor(administrator)
    specialty = create_specialty(
        actor=actor, code="catalog-neurology", name=" Catalog Neurology "
    )

    assert specialty.name == "Catalog Neurology"
    with pytest.raises(CatalogConflictError):
        create_specialty(actor=actor, code="other", name="catalog neurology")

    renamed = update_specialty(
        actor=actor, specialty=specialty, name="Clinical Neurology", is_active=True
    )
    assert renamed.code == "catalog-neurology"
    assert renamed.name == "Clinical Neurology"

    service = HospitalService.objects.create(code="catalog-ward", name="Catalog ward")
    subject = user_factory(username="catalog-specialty-subject")
    Professional.objects.create(
        user=subject,
        dni="12345678",
        registration_number="PR-CATALOG-00000001",
        license_number="MN 1",
        first_name="Assigned",
        last_name="Professional",
        date_of_birth=date(1990, 1, 1),
        specialty=renamed,
        hospital_service=service,
        registration_completed_at="2026-01-01T00:00:00Z",
    )

    with pytest.raises(CatalogConflictError, match="retire"):
        delete_specialty(actor=actor, specialty=renamed)
    retired = retire_specialty(actor=actor, specialty=renamed)
    assert retired.is_active is False
    assert Professional.objects.get().specialty_id == retired.pk


@pytest.mark.django_db
def test_append_only_creation_and_import_reuse_exact_rows_atomically(administrator):
    actor = administrative_actor(administrator)
    created, was_created = create_catalog_entry(
        actor=actor,
        model=TerminologyEntry,
        values={**terminology_row(), "source_label": "Manual source"},
    )
    same, was_reused = create_catalog_entry(
        actor=actor,
        model=TerminologyEntry,
        values={**terminology_row(), "source_label": "Manual source"},
    )
    assert was_created is True
    assert was_reused is False
    assert same.pk == created.pk

    payload = {
        "source_label": "Third party",
        "entries": [terminology_row("456"), terminology_row("456")],
    }
    result = import_entries(
        actor=actor, model=TerminologyEntry, payload=json.dumps(payload).encode()
    )
    assert result.created == 1
    assert result.unchanged == 1

    conflicting = {
        "source_label": "Third party",
        "entries": [
            terminology_row("789"),
            {**terminology_row("456"), "display": "Different text"},
        ],
    }
    with pytest.raises(CatalogConflictError):
        import_entries(
            actor=actor,
            model=TerminologyEntry,
            payload=json.dumps(conflicting).encode(),
        )
    assert TerminologyEntry.objects.filter(code="789").count() == 0


@pytest.mark.django_db
def test_invalid_import_rows_report_indexes_and_do_not_partially_write(administrator):
    payload = {
        "source_label": "Third party",
        "entries": [terminology_row("valid"), {"system": "", "code": "missing"}],
    }
    with pytest.raises(CatalogInputError) as raised:
        import_entries(
            actor=administrative_actor(administrator),
            model=TerminologyEntry,
            payload=json.dumps(payload).encode(),
        )
    assert "1" in raised.value.errors["entries"]
    assert TerminologyEntry.objects.count() == 0


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@pytest.mark.parametrize("operation", ["retire", "delete"])
def test_specialty_registration_races_are_controlled_without_broken_links(
    administrator,
    user_factory,
    operation,
):
    Group.objects.get_or_create(name=MEDICAL_PROFESSIONAL_GROUP)
    specialty = Specialty.objects.create(
        code=f"race-{operation}", name=f"Race {operation}"
    )
    HospitalService.objects.create(code=f"ward-{operation}", name=f"Ward {operation}")
    subject = user_factory(username=f"catalog-race-{operation}-subject")
    actor = administrative_actor(administrator)
    barrier = Barrier(2)

    def register() -> str:
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                register_professional(
                    actor=actor,
                    username=subject.username,
                    dni="23456789",
                    license_number="MN 123",
                    first_name="Race",
                    last_name="Registrant",
                    date_of_birth=date(1990, 1, 1),
                    specialty_code=specialty.code,
                    hospital_service_code=f"ward-{operation}",
                )
                return "registered"
            except (CatalogConflictError, ValidationError):
                return "rejected"
        finally:
            connection.close()

    def change_reference() -> str:
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                locked = Specialty.objects.get(pk=specialty.pk)
                if operation == "retire":
                    retire_specialty(actor=actor, specialty=locked)
                    return "retired"
                delete_specialty(actor=actor, specialty=locked)
                return "deleted"
            except CatalogConflictError:
                return "protected"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = set(executor.map(lambda job: job(), (register, change_reference)))

    assert outcomes in (
        {"registered", "retired"},
        {"rejected", "retired"},
        {"registered", "protected"},
        {"rejected", "deleted"},
    )
    profile = Professional.objects.filter(user=subject).first()
    if profile is not None:
        assert Specialty.objects.filter(pk=profile.specialty_id).exists()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_imports_reuse_the_same_source_identity(administrator):
    actor = administrative_actor(administrator)
    payload = json.dumps(
        {
            "source_label": "Concurrent source",
            "entries": [terminology_row("concurrent")],
        }
    ).encode()
    barrier = Barrier(2)

    def import_once():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return import_entries(actor=actor, model=TerminologyEntry, payload=payload)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: import_once(), range(2)))

    assert sorted((result.created, result.unchanged) for result in results) == [
        (0, 1),
        (1, 0),
    ]
    assert TerminologyEntry.objects.filter(code="concurrent").count() == 1


@pytest.mark.django_db
def test_medication_import_validates_protected_terminology_link(administrator):
    payload = {
        "source_label": "Medication source",
        "entries": [
            {
                "system": "https://medications.example.test",
                "version": "1",
                "code": "MED-1",
                "name": "Example medicine",
                "presentation": "10 mg tablet",
                "terminology_entry_id": 99999,
            }
        ],
    }
    with pytest.raises(CatalogInputError):
        import_entries(
            actor=administrative_actor(administrator),
            model=MedicationEntry,
            payload=json.dumps(payload).encode(),
        )
    assert MedicationEntry.objects.count() == 0
