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
