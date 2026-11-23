"""Follow a clinician through an assignment, a canceled visit, and revocation."""

from contextlib import ExitStack
from datetime import timedelta
from urllib.parse import urljoin

from playwright.sync_api import expect

from access_control.acceptance_personas import (
    CARE_COORDINATOR,
    CHART_REASON,
    DJANGO_ADMIN_USERNAME,
    PAGED_ACTIVE_USERNAME_PREFIX,
    PAGED_INACTIVE_USERNAME_PREFIX,
    RECEPTIONIST,
)
from tests.chart_documentation_journey import document_care
from tests.chart_review_journey import grant_audit, review_chart

UNREGISTERED_PHYSICIAN = "chart-unregistered-medical"


def assigned_chart_journey(page, login, schedule_day, doctor):
    dni = "20000016"
    populated = "Open chart for Patient 16 Zpagination"
    empty = "Open chart for Patient 15 Zpagination"
    day = (schedule_day + timedelta(weeks=6)).isoformat()

    def patient_record(admin, identifier):
        admin.get_by_role("link", name="Patient search", exact=True).click()
        admin.get_by_label("DNI", exact=True).fill(identifier)
        admin.get_by_role("button", name="Search patient").click()
        admin.get_by_role("link", name="Open patient record", exact=True).click()

    def open_intake(tab):
        tab.get_by_role("link", name="Clinical workspace", exact=True).click()
        tab.get_by_label("DNI", exact=True).fill(dni)
        tab.get_by_role("button", name="Find patient").click()
        tab.get_by_role(
            "link", name="Record admission for Patient 16 Zpagination"
        ).click()
        expect(tab.get_by_role("button", name="Record admission")).to_be_visible()

    def expect_intake_only(tab):
        expect(tab.get_by_role("heading", name="Admission history")).to_have_count(0)
        expect(tab.get_by_text(CHART_REASON, exact=True)).to_have_count(0)
        expect(
            tab.get_by_role("heading", name="Medication requests received")
        ).to_have_count(0)
        expect(
            tab.get_by_role("link", name="Interoperability", exact=True)
        ).to_have_count(0)
        expect(tab.get_by_role("link", name="Prescriptions", exact=True)).to_have_count(
            0
        )

    def assign(admin, patient_dni, professional_dni):
        patient_record(admin, patient_dni)
        admin.get_by_role("link", name="Care team").click()
        admin.get_by_label("Professional DNI").fill(professional_dni)
        admin.get_by_role("button", name="Search professional").click()
        admin.get_by_role("button", name="Assign professional").click()

    def book(reception, interval):
        reception.get_by_role("link", name="Find an opening").click()
        reception.get_by_label("Date", exact=True).fill(day)
        reception.get_by_label("Specialty").select_option(label="General Medicine")
        reception.get_by_role("button", name="Search openings").click()
        reception.get_by_role("link", name=f"{doctor} · {day} {interval}").click()
        reception.get_by_label("Patient DNI").fill(dni)
        reception.get_by_role("button", name="Find patient").click()
        reception.get_by_label("Patient-supplied date of birth").fill("1990-01-01")
        reception.get_by_label("Status").select_option("confirmed")
        reception.get_by_role("button", name="Reserve appointment").click()
        row = (
            reception.get_by_role("row").filter(has_text=dni).filter(has_text=interval)
        )
        expect(row).to_contain_text("Confirmed")
        return row

    with ExitStack() as sessions:

        def signed_in(username):
            tab = page.context.browser.new_page()
            sessions.callback(tab.close)
            login(tab, username)
            return tab

        admin = signed_in(CARE_COORDINATOR)
        patient_record(admin, dni)
        admin.get_by_role("link", name="Record admission", exact=True).click()
        for label, value in [
            ("Consultation reason", CHART_REASON),
            ("Systolic blood pressure", "118"),
            ("Diastolic blood pressure", "76"),
            ("Heart rate", "68"),
            ("Temperature", "36.6"),
        ]:
            admin.get_by_label(label).fill(value)
        admin.get_by_role("button", name="Record admission").click()
        expect(admin.get_by_role("heading", name=CHART_REASON)).to_be_visible()
        assign(admin, dni, "31000001")
        assign(admin, "20000015", "31000000")

        colleague = signed_in(f"{PAGED_ACTIVE_USERNAME_PREFIX}-01")
        colleague.get_by_role("link", name="Assigned patient charts").click()
        colleague.get_by_role("link", name=populated).click()
        chart_url = colleague.url
        colleague.get_by_role("link", name=CHART_REASON).click()
        detail_url = colleague.url
        for username in (
            UNREGISTERED_PHYSICIAN,
            f"{PAGED_INACTIVE_USERNAME_PREFIX}-00",
        ):
            ineligible = signed_in(username)
            expect(
                ineligible.get_by_role("link", name="Clinical workspace")
            ).to_have_count(0)
            assert ineligible.goto(detail_url).status == 403

        login(page, f"{PAGED_ACTIVE_USERNAME_PREFIX}-00")
        expect(page.get_by_role("heading", name="Clinical workspace")).to_be_visible()
        open_intake(page)
        expect_intake_only(page)
        page.get_by_role("link", name="Clinical workspace", exact=True).click()
        page.get_by_role("link", name="Assigned patient charts").click()
        directory = page.url
        page.get_by_role("link", name=empty).click()
        expect(
            page.get_by_text("No clinical records have been recorded for this patient.")
        ).to_be_visible()
        page.get_by_role("link", name="Assigned patient charts").click()
        expect(page.get_by_role("link", name=populated)).to_have_count(0)
        reception = signed_in(RECEPTIONIST)
        booked = book(reception, "19:00–19:30")
        assert page.goto(chart_url).status == 403
        booked.get_by_role("link", name="Check in patient").click()
        reception.get_by_label("Patient-supplied DNI").fill(dni)
        reception.get_by_label("Patient-supplied date of birth").fill("1990-01-01")
        reception.get_by_role("button", name="Record arrival").click()
        expect(booked).to_contain_text("Attended")
        assert page.goto(detail_url).status == 403
        assert reception.goto(chart_url).status == 403
        reception.go_back()

        assign(admin, dni, "31000000")
        page.goto(directory)
        page.get_by_label("Name or surname").fill("Patient 16")
        page.get_by_role("link", name=populated).click()
        expect(page.get_by_text("Patient 16 Zpagination", exact=True)).to_be_visible()
        expect(page.get_by_text(f"DNI {dni}", exact=False)).to_contain_text(
            "Clinical record"
        )
        page.get_by_role("link", name=CHART_REASON).click()
        expect(page.get_by_text("118/76 mmHg")).to_be_visible()
        expect(page.get_by_text(CARE_COORDINATOR, exact=True)).to_be_visible()
        canceled = book(reception, "19:30–20:00")
        canceled.get_by_role("button", name="Cancel appointment").click()
        expect(canceled).to_contain_text("Canceled")
        page.reload()
        expect(page.get_by_text(CHART_REASON, exact=True)).to_be_visible()
        document_care(page, colleague)
        colleague.get_by_role("link", name="Edit family history").click()
        expect(colleague.get_by_role("heading", name="Prior revisions")).to_have_count(
            0
        )
        accounts = signed_in(DJANGO_ADMIN_USERNAME)
        grant_audit(accounts, f"{PAGED_ACTIVE_USERNAME_PREFIX}-01")
        colleague.reload()
        expect(colleague.get_by_role("heading", name="Prior revisions")).to_be_visible()
        previous = colleague.locator("article").filter(
            has_text="Family history reported at intake."
        )
        expect(previous).to_contain_text("Mother")
        expect(previous).to_contain_text("Zpagination active, Paged 00")
        reviewer = review_chart(signed_in, accounts, colleague, reception, populated)
        intake = signed_in(f"{PAGED_ACTIVE_USERNAME_PREFIX}-00")
        open_intake(intake)
        expect(intake.get_by_text(CHART_REASON, exact=True)).to_be_visible()
        expect(
            intake.get_by_role("heading", name="Medication requests received")
        ).to_be_visible()
        history_links = [
            intake.get_by_role("link", name=label, exact=True).get_attribute("href")
            for label in ("Prescriptions", "Interoperability")
        ]
        admin.get_by_role(
            "link", name="Revoke assignment for Paged 00 Zpagination active"
        ).click()
        admin.get_by_label("I confirm this assignment should be revoked.").check()
        admin.get_by_role("button", name="Revoke assignment").click()
        with page.expect_response(
            lambda response: response.request.method == "POST"
        ) as denied:
            page.get_by_role("button", name="Add progress note").click()
        assert denied.value.status == 403
        intake.reload()
        expect_intake_only(intake)
        for href in history_links:
            assert intake.goto(urljoin(chart_url, href)).status == 403
        assert reviewer.reload().status == 403
        assert page.goto(detail_url).status == 403
        assert page.goto(chart_url).status == 403
        page.goto(directory)
        expect(page.get_by_role("link", name=empty)).to_be_visible()
        expect(page.get_by_role("link", name=populated)).to_have_count(0)
