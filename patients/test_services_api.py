from datetime import date
from threading import Thread

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from access_control.actors import ActorContext, ActorRole
from access_control.roles import ADMINISTRATIVE_GROUP
from patients.models import Patient
from patients.services import (
    DuplicateActivePatientDNIError,
    create_patient,
    deactivate_patient,
    update_patient,
)


def valid_patient_data(**overrides):
    data = {
        "dni": "12345678",
        "first_name": "Alex",
        "last_name": "Patient",
        "date_of_birth": date(1990, 1, 1),
        "sex": "unspecified",
        "phone": "+54 11 5555-0101",
        "email": "alex.patient@example.test",
        "address": "123 Test Street",
        "health_insurer": "Test Health",
    }
    data.update(overrides)
    return data


def administrative_actor():
    return ActorContext(
        user_id=1,
        roles=frozenset({ActorRole.ADMINISTRATIVE}),
    )


def administrative_api_client(user_factory):
    user = user_factory(username="patient-api-admin")
    user.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_patient_service_creates_one_complete_patient_transactionally():
    patient = create_patient(actor=administrative_actor(), **valid_patient_data())

    assert Patient.objects.get() == patient
    assert patient.clinical_record_number.startswith("HC-")


@pytest.mark.django_db
def test_patient_service_rejects_duplicate_dni_without_partial_write():
    existing = create_patient(actor=administrative_actor(), **valid_patient_data())

    with pytest.raises(DuplicateActivePatientDNIError) as error:
        create_patient(
            actor=administrative_actor(),
            **valid_patient_data(email="different@example.test"),
        )

    assert error.value.patient == existing
    assert Patient.all_objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_patient_creation_reports_a_concurrent_duplicate_as_a_duplicate_conflict(
    monkeypatch,
):
    data = valid_patient_data()
    original_full_clean = Patient.full_clean
    competing_errors: list[Exception] = []

    def insert_competing_patient() -> None:
        close_old_connections()
        try:
            Patient.all_objects.create(**data)
        except Exception as error:  # pragma: no cover - asserted below.
            competing_errors.append(error)
        finally:
            close_old_connections()

    def full_clean_after_competing_insert(self, *args, **kwargs):
        competing_insert = Thread(target=insert_competing_patient)
        competing_insert.start()
        competing_insert.join(timeout=10)
        assert not competing_insert.is_alive()
        return original_full_clean(self, *args, **kwargs)

    monkeypatch.setattr(Patient, "full_clean", full_clean_after_competing_insert)

    with pytest.raises(DuplicateActivePatientDNIError) as error:
        create_patient(actor=administrative_actor(), **data)

    assert not competing_errors
    assert error.value.patient.dni == data["dni"]
    assert Patient.all_objects.filter(dni=data["dni"]).count() == 1


