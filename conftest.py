from pathlib import Path

import pytest
from django.db import connection
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from tests.factories import UserFactory


@pytest.fixture
def postgresql_db(db):
    """Provide an initialized test database and enforce the PostgreSQL contract."""
    assert connection.vendor == "postgresql"
    assert connection.settings_dict["ENGINE"] == "django.db.backends.postgresql"
    connection.ensure_connection()
    return connection


@pytest.fixture
def user_factory(django_user_model, postgresql_db):
    """Build persisted users with unique defaults on the PostgreSQL test database."""
    return UserFactory(django_user_model)


@pytest.fixture
def assign_patient(user_factory):
    from django.contrib.auth.models import Group

    from access_control.actors import actor_context_from_user
    from access_control.roles import ADMINISTRATIVE_GROUP
    from clinical_records.care_services import assign_care_relationship

    admin = user_factory()
    admin.groups.add(Group.objects.get_or_create(name=ADMINISTRATIVE_GROUP)[0])

    def assign(patient, professional):
        return assign_care_relationship(
            actor=actor_context_from_user(admin),
            patient=patient,
            professional_dni=professional.dni,
        )

    return assign


@pytest.fixture
def playwright_instance() -> Playwright:
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture
def browser(playwright_instance: Playwright) -> Browser:
    chromium = playwright_instance.chromium
    if not Path(chromium.executable_path).is_file():
        pytest.skip(
            "Playwright Chromium is not installed; run "
            "`uv run playwright install chromium` to enable browser tests."
        )

    browser = chromium.launch(headless=True)
    yield browser
    browser.close()


@pytest.fixture
def browser_page(browser: Browser) -> Page:
    page = browser.new_page()
    yield page
    page.close()
