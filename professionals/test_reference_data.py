import pytest

from professionals.models import HospitalService, Specialty

EXPECTED_SPECIALTIES = {
    "cardiology": "Cardiology",
    "emergency-medicine": "Emergency Medicine",
    "general-medicine": "General Medicine",
    "general-surgery": "General Surgery",
    "gynecology-obstetrics": "Gynecology and Obstetrics",
    "pediatrics": "Pediatrics",
}

EXPECTED_HOSPITAL_SERVICES = {
    "emergency-department": "Emergency Department",
    "inpatient-ward": "Inpatient Ward",
    "intensive-care-unit": "Intensive Care Unit",
    "operating-room": "Operating Room",
    "outpatient-clinic": "Outpatient Clinic",
}


@pytest.mark.django_db
def test_clean_migrations_expose_active_seeded_reference_data():
    specialties = {
        specialty.code: specialty.name
        for specialty in Specialty.objects.filter(is_active=True)
    }
    services = {
        service.code: service.name
        for service in HospitalService.objects.filter(is_active=True)
    }

    assert specialties == EXPECTED_SPECIALTIES
    assert services == EXPECTED_HOSPITAL_SERVICES


@pytest.mark.django_db
def test_reference_codes_and_names_are_unique():
    specialty = Specialty.objects.get(code="cardiology")
    service = HospitalService.objects.get(code="emergency-department")

    assert Specialty._meta.get_field("code").unique is True
    assert Specialty._meta.get_field("name").unique is True
    assert HospitalService._meta.get_field("code").unique is True
    assert HospitalService._meta.get_field("name").unique is True
    assert str(specialty) == "Cardiology"
    assert str(service) == "Emergency Department"
