import pytest
from django.db import IntegrityError, transaction

from catalogs.models import MedicationEntry, TerminologyEntry


def terminology_attributes(**overrides: object) -> dict[str, object]:
    attributes: dict[str, object] = {
        "system": "http://snomed.info/sct",
        "version": "2026-09-01",
        "code": "80146002",
        "display": "Appendectomy",
        "source_label": "Test terminology source",
    }
    attributes.update(overrides)
    return attributes


def medication_attributes(**overrides: object) -> dict[str, object]:
    attributes: dict[str, object] = {
        "system": "https://catalog.example.test/medications",
        "version": "2026-09",
        "code": "AMOX-500-CAP",
        "name": "Amoxicillin",
        "presentation": "500 mg capsule",
        "source_label": "Test medication source",
    }
    attributes.update(overrides)
    return attributes


@pytest.mark.django_db
def test_terminology_entry_keeps_its_source_identity_and_auditor(user_factory):
    actor = user_factory(username="catalog-model-author")

    entry = TerminologyEntry.objects.create(
        created_by=actor,
        **terminology_attributes(),
    )

    assert entry.created_at is not None
    assert entry.created_by == actor
    assert entry.system == "http://snomed.info/sct"
    assert entry.version == "2026-09-01"
    assert entry.code == "80146002"


@pytest.mark.django_db
def test_catalog_identity_is_unique_per_source_version_and_code(user_factory):
    actor = user_factory(username="catalog-model-unique-author")
    TerminologyEntry.objects.create(created_by=actor, **terminology_attributes())

    with pytest.raises(IntegrityError), transaction.atomic():
        TerminologyEntry.objects.create(
            created_by=actor,
            **terminology_attributes(display="Conflicting display"),
        )


@pytest.mark.django_db
def test_medication_protects_its_optional_terminology_link(user_factory):
    actor = user_factory(username="catalog-model-link-author")
    terminology = TerminologyEntry.objects.create(
        created_by=actor,
        **terminology_attributes(),
    )
    medication = MedicationEntry.objects.create(
        created_by=actor,
        terminology_entry=terminology,
        **medication_attributes(),
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        terminology.delete()

    medication.refresh_from_db()
    assert medication.terminology_entry_id == terminology.id


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("model", "attributes", "field"),
    [
        (TerminologyEntry, terminology_attributes, "display"),
        (MedicationEntry, medication_attributes, "presentation"),
    ],
)
def test_database_rejects_blank_catalog_values(user_factory, model, attributes, field):
    actor = user_factory(username=f"catalog-model-blank-{field}")

    with pytest.raises(IntegrityError), transaction.atomic():
        model.objects.create(created_by=actor, **attributes(**{field: "   "}))
