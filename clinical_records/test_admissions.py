from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from access_control.actors import ActorContext, ActorRole
from access_control.roles import (
    ADMINISTRATIVE_GROUP,
    MEDICAL_PROFESSIONAL_GROUP,
)
from clinical_records.forms import AdmissionForm
from clinical_records.models import Admission
from clinical_records.services import InactivePatientError, create_admission
from patients.models import Patient
from professionals.models import Professional


def patient_attributes(**overrides):
    attributes = {
        "dni": "12345678",
        "clinical_record_number": "HC-ADMISSION-01",
        "first_name": "Alex",
        "last_name": "Patient",
        "date_of_birth": date(1990, 1, 1),
        "sex": "unspecified",
        "phone": "+54 11 5555-0101",
        "email": "alex.patient@example.test",
        "address": "123 Test Street",
        "health_insurer": "Test Health",
    }
    attributes.update(overrides)
    return attributes


def admission_data(**overrides):
    data = {
        "consultation_reason": "Persistent headache",
        "systolic_blood_pressure": 120,
        "diastolic_blood_pressure": 80,
        "heart_rate": 72,
        "temperature": Decimal("36.7"),
    }
    data.update(overrides)
    return data


def professional_actor(user):
    return ActorContext(
        user_id=user.pk,
        roles=frozenset({ActorRole.MEDICAL_PROFESSIONAL}),
    )


def create_professional_user(user_factory, **user_overrides):
    user = user_factory(**user_overrides)
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    professional = Professional.objects.create(user=user)
    return user, professional


@pytest.mark.django_db
def test_admission_persists_patient_professional_vitals_and_server_timestamp(
    user_factory,
):
    patient = Patient.objects.create(**patient_attributes())
    user, professional = create_professional_user(user_factory)
    before_creation = timezone.now()

    admission = create_admission(
        actor=professional_actor(user),
        patient=patient,
        **admission_data(),
    )
    after_creation = timezone.now()
    admission.refresh_from_db()

    assert admission.patient == patient
    assert admission.professional == professional
    assert admission.consultation_reason == "Persistent headache"
    assert admission.systolic_blood_pressure == 120
    assert admission.diastolic_blood_pressure == 80
    assert admission.heart_rate == 72
    assert admission.temperature == Decimal("36.7")
    assert before_creation <= admission.created_at <= after_creation


@pytest.mark.django_db
@pytest.mark.parametrize("orphan_field", ["patient_id", "professional_id"])
def test_postgresql_rejects_orphaned_admission_relations(user_factory, orphan_field):
    patient = Patient.objects.create(**patient_attributes())
    _, professional = create_professional_user(user_factory)
    attributes = {
        "patient": patient,
        "professional": professional,
        **admission_data(),
    }
    attributes.pop("patient" if orphan_field == "patient_id" else "professional")
    attributes[orphan_field] = 999_999_999

    with pytest.raises(IntegrityError), transaction.atomic():
        Admission.objects.create(**attributes)
        connection.check_constraints()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field_name", "boundary"),
    [
        ("systolic_blood_pressure", 70),
        ("systolic_blood_pressure", 250),
        ("diastolic_blood_pressure", 40),
        ("diastolic_blood_pressure", 150),
        ("heart_rate", 30),
        ("heart_rate", 220),
        ("temperature", Decimal("30.0")),
        ("temperature", Decimal("45.0")),
    ],
)
def test_vital_sign_boundaries_are_accepted(user_factory, field_name, boundary):
    patient = Patient.objects.create(**patient_attributes())
    user, _ = create_professional_user(user_factory)

    admission = create_admission(
        actor=professional_actor(user),
        patient=patient,
        **admission_data(**{field_name: boundary}),
    )

    assert admission.pk is not None


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field_name", "outside_value"),
    [
        ("systolic_blood_pressure", 69),
        ("systolic_blood_pressure", 251),
        ("diastolic_blood_pressure", 39),
        ("diastolic_blood_pressure", 151),
        ("heart_rate", 29),
        ("heart_rate", 221),
        ("temperature", Decimal("29.9")),
        ("temperature", Decimal("45.1")),
    ],
)
def test_out_of_range_vital_signs_are_rejected_atomically(
    user_factory,
    field_name,
    outside_value,
):
    patient = Patient.objects.create(**patient_attributes())
    user, _ = create_professional_user(user_factory)

    with pytest.raises(ValidationError) as error:
        create_admission(
            actor=professional_actor(user),
            patient=patient,
            **admission_data(**{field_name: outside_value}),
        )

    assert field_name in error.value.message_dict
    assert Admission.objects.count() == 0


