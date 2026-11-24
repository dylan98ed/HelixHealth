"""Cold-start scheduling journeys shared by the isolated and Compose browsers."""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from playwright.sync_api import Page, expect

from access_control.acceptance_personas import (
    ACTIVE_PATIENT_DNI,
    CARE_COORDINATOR,
    CHECK_IN_OPERATOR,
    DJANGO_ADMIN_USERNAME,
    INACTIVE_PATIENT_DNI,
    RECEPTIONIST,
    SCHEDULE_MANAGER,
)
from tests.attendance_journey import run_attendance_journey
from tests.chart_journey import (
    UNREGISTERED_PHYSICIAN,
    assigned_chart_journey,
)
from tests.reminder_journey import compose_reminder_worker, run_reminder_journey

NO_ROLE = "booking-unassigned"
DOCTORS = ("Zpagination active, Paged 00", "Zpagination active, Paged 01")


def scheduling_journeys(base_url, password, reminder_worker=compose_reminder_worker):
    day = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date() + timedelta(
        days=7
    )
    protected = {}

    def login(page, username):
        page.goto(f"{base_url}/")
        page.get_by_role("link", name="Sign in").click()
        expect(page).to_have_url(f"{base_url}/login/")
        page.get_by_label("Username").fill(username)
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Sign in").click()

    def provision(page: Page):
        login(page, DJANGO_ADMIN_USERNAME)
        page.get_by_role("link", name="Account administration").click()
        page.get_by_role("link", name="Users", exact=True).click()
        for username, group in [
            (SCHEDULE_MANAGER, "Administrative"),
            (CARE_COORDINATOR, "Administrative"),
            (UNREGISTERED_PHYSICIAN, "Medical Professionals"),
            (RECEPTIONIST, "Reception"),
            (CHECK_IN_OPERATOR, "Reception"),
            (NO_ROLE, ""),
        ]:
            page.get_by_role("link", name="Add user").click()
            page.get_by_label("Username").fill(username)
            page.locator("#id_password1").fill(password)
            page.locator("#id_password2").fill(password)
            page.get_by_role("button", name="Save", exact=True).click()
            expect(page.get_by_role("heading", name="Change user")).to_be_visible()
            if group:
                page.locator("#id_groups_from").get_by_role(
                    "option", name=group, exact=True
                ).dblclick()
            if username == SCHEDULE_MANAGER:
                page.locator("#id_user_permissions_from").get_by_role(
                    "option", name=re.compile("Can manage availability$")
                ).dblclick()
            page.get_by_role("button", name="Save", exact=True).click()
            expect(page.get_by_role("link", name="Add user")).to_be_visible()

    def unassigned(page: Page):
        login(page, NO_ROLE)
        expect(page).to_have_url(f"{base_url}/")
        expect(
            page.get_by_text("No workspace role is assigned.", exact=False)
        ).to_be_visible()
        expect(page.get_by_role("link", name="Daily agenda")).to_have_count(0)
        expect(page.get_by_role("link", name="Manage availability")).to_have_count(0)

    def configure(page: Page):
        login(page, SCHEDULE_MANAGER)
        expect(page).to_have_url(f"{base_url}/patients/search/")
        page.get_by_label("Name or surname").fill("Acceptance Patient")
        page.get_by_role(
            "link", name="Open patient record for Acceptance Patient"
        ).click()
        protected["record"] = page.url
        protected["admissions"] = page.get_by_role(
            "link", name="Record admission"
        ).get_attribute("href")
        page.get_by_role("link", name="Manage availability").click()
        for name in DOCTORS:
            selector = page.get_by_label("Professional", exact=True)
            label = selector.locator("option").filter(has_text=name).inner_text()
            selector.select_option(label=label)
            page.get_by_role("button", name="Open schedule").click()
            expect(page.get_by_text("No weekly hours configured.")).to_be_visible()
            page.get_by_role("checkbox", name=day.strftime("%A")).check()
            page.get_by_label("Opening time", exact=True).fill("19:00")
            page.get_by_label("Closing time", exact=True).fill("20:00")
            page.get_by_label("Slot duration (minutes)", exact=True).fill("30")
            page.get_by_label("Effective from").fill(day.isoformat())
            page.get_by_role("button", name="Add weekly hours").click()
            expect(page.get_by_role("status")).to_contain_text("Availability saved")
        protected["hours"] = page.url
        page.get_by_role("link", name="Edit hours").click()
        page.get_by_label("Closing time", exact=True).fill("18:00")
        page.get_by_role("button", name="Update weekly hours").click()
        expect(
            page.get_by_text("Closing time must be after opening time.")
        ).to_be_visible()
        page.get_by_label("Closing time", exact=True).fill("20:00")
        page.get_by_role("button", name="Update weekly hours").click()
        expect(page.get_by_role("status")).to_contain_text("Availability saved")

    def configure_weekdays(page: Page):
        login(page, SCHEDULE_MANAGER)
        page.get_by_role("link", name="Manage availability").click()
        selector = page.get_by_label("Professional", exact=True)
        label = selector.get_by_role(
            "option", name=re.compile("Zpagination active, Paged 02")
        ).inner_text()
        selector.select_option(label=label)
        page.get_by_role("button", name="Open schedule").click()
        expect(page.get_by_text("No weekly hours configured.")).to_be_visible()
        page.get_by_role("checkbox", name="Sunday").check()
        page.get_by_role("button", name="Select weekdays").click()
        expect(page.get_by_role("checkbox", name="Sunday")).not_to_be_checked()
        page.get_by_label("Opening time", exact=True).fill("08:00")
        page.get_by_label("Closing time", exact=True).fill("16:00")
        page.get_by_label("Slot duration (minutes)", exact=True).fill("30")
        page.get_by_label("Effective from").fill(
            (day + timedelta(days=365)).isoformat()
        )
        page.get_by_role("button", name="Add weekly hours").click()
        rows = page.get_by_role("listitem").filter(
            has=page.get_by_role("link", name="Edit hours")
        )
        expect(rows).to_have_count(5)
        rows.filter(has_text="Friday").get_by_role("link", name="Edit hours").click()
        page.get_by_label("Opening time", exact=True).fill("07:00")
        page.get_by_label("Closing time", exact=True).fill("14:00")
        page.get_by_role("button", name="Update weekly hours").click()

        # Only Friday conflicts. The four earlier days must roll back together.
        page.get_by_role("button", name="Select weekdays").click()
        page.get_by_label("Opening time", exact=True).fill("07:00")
        page.get_by_label("Closing time", exact=True).fill("08:00")
        page.get_by_label("Slot duration (minutes)", exact=True).fill("30")
        page.get_by_role("button", name="Add weekly hours").click()
        expect(
            page.get_by_text("Friday: these hours overlap another effective rule.")
        ).to_be_visible()
        expect(page.get_by_role("checkbox", name="Monday")).to_be_checked()
        page.get_by_role("button", name="Open schedule").click()
        expect(rows).to_have_count(5)
        for weekday in ("Monday", "Tuesday", "Wednesday", "Thursday"):
            expect(rows.filter(has_text=weekday)).to_contain_text("08:00–16:00")
        expect(rows.filter(has_text="Friday")).to_contain_text("07:00–14:00")

    def search(page):
        page.get_by_role("link", name="Find an opening").click()
        page.get_by_label("Specialty", exact=True).select_option(
            label="General Medicine"
        )
        page.get_by_role("button", name="Search openings").click()

    def book(page: Page):
        login(page, RECEPTIONIST)
        expect(page).to_have_url(f"{base_url}/appointments/")
        expect(page.get_by_label("Date", exact=True)).to_have_value(
            (day - timedelta(days=7)).isoformat()
        )
        expect(page.get_by_text("No appointments for this day.")).to_be_visible()
        for label in ("Manage availability", "Patient search", "Clinical workspace"):
            expect(page.get_by_role("link", name=label)).to_have_count(0)
        for url in protected.values():
            response = page.goto(url if url.startswith(base_url) else base_url + url)
            assert response.status == 403
        page.goto(f"{base_url}/")
        page.get_by_role("link", name="Open daily agenda").click()
        search(page)
        chosen_label = f"{DOCTORS[1]} · {day} 19:00–19:30"
        expect(
            page.get_by_role("link", name=f"{DOCTORS[0]} · {day} 19:00–19:30")
        ).to_be_visible()
        page.get_by_role("link", name=chosen_label).click()
        page.get_by_label("Patient DNI").fill(INACTIVE_PATIENT_DNI)
        page.get_by_role("button", name="Find patient").click()
        expect(page.get_by_role("alert")).to_contain_text("No active patient")
        page.get_by_label("Patient DNI").fill("11.224.488")
        page.get_by_role("button", name="Find patient").click()
        expect(page.get_by_role("heading", name="Acceptance Patient")).to_be_visible()
        expect(page.get_by_text("1990-01-01")).to_have_count(0)
        page.get_by_label("Patient-supplied date of birth").fill("1991-01-01")
        page.get_by_role("button", name="Reserve appointment").click()
        expect(page.get_by_role("alert")).to_contain_text("do not match")
        stale = page.context.new_page()
        stale.goto(f"{base_url}/")
        stale.get_by_role("link", name="Open daily agenda").click()
        search(stale)
        stale.get_by_role("link", name=chosen_label).click()
        stale.get_by_label("Patient DNI").fill(ACTIVE_PATIENT_DNI)
        stale.get_by_role("button", name="Find patient").click()
        stale.get_by_label("Patient-supplied date of birth").fill("1990-01-01")
        page.get_by_label("Patient-supplied date of birth").fill("1990-01-01")
        page.get_by_role("button", name="Reserve appointment").click()
        expect(page.get_by_role("status")).to_contain_text("Appointment reserved.")
        stale.get_by_role("button", name="Reserve appointment").click()
        expect(stale.get_by_role("alert")).to_contain_text("no longer available")
        expect(stale.get_by_role("link", name=chosen_label)).to_have_count(0)
        expect(
            stale.get_by_role("link", name=f"{DOCTORS[0]} · {day} 19:00–19:30")
        ).to_be_visible()
        stale.close()
        agenda = page.url
        expect(page).to_have_url(re.compile(r"/appointments/\?day="))
        search(page)
        expect(page.get_by_role("link", name=chosen_label)).to_have_count(0)
        expect(
            page.get_by_role("link", name=f"{DOCTORS[0]} · {day} 19:00–19:30")
        ).to_be_visible()
        page.goto(agenda)
        page.reload()
        row = page.get_by_role("row").filter(has_text=ACTIVE_PATIENT_DNI)
        expect(row).to_have_count(1)
        for value in ("19:00–19:30", DOCTORS[1], "Confirmed"):
            expect(row).to_contain_text(value)

    def request_contact(page: Page, channel: str, weeks: int):
        login(page, RECEPTIONIST)
        expect(page).to_have_url(f"{base_url}/appointments/")
        page.get_by_role("link", name="Request inbox").click()
        page.get_by_role("link", name="New appointment request").click()
        preference = f"{channel} evening appointment"
        picker = page.get_by_role("combobox", name="Patient", exact=True)
        expect(
            picker.get_by_role("option", name=re.compile(INACTIVE_PATIENT_DNI))
        ).to_have_count(0)
        picker.select_option(
            label=picker.get_by_role(
                "option", name=re.compile(ACTIVE_PATIENT_DNI)
            ).inner_text()
        )
        page.get_by_label("Original channel").select_option(label=channel)
        page.get_by_label("Contact number").fill("+54 11 5555 0130")
        page.get_by_label("Appointment preference").fill(preference)
        page.get_by_role("button", name="Record request").click()
        expect(page.get_by_text("Pending", exact=True)).to_be_visible()
        page.get_by_role("button", name=f"Record no answer by {channel}").click()
        page.get_by_role("link", name="Request inbox").click()
        page.get_by_role("row").filter(has_text=preference).get_by_role("link").click()
        history = page.locator("section").filter(
            has=page.get_by_role("heading", name="Contact history")
        )
        expect(history.get_by_role("listitem")).to_contain_text(
            f"No answer · {channel} · {RECEPTIONIST}"
        )
        page.get_by_role("link", name="Choose an opening").click()
        requested_day = day + timedelta(weeks=weeks)
        opening = f"{DOCTORS[0]} · {requested_day} 19:00–19:30"

        def show_openings(tab):
            tab.get_by_label("Specialty").select_option(label="General Medicine")
            tab.get_by_role("button", name="Search openings").click()

        show_openings(page)
        expect(page.get_by_label("Professional", exact=True)).to_have_count(0)
        links = page.locator("section li a")
        labels = links.all_text_contents()
        starts = [label.split(" · ")[1].split("–")[0] for label in labels]
        assert starts == sorted(starts)
        assert all(any(doctor in label for label in labels) for doctor in DOCTORS)
        page.get_by_role("link", name="Later openings").click()
        assert links.first.inner_text().split(" · ")[1] >= starts[-1]
        page.go_back()
        page.get_by_role("link", name=opening).click()
        observer = page.context.browser.new_page()
        try:
            login(observer, RECEPTIONIST)
            observer.get_by_role("link", name="Find an opening").click()
            show_openings(observer)
            expect(observer.get_by_role("link", name=opening)).to_be_visible()
            patient_picker = page.get_by_role("combobox", name="Patient", exact=True)
            expect(patient_picker.locator("option:checked")).to_contain_text(
                ACTIVE_PATIENT_DNI
            )
            expect(patient_picker.get_by_role("option")).to_have_count(1)
            expect(page.get_by_label("Patient-supplied date of birth")).to_have_count(0)
            if channel == "WhatsApp":
                page.get_by_label("Status").select_option("confirmed")
            save = page.get_by_role("button", name="Save request reservation")
            if channel == "Phone":
                save.click()
                expect(page.get_by_text("Pending", exact=True)).to_be_visible()
                observer.reload()
                expect(observer.get_by_role("link", name=opening)).to_have_count(0)
                page.get_by_label("Patient-supplied DNI").fill(ACTIVE_PATIENT_DNI)
                page.get_by_label("Patient-supplied date of birth").fill("1980-01-01")
                save = page.get_by_role("button", name="Record confirmation by Phone")
                save.click()
                expect(
                    page.get_by_text(
                        "The DNI and date of birth do not match the active request patient."
                    )
                ).to_be_visible()
                page.get_by_label("Patient-supplied date of birth").fill("1990-01-01")
            with page.expect_request(lambda req: req.method == "POST") as sent:
                save.click()
            expect(page.get_by_text("Confirmed", exact=True)).to_be_visible()
            # Replay the exact browser submission, including its original operation token.
            submission = sent.value
            replay = page.evaluate(
                """async ({url, body, contentType}) => {
                    const response = await fetch(url, {method: "POST", body,
                        headers: {"Content-Type": contentType}, credentials: "same-origin"});
                    return [response.status, response.url];
                }""",
                {
                    "url": submission.url,
                    "body": submission.post_data,
                    "contentType": submission.headers["content-type"],
                },
            )
            assert replay == [200, page.url]
            page.reload()
            attempts = history.get_by_role("listitem")
            expect(attempts).to_have_count(2)
            expect(attempts.nth(1)).to_contain_text(
                f"Confirmed · {channel} · {RECEPTIONIST}"
            )
            for attempt in attempts.all():
                assert attempt.locator("time").get_attribute("datetime")
            observer.reload()
            expect(observer.get_by_role("link", name=opening)).to_have_count(0)
            page.get_by_role("link", name="View on daily agenda").click()
            row = page.get_by_role("row").filter(has_text=ACTIVE_PATIENT_DNI)
            expect(row).to_have_count(1)
            expect(row).to_contain_text("Confirmed")
            row.get_by_role("link", name="Open request").click()
            expect(page).to_have_url(re.compile(r"/appointments/requests/\d+/$"))
            expect(history.get_by_role("listitem")).to_have_count(2)
        finally:
            observer.close()

    return [
        ("scheduling-account-provisioning", provision),
        ("unassigned-scheduling-denial", unassigned),
        ("administrative-availability", configure),
        ("weekday-availability-and-independent-edit", configure_weekdays),
        ("reception-booking-and-agenda", book),
        (
            "phone-request-and-later-confirmation",
            lambda page: request_contact(page, "Phone", 1),
        ),
        (
            "whatsapp-request-and-confirmation",
            lambda page: request_contact(page, "WhatsApp", 2),
        ),
        (
            "reception-arrivals-absence-and-cancellation",
            lambda page: run_attendance_journey(page, login, day, DOCTORS),
        ),
        (
            "reception-reminder-delivery-and-review",
            lambda page: run_reminder_journey(page, login, DOCTORS[1], reminder_worker),
        ),
        (
            "assigned-patient-chart-and-revocation",
            lambda page: assigned_chart_journey(page, login, day, DOCTORS[0]),
        ),
    ]
