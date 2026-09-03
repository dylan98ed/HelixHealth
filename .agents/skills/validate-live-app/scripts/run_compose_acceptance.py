from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Browser, Page, expect, sync_playwright

repository_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(repository_root))
personas = importlib.import_module("access_control.acceptance_personas")

ACCEPTANCE_PASSWORD_ENV = personas.ACCEPTANCE_PASSWORD_ENV
ACTIVE_PATIENT_DNI = personas.ACTIVE_PATIENT_DNI
ADMINISTRATOR_USERNAME = personas.ADMINISTRATOR_USERNAME
ADMISSION_REASON = personas.ADMISSION_REASON
BROWSER_CREATED_USERNAME = personas.BROWSER_CREATED_USERNAME
DJANGO_ADMIN_USERNAME = personas.DJANGO_ADMIN_USERNAME
INACTIVE_PATIENT_DNI = personas.INACTIVE_PATIENT_DNI
MEDICAL_ACTIVE_USERNAME = personas.MEDICAL_ACTIVE_USERNAME
MEDICAL_INACTIVE_USERNAME = personas.MEDICAL_INACTIVE_USERNAME
MEDICAL_LEGACY_STAFF_USERNAME = personas.MEDICAL_LEGACY_STAFF_USERNAME
MEDICAL_UNPROVISIONED_USERNAME = personas.MEDICAL_UNPROVISIONED_USERNAME
REGISTERED_PATIENT_DNI = personas.REGISTERED_PATIENT_DNI

Journey = Callable[[Page], None]