@override_settings(
    CLINICAL_VITAL_SIGN_RANGES={
        "systolic_blood_pressure": {
            "minimum": "100",
            "maximum": "140",
            "unit": "custom-systolic-unit",
        },
        "diastolic_blood_pressure": {
            "minimum": "60",
            "maximum": "90",
            "unit": "custom-diastolic-unit",
        },
        "heart_rate": {"minimum": "50", "maximum": "100", "unit": "beats"},
        "temperature": {
            "minimum": "35.0",
            "maximum": "38.0",
            "unit": "custom-temperature-unit",
        },
    }
)
def test_vital_ranges_and_units_are_runtime_configurable():
    form = AdmissionForm()

    assert (
        "100–140 custom-systolic-unit"
        in form.fields["systolic_blood_pressure"].help_text
    )
    assert form.fields["temperature"].widget.attrs["max"] == "38.0"


@pytest.mark.django_db
def test_creation_rejects_missing_wrong_inactive_and_unlinked_professional_actors(
    user_factory,
):
    patient = Patient.objects.create(**patient_attributes())

    with pytest.raises(PermissionError):
        create_admission(actor=None, patient=patient, **admission_data())

    administrative_user = user_factory(username="admission-admin")
    with pytest.raises(PermissionError):
        create_admission(
            actor=ActorContext(
                user_id=administrative_user.pk,
                roles=frozenset({ActorRole.ADMINISTRATIVE}),
            ),
            patient=patient,
            **admission_data(),
        )

    unlinked_user = user_factory(username="unlinked-professional")
    with pytest.raises(PermissionDenied):
        create_admission(
            actor=professional_actor(unlinked_user),
            patient=patient,
            **admission_data(),
        )

    inactive_user, inactive_professional = create_professional_user(
        user_factory,
        username="inactive-professional",
    )
    inactive_professional.is_active = False
    inactive_professional.save(update_fields=["is_active"])
    with pytest.raises(PermissionDenied):
        create_admission(
            actor=professional_actor(inactive_user),
            patient=patient,
            **admission_data(),
        )

    assert Admission.objects.count() == 0


@pytest.mark.django_db
def test_creation_rejects_an_inactive_patient_without_partial_write(user_factory):
    patient = Patient.all_objects.create(**patient_attributes(is_active=False))
    user, _ = create_professional_user(user_factory)

    with pytest.raises(InactivePatientError):
        create_admission(
            actor=professional_actor(user),
            patient=patient,
            **admission_data(),
        )

    assert Admission.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("reason", ["", "   "])
def test_creation_rejects_blank_consultation_reason_atomically(user_factory, reason):
    patient = Patient.objects.create(**patient_attributes())
    user, _ = create_professional_user(user_factory)

    with pytest.raises(ValidationError) as error:
        create_admission(
            actor=professional_actor(user),
            patient=patient,
            **admission_data(consultation_reason=reason),
        )

    assert "consultation_reason" in error.value.message_dict
    assert Admission.objects.count() == 0


@pytest.mark.django_db
def test_api_rejects_server_owned_metadata_and_uses_authenticated_professional(
    client,
    user_factory,
):
    patient = Patient.objects.create(**patient_attributes())
    user, professional = create_professional_user(user_factory)
    _, other_professional = create_professional_user(
        user_factory,
        username="metadata-override-target",
    )
    client.force_login(user)
    url = reverse("clinical_records:api-create-admission", args=[patient.pk])
    payload = {
        **admission_data(),
        "professional_id": other_professional.pk,
        "created_at": "2000-01-01T00:00:00Z",
    }

    rejected_response = client.post(url, payload)

    assert rejected_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "professional_id" in rejected_response.json()
    assert "created_at" in rejected_response.json()
    assert Admission.objects.count() == 0

    before_creation = timezone.now()
    response = client.post(url, admission_data())
    after_creation = timezone.now()
    admission = Admission.objects.get()

    assert response.status_code == status.HTTP_201_CREATED
    assert admission.professional == professional
    assert before_creation <= admission.created_at <= after_creation


