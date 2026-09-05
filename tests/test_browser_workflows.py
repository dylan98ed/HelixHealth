import re
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from playwright.sync_api import Page, expect

from access_control.roles import ADMINISTRATIVE_GROUP, MEDICAL_PROFESSIONAL_GROUP
from clinical_records.models import Admission
from patients.identifiers import generate_clinical_record_number
from patients.models import Patient
from professionals.models import Professional

TEST_PASSWORD = "Browser-test-password-2026!"


@pytest.fixture
def browser_superuser(user_factory):
    return user_factory(
        username="browser-superuser",
        password=TEST_PASSWORD,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def browser_patient_administrator(user_factory):
    user = user_factory(
        username="browser-patient-administrator",
        password=TEST_PASSWORD,
        is_staff=False,
    )
    administrative_group, _ = Group.objects.get_or_create(name=ADMINISTRATIVE_GROUP)
    user.groups.add(administrative_group)
    return user


@pytest.fixture
def browser_medical_professional(user_factory):
    user = user_factory(
        username="browser-medical-professional",
        password=TEST_PASSWORD,
        is_staff=False,
    )
    medical_group, _ = Group.objects.get_or_create(name=MEDICAL_PROFESSIONAL_GROUP)
    user.groups.add(medical_group)
    return user


@pytest.fixture
def browser_legacy_staff_medical_professional(user_factory):
    user = user_factory(
        username="browser-legacy-staff-medical-professional",
        password=TEST_PASSWORD,
        is_staff=True,
    )
    medical_group, _ = Group.objects.get_or_create(name=MEDICAL_PROFESSIONAL_GROUP)
    user.groups.add(medical_group)
    return user


@pytest.fixture
def browser_admission_patient(browser_medical_professional):
    return Patient.objects.create(
        dni="11223344",
        clinical_record_number="HC-BROWSER-ADMISSION",
        first_name="Admission",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        sex="unspecified",
        phone="+54 11 5555-0188",
        email="admission.patient@example.test",
        address="Admission Test Street 123",
        health_insurer="Browser Health",
    )


@pytest.fixture
def browser_inactive_admission_patient(browser_medical_professional):
    return Patient.all_objects.create(
        dni="88776655",
        clinical_record_number="HC-BROWSER-INACTIVE",
        first_name="Archived",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        sex="unspecified",
        phone="+54 11 5555-0189",
        email="archived.patient@example.test",
        address="Archived Test Street 123",
        health_insurer="Browser Health",
        is_active=False,
    )


@pytest.fixture
def next_clinical_record_number(browser_patient_administrator):
    previous_number = generate_clinical_record_number()
    next_value = int(previous_number.removeprefix("HC-")) + 1
    return f"HC-{next_value:08d}"


@pytest.fixture
def browser_search_patient(browser_patient_administrator):
    return Patient.objects.create(
        dni="13572468",
        clinical_record_number="HC-BROWSER-SEARCH",
        first_name="Searchable",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        sex="unspecified",
        phone="+54 11 5555-0177",
        email="searchable.patient@example.test",
        address="Search Test Street 123",
        health_insurer="Search Health",
    )


@pytest.fixture
def browser_paginated_patients(browser_medical_professional):
    return [
        Patient.objects.create(
            dni=f"300000{offset:02d}",
            clinical_record_number=f"HC-BROWSER-PAGE-{offset:02d}",
            first_name=f"Patient {offset:02d}",
            last_name="Zpagination",
            date_of_birth=date(1990, 1, 1),
            sex="unspecified",
            phone="+54 11 5555-0198",
            email=f"page-{offset:02d}@example.test",
            address="Pagination Test Street 123",
            health_insurer="Browser Health",
        )
        for offset in range(21)
    ]


def create_history_patient(*, dni: str, clinical_record_number: str) -> Patient:
    patient = Patient.objects.create(
        dni=dni,
        clinical_record_number=clinical_record_number,
        first_name="History",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        sex="unspecified",
        phone="+54 11 5555-0166",
        email=f"{dni}@example.test",
        address="History Test Street 123",
        health_insurer="Browser Health",
    )
    history_professional = Professional.objects.create(
        user=get_user_model().objects.create_user(
            username=f"history-professional-{dni}",
            password=TEST_PASSWORD,
        )
    )
    Admission.objects.bulk_create(
        [
            Admission(
                patient=patient,
                professional=history_professional,
                consultation_reason=f"Browser history {offset}",
                systolic_blood_pressure=120,
                diastolic_blood_pressure=80,
                heart_rate=72,
                temperature="36.7",
            )
            for offset in range(21)
        ]
    )
    return patient


@pytest.fixture
def browser_medical_history_patient(browser_medical_professional):
    return create_history_patient(
        dni="31112223",
        clinical_record_number="HC-BROWSER-MEDICAL-HISTORY",
    )


@pytest.fixture
def browser_administrative_history_patient(browser_patient_administrator):
    return create_history_patient(
        dni="32223334",
        clinical_record_number="HC-BROWSER-ADMIN-HISTORY",
    )


def login_through_admin(
    page: Page,
    live_server_url: str,
    *,
    username: str,
    password: str,
) -> None:
    page.goto(f"{live_server_url}{reverse('admin:login')}")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Log in").click()
    expect(page.get_by_role("heading", name="Site administration")).to_be_visible()


def login_through_application(
    page: Page,
    live_server_url: str,
    *,
    username: str,
    password: str,
) -> None:
    page.goto(f"{live_server_url}{reverse('home')}")
    page.get_by_role("link", name="Sign in").click()
    expect(page).to_have_url(f"{live_server_url}{reverse('login')}")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_legacy_admin_login_redirects_medical_professional_to_workspace(
    browser_legacy_staff_medical_professional,
    live_server,
    browser_page,
):
    browser_page.goto(f"{live_server.url}{reverse('admin:login')}")
    browser_page.get_by_label("Username").fill(
        browser_legacy_staff_medical_professional.username
    )
    browser_page.get_by_label("Password").fill(TEST_PASSWORD)
    browser_page.get_by_role("button", name="Log in").click()

    dashboard_url = reverse("clinical_records:dashboard")
    expect(browser_page).to_have_url(f"{live_server.url}{dashboard_url}")
    expect(
        browser_page.get_by_role("heading", name="Clinical workspace")
    ).to_be_visible()


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_superuser_creates_user_through_admin(
    browser_superuser,
    live_server,
    browser_page,
):
    login_through_admin(
        browser_page,
        live_server.url,
        username=browser_superuser.username,
        password=TEST_PASSWORD,
    )

    browser_page.goto(f"{live_server.url}{reverse('admin:auth_user_add')}")
    expect(browser_page.get_by_role("heading", name="Add user")).to_be_visible()
    browser_page.get_by_label("Username").fill("browser-created-user")
    browser_page.locator("#id_password1").fill(TEST_PASSWORD)
    browser_page.locator("#id_password2").fill(TEST_PASSWORD)
    browser_page.get_by_role("button", name="Save", exact=True).click()

    expect(browser_page).to_have_url(re.compile(r"/admin/auth/user/\d+/change/$"))
    expect(
        browser_page.get_by_text(re.compile(r"was added successfully"))
    ).to_be_visible()
    expect(
        browser_page.get_by_role("heading", name="browser-created-user")
    ).to_be_visible()


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_administrative_user_registers_patient_through_ui(
    browser_patient_administrator,
    next_clinical_record_number,
    live_server,
    browser_page,
):
    login_through_application(
        browser_page,
        live_server.url,
        username=browser_patient_administrator.username,
        password=TEST_PASSWORD,
    )
    expect(browser_page).to_have_url(f"{live_server.url}{reverse('patients:search')}")
    expect(browser_page.get_by_role("heading", name="Search patients")).to_be_visible()
    browser_page.get_by_label("DNI").fill("24681357")
    browser_page.get_by_role("button", name="Search patient").click()
    expect(browser_page.get_by_text("No patient matches DNI 24681357.")).to_be_visible()
    browser_page.get_by_role("link", name="Register a new patient").click()
    expect(browser_page).to_have_url(
        f"{live_server.url}{reverse('patients:register')}?dni=24681357"
    )

    expect(browser_page.get_by_label("Dni")).to_have_value("24681357")
    browser_page.get_by_label("First name").fill("Browser")
    browser_page.get_by_label("Last name").fill("Patient")
    browser_page.get_by_label("Date of birth").fill("1990-01-01")
    browser_page.get_by_label("Sex").fill("unspecified")
    browser_page.get_by_label("Phone").fill("+54 11 5555-0199")
    browser_page.get_by_label("Email").fill("browser.patient@example.test")
    browser_page.get_by_label("Address").fill("Browser Test Street 123")
    browser_page.get_by_label("Health insurer").fill("Browser Health")
    browser_page.get_by_label("Phone").fill("invalid")
    browser_page.get_by_role("button", name="Register patient").click()

    expect(browser_page.locator('[data-field-error="phone"]')).to_be_visible()
    expect(browser_page.get_by_role("status")).to_have_count(0)

    browser_page.get_by_label("Phone").fill("+54 11 5555-0199")
    browser_page.get_by_role("button", name="Register patient").click()

    result = browser_page.get_by_role("status")
    expect(result).to_contain_text("Patient registered")
    expect(result).to_contain_text(next_clinical_record_number)

    browser_page.get_by_role("link", name="Open patient record").click()
    expect(browser_page).to_have_url(re.compile(r"/patients/\d+/$"))
    expect(browser_page.get_by_role("heading", name="Browser Patient")).to_be_visible()
    expect(browser_page.get_by_text("24681357", exact=True)).to_be_visible()
    expect(browser_page.get_by_text(re.compile(r"HC-\d{8,}"))).to_be_visible()
    expect(browser_page.get_by_text("Active", exact=True)).to_be_visible()
    browser_page.get_by_role("link", name="Edit patient").click()
    expect(browser_page.get_by_role("heading", name="Edit patient")).to_be_visible()
    browser_page.get_by_label("Phone").fill("+54 11 5555-0123")
    browser_page.get_by_role("button", name="Save changes").click()
    expect(browser_page.get_by_text("+54 11 5555-0123", exact=True)).to_be_visible()

    browser_page.get_by_role("link", name="Deactivate patient").click()
    expect(
        browser_page.get_by_role("heading", name="Deactivate patient")
    ).to_be_visible()
    browser_page.get_by_role("button", name="Deactivate patient").click()
    expect(
        browser_page.get_by_text("Patient deactivation requires explicit confirmation.")
    ).to_be_visible()
    browser_page.get_by_label("I confirm this patient should be deactivated.").check()
    browser_page.get_by_role("button", name="Deactivate patient").click()
    expect(browser_page).to_have_url(re.compile(r"/patients/\d+/$"))
    expect(browser_page.get_by_text("Inactive", exact=True)).to_be_visible()
    expect(browser_page.get_by_role("link", name="Edit patient")).to_have_count(0)
    expect(browser_page.get_by_role("link", name="Deactivate patient")).to_have_count(0)


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_administrative_user_searches_patient_and_prefills_registration(
    browser_patient_administrator,
    browser_search_patient,
    live_server,
    browser_page,
):
    login_through_application(
        browser_page,
        live_server.url,
        username=browser_patient_administrator.username,
        password=TEST_PASSWORD,
    )

    expect(browser_page).to_have_url(f"{live_server.url}{reverse('patients:search')}")
    browser_page.get_by_label("DNI").fill("13572468")
    browser_page.get_by_role("button", name="Search patient").click()

    expect(browser_page).to_have_url(f"{live_server.url}{reverse('patients:search')}")
    expect(browser_page.get_by_role("heading", name="Search patients")).to_be_visible()
    expect(browser_page.get_by_label("DNI")).to_have_value("13572468")
    expect(browser_page.get_by_text("Searchable Patient", exact=False)).to_be_visible()
    expect(
        browser_page.get_by_text(browser_search_patient.clinical_record_number)
    ).to_be_visible()
    browser_page.get_by_role("link", name="Open patient record").click()
    expect(browser_page).to_have_url(re.compile(r"/patients/\d+/$"))
    expect(
        browser_page.get_by_role("heading", name="Searchable Patient")
    ).to_be_visible()

    browser_page.get_by_role("link", name="Patient search").click()
    browser_page.get_by_label("DNI").fill("87654321")
    browser_page.get_by_role("button", name="Search patient").click()
    expect(browser_page.get_by_text("No patient matches DNI 87654321.")).to_be_visible()
    browser_page.get_by_role("link", name="Register a new patient").click()

    expect(browser_page).to_have_url(
        f"{live_server.url}{reverse('patients:register')}?dni=87654321"
    )
    expect(browser_page.get_by_label("Dni")).to_have_value("87654321")


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_medical_professional_records_admission_through_ui(
    browser_medical_professional,
    browser_admission_patient,
    live_server,
    browser_page,
):
    login_through_application(
        browser_page,
        live_server.url,
        username=browser_medical_professional.username,
        password=TEST_PASSWORD,
    )
    dashboard_url = reverse("clinical_records:dashboard")
    expect(browser_page).to_have_url(f"{live_server.url}{dashboard_url}")
    expect(
        browser_page.get_by_role("heading", name="Clinical workspace")
    ).to_be_visible()
    patient_card = browser_page.locator(
        f'[data-active-patient-id="{browser_admission_patient.pk}"]'
    )
    expect(patient_card.get_by_text("Admission Patient", exact=True)).to_be_visible()
    expect(patient_card.get_by_text(browser_admission_patient.dni)).to_be_visible()
    expect(
        patient_card.get_by_text(browser_admission_patient.clinical_record_number)
    ).to_be_visible()
    patient_card.get_by_role(
        "link", name="Record admission for Admission Patient"
    ).click()
    admission_url = reverse(
        "clinical_records:patient-admissions",
        args=[browser_admission_patient.pk],
    )
    expect(browser_page).to_have_url(f"{live_server.url}{admission_url}")

    expect(
        browser_page.get_by_role("heading", name="Patient admission")
    ).to_be_visible()
    browser_page.get_by_label("Consultation reason").fill("Browser headache")
    browser_page.get_by_label("Systolic blood pressure").fill("251")
    browser_page.get_by_label("Heart rate").fill("72")
    browser_page.get_by_label("Temperature").fill("36.7")
    browser_page.get_by_role("button", name="Record admission").click()

    expect(
        browser_page.locator('[data-field-error="systolic_blood_pressure"]')
    ).to_be_visible()
    expect(
        browser_page.locator('[data-field-error="diastolic_blood_pressure"]')
    ).to_be_visible()
    browser_page.get_by_label("Systolic blood pressure").fill("120")
    browser_page.get_by_label("Diastolic blood pressure").fill("80")
    browser_page.get_by_role("button", name="Record admission").click()

    result = browser_page.get_by_role("status")
    expect(result).to_contain_text("Admission recorded")
    expect(browser_page.get_by_text("Browser headache", exact=True)).to_be_visible()
    expect(browser_page.get_by_text("120/80 mmHg", exact=False)).to_be_visible()
    expect(browser_page.get_by_text("72 bpm", exact=True)).to_be_visible()
    expect(browser_page.get_by_text("36.7 degrees Celsius", exact=True)).to_be_visible()
    expect(
        browser_page.locator("#admission-workflow").get_by_text(
            browser_medical_professional.username,
            exact=True,
        )
    ).to_be_visible()

    browser_page.goto(f"{live_server.url}{admission_url}")
    history = browser_page.get_by_role("region", name="Admission history")
    expect(history.get_by_text("Browser headache", exact=True)).to_be_visible()
    expect(history.get_by_text("120/80 mmHg", exact=False)).to_be_visible()
    expect(
        history.get_by_text(browser_medical_professional.username, exact=True)
    ).to_be_visible()


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_medical_workspace_paginates_active_patients_through_visible_controls(
    browser_medical_professional,
    browser_paginated_patients,
    live_server,
    browser_page,
):
    login_through_application(
        browser_page,
        live_server.url,
        username=browser_medical_professional.username,
        password=TEST_PASSWORD,
    )

    first_page_patient = browser_paginated_patients[0]
    second_page_patient = browser_paginated_patients[-1]
    expect(browser_page.get_by_text(first_page_patient.dni, exact=True)).to_be_visible()
    expect(browser_page.get_by_text(second_page_patient.dni, exact=True)).to_have_count(
        0
    )
    pagination = browser_page.get_by_role(
        "navigation", name="Active patients pagination"
    )
    pagination.get_by_role("link", name="Next").click()
    expect(browser_page).to_have_url(
        f"{live_server.url}{reverse('clinical_records:dashboard')}?page=2"
    )
    expect(
        browser_page.get_by_text(second_page_patient.dni, exact=True)
    ).to_be_visible()
    expect(browser_page.get_by_text(first_page_patient.dni, exact=True)).to_have_count(
        0
    )


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_medical_professional_paginates_admission_history_through_visible_controls(
    browser_medical_professional,
    browser_medical_history_patient,
    live_server,
    browser_page,
):
    login_through_application(
        browser_page,
        live_server.url,
        username=browser_medical_professional.username,
        password=TEST_PASSWORD,
    )
    patient_card = browser_page.locator(
        f'[data-active-patient-id="{browser_medical_history_patient.pk}"]'
    )
    patient_card.get_by_role(
        "link", name="Record admission for History Patient"
    ).click()
    expect(browser_page.get_by_text("Browser history 20", exact=True)).to_be_visible()
    pagination = browser_page.get_by_role(
        "navigation", name="Admission history pagination"
    )
    pagination.get_by_role("link", name="Next").click()
    expect(browser_page).to_have_url(re.compile(r"/admissions/\?history_page=2$"))
    expect(browser_page.get_by_text("Browser history 0", exact=True)).to_be_visible()
    expect(pagination.get_by_role("link", name="Previous")).to_be_visible()


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_administrative_user_paginates_patient_history_through_visible_controls(
    browser_patient_administrator,
    browser_administrative_history_patient,
    live_server,
    browser_page,
):
    login_through_application(
        browser_page,
        live_server.url,
        username=browser_patient_administrator.username,
        password=TEST_PASSWORD,
    )
    browser_page.get_by_label("DNI").fill(browser_administrative_history_patient.dni)
    browser_page.get_by_role("button", name="Search patient").click()
    browser_page.get_by_role("link", name="Open patient record").click()
    expect(browser_page.get_by_text("Browser history 20", exact=True)).to_be_visible()
    pagination = browser_page.get_by_role("navigation", name="Admissions pagination")
    pagination.get_by_role("link", name="Next").click()
    expect(browser_page).to_have_url(re.compile(r"/patients/\d+/\?history_page=2$"))
    expect(browser_page.get_by_text("Browser history 0", exact=True)).to_be_visible()
    expect(pagination.get_by_role("link", name="Previous")).to_be_visible()


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_medical_professional_cannot_open_inactive_patient_by_internal_id(
    browser_medical_professional,
    browser_inactive_admission_patient,
    live_server,
    browser_page,
):
    login_through_application(
        browser_page,
        live_server.url,
        username=browser_medical_professional.username,
        password=TEST_PASSWORD,
    )
    dashboard_url = reverse("clinical_records:dashboard")
    expect(browser_page).to_have_url(f"{live_server.url}{dashboard_url}")
    expect(
        browser_page.get_by_text(browser_inactive_admission_patient.dni, exact=True)
    ).to_have_count(0)

    inactive_admission_url = reverse(
        "clinical_records:patient-admissions",
        args=[browser_inactive_admission_patient.pk],
    )
    denied_response = browser_page.goto(f"{live_server.url}{inactive_admission_url}")

    assert denied_response is not None
    assert denied_response.status == 404
    expect(
        browser_page.get_by_text(browser_inactive_admission_patient.dni, exact=True)
    ).to_have_count(0)
