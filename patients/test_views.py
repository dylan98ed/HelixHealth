from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from access_control.actors import ActorContext, ActorRole
from access_control.roles import ADMINISTRATIVE_GROUP
from patients.identifiers import generate_clinical_record_number
from patients.models import Patient
from patients.services import create_patient


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


def login_administrative_user(client, user_factory):
    user = user_factory(username="patient-template-admin")
    user.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))
    client.force_login(user)


@pytest.mark.django_db
def test_htmx_registration_displays_generated_clinical_record_number(
    client,
    user_factory,
):
    login_administrative_user(client, user_factory)
    payload = valid_patient_data(date_of_birth="1990-01-01")

    response = client.post(
        reverse("patients:register"),
        payload,
        HTTP_HX_REQUEST="true",
    )

    patient = Patient.objects.get()
    assert response.status_code == 200
    assert patient.clinical_record_number.encode() in response.content
    assert b"Patient registered" in response.content


@pytest.mark.django_db
def test_htmx_registration_identifies_each_invalid_field(client, user_factory):
    login_administrative_user(client, user_factory)

    response = client.post(
        reverse("patients:register"),
        {
            "dni": "1234 678",
            "first_name": "",
            "last_name": "",
            "date_of_birth": "2999-01-01",
            "sex": "",
            "phone": "invalid",
            "email": "invalid",
            "address": "",
            "health_insurer": "",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    for field_name in (
        "dni",
        "first_name",
        "last_name",
        "date_of_birth",
        "sex",
        "phone",
        "email",
        "address",
        "health_insurer",
    ):
        assert f'data-field-error="{field_name}"'.encode() in response.content
    assert Patient.all_objects.count() == 0


@pytest.mark.django_db
def test_invalid_registration_does_not_allocate_clinical_record_number(
    client,
    user_factory,
):
    login_administrative_user(client, user_factory)
    number_before_invalid_submission = generate_clinical_record_number()

    response = client.post(
        reverse("patients:register"),
        valid_patient_data(phone="invalid", date_of_birth="1990-01-01"),
        HTTP_HX_REQUEST="true",
    )

    number_after_invalid_submission = generate_clinical_record_number()
    before_value = int(number_before_invalid_submission.removeprefix("HC-"))
    after_value = int(number_after_invalid_submission.removeprefix("HC-"))
    assert response.status_code == 422
    assert Patient.all_objects.count() == 0
    assert after_value == before_value + 1


@pytest.mark.django_db
def test_duplicate_registration_links_to_existing_patient(client, user_factory):
    login_administrative_user(client, user_factory)
    patient = create_patient(actor=administrative_actor(), **valid_patient_data())

    response = client.post(
        reverse("patients:register"),
        valid_patient_data(date_of_birth="1990-01-01"),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert reverse("patients:detail", args=[patient.pk]).encode() in response.content
    assert b"Open the existing patient record" in response.content


@pytest.mark.django_db
def test_server_rendered_detail_displays_complete_patient(client, user_factory):
    login_administrative_user(client, user_factory)
    patient = create_patient(actor=administrative_actor(), **valid_patient_data())

    response = client.get(reverse("patients:detail", args=[patient.pk]))

    assert response.status_code == 200
    for value in (
        str(patient.pk),
        patient.dni,
        patient.clinical_record_number,
        patient.first_name,
        patient.last_name,
        patient.phone,
        patient.email,
        patient.address,
        patient.health_insurer,
    ):
        assert value.encode() in response.content


@pytest.mark.django_db
def test_server_rendered_update_does_not_expose_immutable_fields(
    client,
    user_factory,
):
    login_administrative_user(client, user_factory)
    patient = create_patient(actor=administrative_actor(), **valid_patient_data())

    response = client.get(reverse("patients:update", args=[patient.pk]))

    assert response.status_code == 200
    assert b'name="dni"' not in response.content
    assert b'name="clinical_record_number"' not in response.content
    assert patient.dni.encode() in response.content
    assert patient.clinical_record_number.encode() in response.content


@pytest.mark.django_db
def test_server_rendered_update_reports_inactive_patient_without_server_error(
    client,
    user_factory,
):
    login_administrative_user(client, user_factory)
    patient = create_patient(actor=administrative_actor(), **valid_patient_data())
    patient.is_active = False
    patient.save(update_fields=["is_active"])

    payload = valid_patient_data(date_of_birth="1990-01-01")
    payload.pop("dni")
    response = client.post(
        reverse("patients:update", args=[patient.pk]),
        payload,
    )

    assert response.status_code == 200
    assert b"Inactive patients cannot be updated." in response.content