@pytest.mark.django_db
def test_api_authorization_rejects_anonymous_admin_and_inactive_professional(
    client,
    user_factory,
):
    patient = Patient.objects.create(**patient_attributes())
    url = reverse("clinical_records:api-create-admission", args=[patient.pk])

    assert client.post(url, admission_data()).status_code == status.HTTP_403_FORBIDDEN

    admin = user_factory(username="api-admission-admin")
    admin.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))
    client.force_login(admin)
    assert client.post(url, admission_data()).status_code == status.HTTP_403_FORBIDDEN

    inactive_user, inactive_professional = create_professional_user(
        user_factory,
        username="api-inactive-professional",
    )
    inactive_professional.is_active = False
    inactive_professional.save(update_fields=["is_active"])
    client.force_login(inactive_user)
    assert client.post(url, admission_data()).status_code == status.HTTP_403_FORBIDDEN
    assert Admission.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("profile_state", ["missing", "inactive"])
def test_api_checks_active_professional_before_patient_lookup_or_validation(
    client,
    user_factory,
    profile_state,
):
    patient = Patient.objects.create(**patient_attributes())
    user = user_factory(username=f"api-{profile_state}-profile")
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    if profile_state == "inactive":
        Professional.objects.create(user=user, is_active=False)
    client.force_login(user)

    for patient_pk in (patient.pk, 999_999_999):
        response = client.post(
            reverse("clinical_records:api-create-admission", args=[patient_pk]),
            {},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    assert Admission.objects.count() == 0


@pytest.mark.django_db
def test_api_rejects_a_non_object_json_body_without_server_error(
    client,
    user_factory,
):
    patient = Patient.objects.create(**patient_attributes())
    user, _ = create_professional_user(user_factory)
    client.force_login(user)

    response = client.post(
        reverse("clinical_records:api-create-admission", args=[patient.pk]),
        [{}],
        content_type="application/json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Admission.objects.count() == 0


@pytest.mark.django_db
def test_htmx_admission_reports_specific_missing_and_invalid_values(
    client,
    user_factory,
):
    patient = Patient.objects.create(**patient_attributes())
    user, _ = create_professional_user(user_factory)
    client.force_login(user)
    payload = admission_data(systolic_blood_pressure=251)
    payload.pop("diastolic_blood_pressure")

    response = client.post(
        reverse("clinical_records:patient-admissions", args=[patient.pk]),
        payload,
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert b'data-field-error="systolic_blood_pressure"' in response.content
    assert b'data-field-error="diastolic_blood_pressure"' in response.content
    assert Admission.objects.count() == 0


@pytest.mark.django_db
def test_non_htmx_admission_uses_post_redirect_get(client, user_factory):
    patient = Patient.objects.create(**patient_attributes())
    user, _ = create_professional_user(user_factory)
    client.force_login(user)
    url = reverse("clinical_records:patient-admissions", args=[patient.pk])

    response = client.post(url, admission_data())

    assert response.status_code == 302
    assert response.url == url
    assert Admission.objects.count() == 1

    destination = client.get(response.url)
    assert destination.status_code == 200
    assert b"<!doctype html>" in destination.content
    assert b"Persistent headache" in destination.content


@pytest.mark.django_db
def test_medical_search_finds_active_patient_and_links_to_admission_form(
    client,
    user_factory,
):
    patient = Patient.objects.create(**patient_attributes())
    user, _ = create_professional_user(user_factory)
    client.force_login(user)

    response = client.get(
        reverse("clinical_records:admission-search"),
        {"dni": f"  {patient.dni}  "},
    )

    assert response.status_code == 200
    assert f"{patient.first_name} {patient.last_name}".encode() in response.content
    assert patient.clinical_record_number.encode() in response.content
    assert (
        reverse(
            "clinical_records:patient-admissions",
            args=[patient.pk],
        ).encode()
        in response.content
    )
    assert b"Record admission for Alex Patient" in response.content


@pytest.mark.django_db
def test_clinical_workspace_lists_all_active_patients_and_excludes_inactive(
    client,
    user_factory,
):
    first_patient = Patient.objects.create(**patient_attributes())
    second_patient = Patient.objects.create(
        **patient_attributes(
            dni="87654321",
            clinical_record_number="HC-ADMISSION-02",
            first_name="Second",
        )
    )
    inactive_patient = Patient.all_objects.create(
        **patient_attributes(
            dni="11223344",
            clinical_record_number="HC-ADMISSION-03",
            first_name="Inactive",
            is_active=False,
        )
    )
    user, _ = create_professional_user(user_factory)
    client.force_login(user)

    response = client.get(reverse("clinical_records:dashboard"))

    assert response.status_code == 200
    for patient in (first_patient, second_patient):
        assert f'data-active-patient-id="{patient.pk}"'.encode() in response.content
        assert patient.dni.encode() in response.content
        assert patient.clinical_record_number.encode() in response.content
    assert (
        f'data-active-patient-id="{inactive_patient.pk}"'.encode()
        not in response.content
    )
    assert inactive_patient.dni.encode() not in response.content


@pytest.mark.django_db
@pytest.mark.parametrize("patient_exists", [False, True])
def test_medical_search_does_not_offer_admission_for_missing_or_inactive_patient(
    client,
    user_factory,
    patient_exists,
):
    if patient_exists:
        Patient.all_objects.create(**patient_attributes(is_active=False))
    user, _ = create_professional_user(user_factory)
    client.force_login(user)

    response = client.get(
        reverse("clinical_records:admission-search"),
        {"dni": "12345678"},
    )

    assert response.status_code == 200
    assert b"No active patient matches DNI 12345678." in response.content
    assert b"Record admission for" not in response.content


@pytest.mark.django_db
def test_medical_search_reports_invalid_dni_and_rejects_non_professional(
    client,
    user_factory,
):
    user, _ = create_professional_user(user_factory)
    client.force_login(user)
    results_url = reverse("clinical_records:admission-search-results")

    invalid_response = client.get(
        results_url,
        {"dni": "12.345.678"},
        HTTP_HX_REQUEST="true",
    )

    assert invalid_response.status_code == 422
    assert b'data-field-error="dni"' in invalid_response.content

    administrator = user_factory(username="admission-search-admin")
    administrator.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))
    client.force_login(administrator)
    assert client.get(results_url, {"dni": "12345678"}).status_code == 403


@pytest.mark.django_db
def test_htmx_success_displays_the_persisted_admission_metadata(
    client,
    user_factory,
):
    patient = Patient.objects.create(**patient_attributes())
    user, _ = create_professional_user(
        user_factory,
        username="display-professional",
    )
    client.force_login(user)

    response = client.post(
        reverse("clinical_records:patient-admissions", args=[patient.pk]),
        admission_data(),
        HTTP_HX_REQUEST="true",
    )
    admission = Admission.objects.get()

    assert response.status_code == 200
    for value in (
        admission.consultation_reason,
        str(admission.systolic_blood_pressure),
        str(admission.diastolic_blood_pressure),
        str(admission.heart_rate),
        str(admission.temperature),
        user.get_username(),
    ):
        assert value.encode() in response.content
    assert admission.created_at.isoformat().encode() in response.content


@pytest.mark.django_db
def test_administrative_patient_record_displays_saved_admission(
    client,
    user_factory,
):
    patient = Patient.objects.create(**patient_attributes())
    professional_user, _ = create_professional_user(user_factory)
    admission = create_admission(
        actor=professional_actor(professional_user),
        patient=patient,
        **admission_data(),
    )
    admin = user_factory(username="admission-record-admin")
    admin.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))
    client.force_login(admin)

    response = client.get(reverse("patients:detail", args=[patient.pk]))

    assert response.status_code == 200
    assert f'data-admission-id="{admission.pk}"'.encode() in response.content
    assert professional_user.get_username().encode() in response.content
    assert admission.created_at.isoformat().encode() in response.content
