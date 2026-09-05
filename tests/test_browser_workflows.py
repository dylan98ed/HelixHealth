import re
from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from playwright.sync_api import Page, expect

from access_control.roles import ADMINISTRATIVE_GROUP, MEDICAL_PROFESSIONAL_GROUP
from patients.identifiers import generate_clinical_record_number
from patients.models import Patient

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
        is_staff=True,
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
    login_through_admin(
        browser_page,
        live_server.url,
        username=browser_patient_administrator.username,
        password=TEST_PASSWORD,
    )

    browser_page.goto(f"{live_server.url}{reverse('patients:register')}")
    browser_page.get_by_label("Dni").fill("24681357")
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


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_administrative_user_searches_patient_and_prefills_registration(
    browser_patient_administrator,
    live_server,
    browser_page,
):
    login_through_admin(
        browser_page,
        live_server.url,
        username=browser_patient_administrator.username,
        password=TEST_PASSWORD,
    )

    browser_page.goto(f"{live_server.url}{reverse('patients:register')}")
    browser_page.get_by_label("Dni").fill("13572468")
    browser_page.get_by_label("First name").fill("Searchable")
    browser_page.get_by_label("Last name").fill("Patient")
    browser_page.get_by_label("Date of birth").fill("1990-01-01")
    browser_page.get_by_label("Sex").fill("unspecified")
    browser_page.get_by_label("Phone").fill("+54 11 5555-0177")
    browser_page.get_by_label("Email").fill("searchable.patient@example.test")
    browser_page.get_by_label("Address").fill("Search Test Street 123")
    browser_page.get_by_label("Health insurer").fill("Search Health")
    browser_page.get_by_role("button", name="Register patient").click()
    registration_result = browser_page.get_by_role("status")
    expect(registration_result).to_contain_text("Patient registered")
    clinical_record_number = re.search(r"HC-\d{8,}", registration_result.text_content())
    assert clinical_record_number is not None

    browser_page.goto(f"{live_server.url}{reverse('home')}")
    browser_page.get_by_role("link", name="Patient search").click()
    browser_page.get_by_label("DNI").fill("13572468")
    browser_page.get_by_role("button", name="Search patient").click()

    expect(browser_page).to_have_url(f"{live_server.url}{reverse('patients:search')}")
    expect(browser_page.get_by_role("heading", name="Search patients")).to_be_visible()
    expect(browser_page.get_by_label("DNI")).to_have_value("13572468")
    expect(browser_page.get_by_text("Searchable Patient", exact=False)).to_be_visible()
    expect(browser_page.get_by_text(clinical_record_number.group())).to_be_visible()
    browser_page.get_by_role("link", name="Open patient record").click()
    expect(browser_page).to_have_url(re.compile(r"/patients/\d+/$"))
    expect(
        browser_page.get_by_role("heading", name="Searchable Patient")
    ).to_be_visible()

    browser_page.goto(f"{live_server.url}{reverse('patients:search')}")
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
