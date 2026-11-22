"""Exercise attendance across independent, signed-out Chromium sessions."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from playwright.sync_api import expect

from access_control.acceptance_personas import (
    CHECK_IN_OPERATOR,
    PAGINATION_SECOND_PAGE_DNI,
    RECEPTIONIST,
    SCHEDULE_MANAGER,
)


def run_attendance_journey(page, login, schedule_day, doctors):
    clinic = ZoneInfo("America/Argentina/Buenos_Aires")
    patient_dni = PAGINATION_SECOND_PAGE_DNI
    browser = page.context.browser
    manager = browser.new_page()
    try:
        login(manager, SCHEDULE_MANAGER)
        manager.get_by_role("link", name="Manage availability").click()
        selector = manager.get_by_label("Professional", exact=True)
        label = selector.locator("option").filter(has_text=doctors[0]).inner_text()
        selector.select_option(label=label)
        manager.get_by_role("button", name="Open schedule").click()
        # Exercise the real server clock. Use one complete future minute, including
        # when the next appointment falls on the other side of local midnight.
        start = datetime.now(clinic).replace(second=0, microsecond=0) + timedelta(
            minutes=2
        )
        end = start + timedelta(minutes=1)
        if end.date() != start.date():
            start, end = end, end + timedelta(minutes=1)
        manager.get_by_label("Exception date").fill(start.date().isoformat())
        manager.get_by_label("Mode", exact=True).select_option("replace")
        manager.get_by_label("Replacement opening time").fill(start.strftime("%H:%M"))
        manager.get_by_label("Replacement closing time").fill(end.strftime("%H:%M"))
        manager.get_by_label("Replacement duration").fill("1")
        manager.get_by_role("button", name="Save dated exception").click()
        expect(manager.get_by_role("status")).to_contain_text("Availability saved")
    finally:
        manager.close()

    def show_day(tab, day):
        tab.get_by_role("link", name="Daily agenda", exact=True).click()
        tab.get_by_label("Date", exact=True).fill(day.isoformat())
        tab.get_by_role("button", name="Show agenda").click()

    def reserve(day, doctor, interval, state):
        page.get_by_role("link", name="Find an opening").click()
        page.get_by_label("Date", exact=True).fill(day.isoformat())
        page.get_by_label("Specialty").select_option(label="General Medicine")
        page.get_by_role("button", name="Search openings").click()
        page.get_by_role("link", name=f"{doctor} · {day} {interval}").click()
        page.get_by_label("Patient DNI").fill(patient_dni)
        page.get_by_role("button", name="Find patient").click()
        page.get_by_label("Patient-supplied date of birth").fill("1990-01-01")
        page.get_by_label("Status").select_option(state)
        page.get_by_role("button", name="Reserve appointment").click()
        expect(page.get_by_role("status")).to_contain_text("Appointment reserved.")

    def row(tab, doctor, interval):
        return (
            tab.get_by_role("row")
            .filter(has_text=patient_dni)
            .filter(has_text=doctor)
            .filter(has_text=interval)
        )

    login(page, RECEPTIONIST)
    missed_time = f"{start:%H:%M}–{end:%H:%M}"
    reserve(start.date(), doctors[0], missed_time, "confirmed")
    expect(
        row(page, doctors[0], missed_time).get_by_role("button", name="Mark absent")
    ).to_be_disabled()

    visit_day = schedule_day + timedelta(weeks=3)
    early, late = "19:00–19:30", "19:30–20:00"
    reserve(visit_day, doctors[0], early, "pending")
    reserve(visit_day, doctors[0], late, "confirmed")
    reserve(visit_day, doctors[1], early, "confirmed")
    show_day(page, visit_day)
    desk = browser.new_page()
    try:
        login(desk, CHECK_IN_OPERATOR)
        show_day(desk, visit_day)
        for interval, old_state in [(early, "Pending"), (late, "Confirmed")]:
            visit = row(desk, doctors[0], interval)
            expect(visit).to_contain_text(old_state)
            visit.get_by_role("link", name="Check in patient").click()
            desk.get_by_label("Patient-supplied DNI").fill(patient_dni)
            dob = desk.get_by_label("Patient-supplied date of birth")
            if old_state == "Pending":
                dob.fill("1991-01-01")
                desk.get_by_role("button", name="Record arrival").click()
                expect(
                    desk.get_by_text(
                        "The DNI and date of birth must match the active patient on this appointment."
                    )
                ).to_be_visible()
                page.reload()
                expect(row(page, doctors[0], interval)).to_contain_text("Pending")
            dob.fill("1990-01-01")
            desk.get_by_role("button", name="Record arrival").click()
            expect(visit).to_contain_text("Attended")
            expect(visit).to_contain_text(CHECK_IN_OPERATOR)
            expect(visit.locator("time")).to_have_count(1)
        # This tab still displays the confirmed booking from before the second arrival.
        row(page, doctors[0], late).get_by_role(
            "button", name="Cancel appointment"
        ).click()
        expect(page.get_by_role("status")).to_contain_text("Current status is Attended")
        expect(row(page, doctors[0], late)).to_contain_text("Attended")
        show_day(page, visit_day)
        row(page, doctors[1], early).get_by_role(
            "button", name="Cancel appointment"
        ).click()
        expect(row(page, doctors[1], early)).to_contain_text("Canceled")
        show_day(desk, start.date())
        missed = row(desk, doctors[0], missed_time)
        absence_button = missed.get_by_role("button", name="Mark absent")
        expect(absence_button).to_be_enabled(timeout=185_000)
        absence_button.click()
        desk.reload()
        expect(missed).to_contain_text("Absent")
        expect(missed).to_contain_text(CHECK_IN_OPERATOR)
        expect(missed.locator("time")).to_have_count(1)
    finally:
        desk.close()
    show_day(page, visit_day)
    expect(row(page, doctors[0], early)).to_contain_text("Attended")
    expect(row(page, doctors[0], late)).to_contain_text("Attended")
    expect(row(page, doctors[1], early)).to_contain_text("Canceled")