@pytest.mark.django_db
def test_patient_create_api_returns_generated_identifiers(user_factory):
    client = administrative_api_client(user_factory)
    payload = valid_patient_data(date_of_birth="1990-01-01")

    response = client.post(reverse("patients:api-create"), payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["id"] == Patient.objects.get().pk
    assert response.data["clinical_record_number"].startswith("HC-")
    assert response.data["is_active"] is True


@pytest.mark.django_db
def test_patient_create_api_rejects_duplicate_without_partial_write(user_factory):
    client = administrative_api_client(user_factory)
    payload = valid_patient_data(date_of_birth="1990-01-01")
    first_response = client.post(
        reverse("patients:api-create"),
        payload,
        format="json",
    )

    duplicate_response = client.post(
        reverse("patients:api-create"),
        payload,
        format="json",
    )

    assert first_response.status_code == status.HTTP_201_CREATED
    assert duplicate_response.status_code == status.HTTP_409_CONFLICT
    assert duplicate_response.data["existing_patient_id"] == first_response.data["id"]
    assert Patient.all_objects.count() == 1


@pytest.mark.django_db
def test_patient_api_requires_administrative_actor(user_factory):
    client = APIClient()
    payload = valid_patient_data(date_of_birth="1990-01-01")

    assert (
        client.post(reverse("patients:api-create"), payload, format="json").status_code
        == status.HTTP_403_FORBIDDEN
    )

    user = user_factory(username="patient-api-non-admin")
    client.force_authenticate(user)
    assert (
        client.post(reverse("patients:api-create"), payload, format="json").status_code
        == status.HTTP_403_FORBIDDEN
    )


@pytest.mark.django_db
def test_patient_detail_api_contract_contains_only_specified_fields(user_factory):
    client = administrative_api_client(user_factory)
    patient = create_patient(actor=administrative_actor(), **valid_patient_data())

    response = client.get(reverse("patients:api-detail", args=[patient.pk]))

    assert response.status_code == status.HTTP_200_OK
    assert set(response.data) == {
        "id",
        "dni",
        "clinical_record_number",
        "first_name",
        "last_name",
        "date_of_birth",
        "sex",
        "phone",
        "email",
        "address",
        "health_insurer",
        "is_active",
    }


@pytest.mark.django_db
def test_patient_update_api_changes_mutable_data_and_rejects_identifiers(user_factory):
    client = administrative_api_client(user_factory)
    patient = create_patient(actor=administrative_actor(), **valid_patient_data())
    original_id = patient.pk
    original_dni = patient.dni
    original_clinical_record_number = patient.clinical_record_number
    url = reverse("patients:api-detail", args=[patient.pk])

    immutable_response = client.patch(
        url,
        {
            "id": original_id + 100,
            "dni": "7654321",
            "clinical_record_number": "HC-99999999",
        },
        format="json",
    )
    mutable_response = client.patch(
        url,
        {"phone": "+54 11 5555-9999", "address": "Updated address"},
        format="json",
    )

    patient.refresh_from_db()
    assert immutable_response.status_code == status.HTTP_400_BAD_REQUEST
    assert mutable_response.status_code == status.HTTP_200_OK
    assert patient.pk == original_id
    assert patient.dni == original_dni
    assert patient.clinical_record_number == original_clinical_record_number
    assert patient.phone == "+54 11 5555-9999"
    assert patient.address == "Updated address"


@pytest.mark.django_db
def test_patient_update_api_reports_inactive_patient_as_validation_error(
    user_factory,
):
    client = administrative_api_client(user_factory)
    patient = create_patient(actor=administrative_actor(), **valid_patient_data())
    deactivate_patient(
        actor=administrative_actor(),
        patient=patient,
        confirmed=True,
    )

    response = client.patch(
        reverse("patients:api-detail", args=[patient.pk]),
        {"phone": "+54 11 5555-9999"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["__all__"] == ["Inactive patients cannot be updated."]


@pytest.mark.django_db
def test_update_reloads_a_stale_patient_after_deactivation():
    patient = create_patient(actor=administrative_actor(), **valid_patient_data())
    stale_patient = Patient.all_objects.get(pk=patient.pk)
    deactivate_patient(
        actor=administrative_actor(),
        patient=Patient.all_objects.get(pk=patient.pk),
        confirmed=True,
    )

    with pytest.raises(ValidationError) as error:
        update_patient(
            actor=administrative_actor(),
            patient=stale_patient,
            changes={"phone": "+54 11 5555-9999"},
        )

    assert "Inactive patients cannot be updated." in str(error.value)
    patient.refresh_from_db()
    assert patient.phone == valid_patient_data()["phone"]


@pytest.mark.django_db
def test_confirmed_deactivation_preserves_record_and_excludes_it_by_default():
    patient = create_patient(actor=administrative_actor(), **valid_patient_data())
    original_identifiers = (patient.pk, patient.dni, patient.clinical_record_number)

    deactivate_patient(
        actor=administrative_actor(),
        patient=patient,
        confirmed=True,
    )

    assert not Patient.objects.filter(pk=patient.pk).exists()
    preserved = Patient.all_objects.get(pk=patient.pk)
    assert preserved.is_active is False
    assert (preserved.pk, preserved.dni, preserved.clinical_record_number) == (
        original_identifiers
    )


@pytest.mark.django_db
def test_deactivation_api_requires_confirmation(user_factory):
    client = administrative_api_client(user_factory)
    patient = create_patient(actor=administrative_actor(), **valid_patient_data())
    url = reverse("patients:api-deactivate", args=[patient.pk])

    unconfirmed_response = client.post(url, {"confirm": False}, format="json")
    confirmed_response = client.post(url, {"confirm": True}, format="json")

    assert unconfirmed_response.status_code == status.HTTP_400_BAD_REQUEST
    assert confirmed_response.status_code == status.HTTP_200_OK
    assert confirmed_response.data["is_active"] is False