def application_login(page: Page, base_url: str, username: str, password: str) -> None:
    page.goto(f"{base_url}/", wait_until="networkidle")
    page.get_by_role("link", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/login/")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()


def run_journey(
    browser: Browser,
    *,
    name: str,
    artifact_dir: Path,
    journey: Journey,
) -> dict[str, str]:
    context = browser.new_context()
    page = context.new_page()
    try:
        journey(page)
        return {"name": name, "status": "passed", "final_url": page.url}
    except Exception as error:
        screenshot = artifact_dir / f"{name}.png"
        page.screenshot(path=str(screenshot), full_page=True)
        raise RuntimeError(
            f"Compose browser journey '{name}' failed at {page.url}; "
            f"screenshot: {screenshot}"
        ) from error
    finally:
        context.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    artifact_dir = args.artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    password = os.environ.get(ACCEPTANCE_PASSWORD_ENV, "")
    if not password:
        raise RuntimeError(f"{ACCEPTANCE_PASSWORD_ENV} is required.")

    def unprovisioned_medical(page: Page) -> None:
        application_login(
            page,
            base_url,
            MEDICAL_UNPROVISIONED_USERNAME,
            password,
        )
        expect(page).to_have_url(f"{base_url}/clinical-records/")
        expect(page.get_by_role("heading", name="Clinical workspace")).to_be_visible()
        expect(page.get_by_text(ACTIVE_PATIENT_DNI, exact=True)).to_be_visible()
        expect(page.get_by_text(INACTIVE_PATIENT_DNI, exact=True)).to_have_count(0)

    def legacy_staff_medical(page: Page) -> None:
        page.goto(f"{base_url}/admin/login/", wait_until="networkidle")
        page.get_by_label("Username").fill(MEDICAL_LEGACY_STAFF_USERNAME)
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Log in").click()
        expect(page).to_have_url(f"{base_url}/clinical-records/")
        expect(page.get_by_role("heading", name="Clinical workspace")).to_be_visible()

    def inactive_medical(page: Page) -> None:
        application_login(page, base_url, MEDICAL_INACTIVE_USERNAME, password)
        expect(page).to_have_url(f"{base_url}/")
        expect(page.get_by_role("heading", name="HelixHealth")).to_be_visible()
        expect(page.get_by_role("link", name="Clinical workspace")).to_have_count(0)

    def record_admission(page: Page) -> None:
        application_login(page, base_url, MEDICAL_ACTIVE_USERNAME, password)
        expect(page).to_have_url(f"{base_url}/clinical-records/")
        patient_card = page.locator("article").filter(has_text="Acceptance Patient")
        expect(patient_card).to_be_visible()
        patient_card.get_by_role(
            "link",
            name="Record admission for Acceptance Patient",
        ).click()
        expect(page.get_by_role("heading", name="Patient admission")).to_be_visible()
        page.get_by_label("Consultation reason").fill(ADMISSION_REASON)
        page.get_by_label("Systolic blood pressure").fill("251")
        page.get_by_label("Heart rate").fill("72")
        page.get_by_label("Temperature").fill("36.7")
        page.get_by_role("button", name="Record admission").click()
        expect(
            page.locator('[data-field-error="systolic_blood_pressure"]')
        ).to_be_visible()
        expect(
            page.locator('[data-field-error="diastolic_blood_pressure"]')
        ).to_be_visible()
        page.get_by_label("Systolic blood pressure").fill("120")
        page.get_by_label("Diastolic blood pressure").fill("80")
        page.get_by_role("button", name="Record admission").click()
        expect(page.get_by_role("status")).to_contain_text("Admission recorded")
        expect(page.get_by_text(ADMISSION_REASON, exact=True)).to_be_visible()
        page.reload(wait_until="networkidle")
        history = page.get_by_role("region", name="Admission history")
        expect(history.get_by_text(ADMISSION_REASON, exact=True)).to_be_visible()
        expect(history.get_by_text(MEDICAL_ACTIVE_USERNAME, exact=True)).to_be_visible()

    def register_patient(page: Page) -> None:
        application_login(page, base_url, ADMINISTRATOR_USERNAME, password)
        expect(page).to_have_url(f"{base_url}/patients/search/")
        page.get_by_label("DNI").fill(REGISTERED_PATIENT_DNI)
        page.get_by_role("button", name="Search patient").click()
        expect(
            page.get_by_text(f"No patient matches DNI {REGISTERED_PATIENT_DNI}.")
        ).to_be_visible()
        page.get_by_role("link", name="Register a new patient").click()
        page.get_by_label("Dni").fill(REGISTERED_PATIENT_DNI)
        page.get_by_label("First name").fill("Compose")
        page.get_by_label("Last name").fill("Registered")
        page.get_by_label("Date of birth").fill("1990-01-01")
        page.get_by_label("Sex").fill("unspecified")
        page.get_by_label("Phone").fill("+54 11 5555-0199")
        page.get_by_label("Email").fill("compose.patient@example.test")
        page.get_by_label("Address").fill("Compose Test Street 123")
        page.get_by_label("Health insurer").fill("Compose Health")
        page.get_by_role("button", name="Register patient").click()
        expect(page.get_by_role("status")).to_contain_text("Patient registered")
        page.get_by_role("link", name="Open patient record").click()
        expect(page.get_by_role("heading", name="Compose Registered")).to_be_visible()
        expect(page.get_by_text(REGISTERED_PATIENT_DNI, exact=True)).to_be_visible()

    def django_admin_user_creation(page: Page) -> None:
        page.goto(f"{base_url}/admin/login/", wait_until="networkidle")
        page.get_by_label("Username").fill(DJANGO_ADMIN_USERNAME)
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Log in").click()
        expect(page.get_by_role("heading", name="Site administration")).to_be_visible()
        page.get_by_role("link", name="Users", exact=True).click()
        page.get_by_role("link", name="Add user").click()
        page.get_by_label("Username").fill(BROWSER_CREATED_USERNAME)
        page.locator("#id_password1").fill(password)
        page.locator("#id_password2").fill(password)
        page.get_by_role("button", name="Save", exact=True).click()
        expect(page).to_have_url(re.compile(r"/admin/auth/user/\d+/change/$"))
        expect(page.get_by_text(re.compile(r"was added successfully"))).to_be_visible()

        page.get_by_role("link", name="Home", exact=True).click()
        page.get_by_role("link", name="Admissions", exact=True).click()
        expect(page.get_by_role("link", name="Add admission")).to_have_count(0)
        page.get_by_role(
            "link",
            name=re.compile(ACTIVE_PATIENT_DNI),
        ).first.click()
        expect(page.get_by_role("button", name="Save", exact=True)).to_have_count(0)
        expect(page.get_by_role("link", name="Delete", exact=True)).to_have_count(0)

    journeys: list[tuple[str, Journey]] = [
        ("medical-unprovisioned-login", unprovisioned_medical),
        ("medical-legacy-admin-login", legacy_staff_medical),
        ("medical-inactive-denied", inactive_medical),
        ("medical-admission", record_admission),
        ("administrative-patient-registration", register_patient),
        ("django-admin-user-creation", django_admin_user_creation),
    ]

    results: list[dict[str, str]] = []
    summary = artifact_dir / "compose-browser-summary.json"
    summary.write_text("[]\n", encoding="utf-8")
    with sync_playwright() as playwright:
        executable = Path(playwright.chromium.executable_path)
        if not executable.is_file():
            raise RuntimeError(
                "Playwright Chromium is not installed; Compose validation is incomplete."
            )
        browser = playwright.chromium.launch(headless=True)
        try:
            for name, journey in journeys:
                results.append(
                    run_journey(
                        browser,
                        name=name,
                        artifact_dir=artifact_dir,
                        journey=journey,
                    )
                )
                summary.write_text(
                    json.dumps(results, indent=2),
                    encoding="utf-8",
                )
        finally:
            browser.close()

    print(f"{len(results)} Compose browser journeys passed.")
    for result in results:
        print(f"- {result['name']}: {result['final_url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
