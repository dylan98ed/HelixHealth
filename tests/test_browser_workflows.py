import re

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from playwright.sync_api import Page, expect

from access_control.roles import ADMINISTRATIVE_GROUP
from patients.identifiers import generate_clinical_record_number

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
