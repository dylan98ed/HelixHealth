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
def playwright_instance() -> Playwright:
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture
def browser(playwright_instance: Playwright) -> Browser:
    browser = playwright_instance.chromium.launch(headless=True)
    yield browser
    browser.close()


@pytest.fixture
def browser_page(browser: Browser) -> Page:
    page = browser.new_page()
    yield page
    page.close()
