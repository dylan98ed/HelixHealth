import re

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from playwright.sync_api import Page, expect

from access_control.roles import ADMINISTRATIVE_GROUP

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
    browser_page.get_by_role("button", name="Register patient").click()

    result = browser_page.get_by_role("status")
    expect(result).to_contain_text("Patient registered")
    expect(result).to_contain_text(re.compile(r"HC-\d{8,}"))

    browser_page.get_by_role("link", name="Open patient record").click()
    expect(browser_page).to_have_url(re.compile(r"/patients/\d+/$"))
    expect(browser_page.get_by_role("heading", name="Browser Patient")).to_be_visible()
    expect(browser_page.get_by_text("24681357", exact=True)).to_be_visible()
    expect(browser_page.get_by_text(re.compile(r"HC-\d{8,}"))).to_be_visible()
    expect(browser_page.get_by_text("Active", exact=True)).to_be_visible()
