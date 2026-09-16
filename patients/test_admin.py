from datetime import date

import pytest
from django.contrib import admin

from patients.admin import PatientAdmin
from patients.models import Patient


@pytest.mark.django_db
def test_admin_allows_dni_on_add_but_protects_it_on_change(rf):
    patient_admin = PatientAdmin(Patient, admin.site)
    request = rf.get("/admin/patients/patient/")
    patient = Patient.objects.create(
        dni="12345678",
        first_name="Alex",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        sex="unspecified",
        phone="+54 11 5555-0101",
        email="alex.patient@example.test",
        address="123 Test Street",
        health_insurer="Test Health",
    )

    assert patient_admin.get_readonly_fields(request, obj=None) == (
        "clinical_record_number",
    )
    assert patient_admin.get_readonly_fields(request, obj=patient) == (
        "clinical_record_number",
        "dni",
    )


@pytest.mark.django_db
def test_admin_inactive_filter_includes_retained_deactivated_patients(
    client, user_factory
):
    administrator = user_factory(username="inactive-patient-admin", is_staff=True)
    administrator.is_superuser = True
    administrator.save(update_fields=("is_superuser",))
    active_patient = Patient.objects.create(
        dni="12345678",
        first_name="Active",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        sex="unspecified",
        phone="+54 11 5555-0101",
        email="active.patient@example.test",
        address="123 Test Street",
        health_insurer="Test Health",
    )
    inactive_patient = Patient.all_objects.create(
        dni="87654321",
        first_name="Inactive",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        sex="unspecified",
        phone="+54 11 5555-0102",
        email="inactive.patient@example.test",
        address="456 Test Street",
        health_insurer="Test Health",
        is_active=False,
    )

    client.force_login(administrator)
    response = client.get("/admin/patients/patient/", {"is_active__exact": "0"})

    assert response.status_code == 200
    assert inactive_patient in response.context["cl"].result_list
    assert active_patient not in response.context["cl"].result_list
