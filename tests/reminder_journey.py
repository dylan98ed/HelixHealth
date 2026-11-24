import json
import os
import subprocess
from contextlib import contextmanager
from datetime import datetime, timedelta
from time import monotonic
from zoneinfo import ZoneInfo

from playwright.sync_api import expect

from access_control.acceptance_personas import (
    CHECK_IN_OPERATOR,
    RECEPTIONIST,
    SCHEDULE_MANAGER,
)


@contextmanager
def compose_reminder_worker():
    project = os.environ["COMPOSE_PROJECT_NAME"]
    if not project.startswith("helixhealth-validation-"):
        raise RuntimeError(
            "The reminder mailbox requires a disposable validation project."
        )
    compose = [
        "docker",
        "compose",
        "-p",
        project,
        "-f",
        "compose.yaml",
        "-f",
        "compose.production.yaml",
        "-f",
        "tests/compose.reminder-mailbox.yaml",
    ]
    try:
        subprocess.run(
            [
                *compose,
                "up",
                "-d",
                "--wait",
                "--build",
                "reminder-mailbox",
                "scheduler",
            ],
            check=True,
        )

        def messages():
            result = subprocess.run(
                [
                    *compose,
                    "exec",
                    "-T",
                    "reminder-mailbox",
                    "python",
                    "-m",
                    "tests.reminder_mailbox",
                    "--read",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return json.loads(result.stdout)

        yield messages
    finally:
        subprocess.run(
            [*compose, "rm", "--stop", "--force", "scheduler", "reminder-mailbox"],
            check=True,
        )


def run_reminder_journey(page, login, doctor, worker):
    zone = ZoneInfo("America/Argentina/Buenos_Aires")
    start = (datetime.now(zone) + timedelta(hours=2)).replace(
        minute=0, second=0, microsecond=0
    )
    day = start.date().isoformat()
    manager = page.context.browser.new_page()
    try:
        login(manager, SCHEDULE_MANAGER)
        manager.get_by_role("link", name="Manage availability").click()
        select = manager.get_by_label("Professional", exact=True)
        select.select_option(
            label=select.locator("option").filter(has_text=doctor).inner_text()
        )
        manager.get_by_role("button", name="Open schedule").click()
        manager.get_by_label("Exception date").fill(day)
        manager.get_by_label("Mode", exact=True).select_option("replace")
        manager.get_by_label("Replacement opening time").fill(start.strftime("%H:%M"))
        manager.get_by_label("Replacement closing time").fill(f"{start:%H}:30")
        manager.get_by_label("Replacement duration").fill("10")
        manager.get_by_role("button", name="Save dated exception").click()
        expect(manager.get_by_role("status")).to_contain_text("Availability saved")
    finally:
        manager.close()

    login(page, RECEPTIONIST)

    def choose_slot(tab, offset):
        begin = start + timedelta(minutes=10 * offset)
        end = begin + timedelta(minutes=10)
        tab.get_by_label("Specialty").select_option(label="General Medicine")
        tab.get_by_role("button", name="Search openings").click()
        tab.get_by_role(
            "link", name=f"{doctor} · {day} {begin:%H:%M}–{end:%H:%M}"
        ).click()

    def reserve(offset, dni):
        page.get_by_role("link", name="Find an opening").click()
        choose_slot(page, offset)
        page.get_by_label("Patient DNI").fill(dni)
        page.get_by_role("button", name="Find patient").click()
        page.get_by_label("Patient-supplied date of birth").fill("1990-01-01")
        page.get_by_label("Status").select_option("confirmed")
        page.get_by_role("button", name="Reserve appointment").click()
        expect(page.get_by_role("status")).to_contain_text("Appointment reserved")

    def await_outcome(dni, outcome):
        row = page.get_by_role("row").filter(has_text=dni)
        deadline = monotonic() + 45
        while monotonic() < deadline:
            page.reload()
            if outcome in row.inner_text():
                break
            page.wait_for_timeout(400)
        expect(row).to_contain_text(outcome)

    dni = "20000018"
    page.get_by_role("link", name="Request inbox").click()
    page.get_by_role("link", name="New appointment request").click()
    picker = page.get_by_label("Patient", exact=True)
    picker.select_option(
        label=picker.locator("option").filter(has_text=dni).inner_text()
    )
    page.get_by_label("Original channel").select_option(label="Phone")
    page.get_by_label("Contact number").fill("+54 11 5555 0118")
    page.get_by_label("Appointment preference").fill("Next available appointment")
    page.get_by_role("button", name="Record request").click()
    page.get_by_role("button", name="Record no answer by Phone").click()
    page.get_by_role("link", name="Choose an opening").click()
    choose_slot(page, 1)

    def verify_identity(tab):
        tab.get_by_label("Patient-supplied DNI").fill(dni)
        tab.get_by_label("Patient-supplied date of birth").fill("1990-01-01")

    expect(
        page.get_by_label("Patient", exact=True).locator("option:checked")
    ).to_contain_text(dni)
    page.get_by_label("Status").select_option("pending")
    page.get_by_role("button", name="Save request reservation").click()
    expect(page.get_by_role("heading", name="Confirm reservation")).to_be_visible()
    verify_identity(page)
    page.get_by_role("button", name="Record confirmation by Phone").click()
    expect(
        page.get_by_text(f"Confirmed · Phone · {RECEPTIONIST}", exact=False)
    ).to_be_visible()
    page.get_by_role("link", name="View on daily agenda").click()
    visit = page.get_by_role("row").filter(has_text=dni)
    interval = f"{start:%H}:10–{start:%H}:20"
    expect(visit).to_contain_text(interval)
    expect(visit).to_contain_text("Confirmed")

    # A second operator saves the destination after the move form has opened.
    moving = page.context.browser.new_page()
    try:
        login(moving, CHECK_IN_OPERATOR)
        moving.get_by_label("Date", exact=True).fill(day)
        moving.get_by_role("button", name="Show agenda").click()
        moving.get_by_role("row").filter(has_text=dni).get_by_role(
            "link", name="Reschedule"
        ).click()
        choose_slot(moving, 0)
        reserve(0, "20000017")
        moving.get_by_role("button", name="Move appointment").click()
        expect(moving.get_by_role("alert")).to_contain_text("no longer available")
        page.reload()
        expect(visit).to_contain_text(interval)
        expect(visit).to_contain_text("Confirmed")
    finally:
        moving.close()
    with worker() as read_mailbox:
        await_outcome("20000018", "Email reminder: Sent")
        expect(page.get_by_role("row").filter(has_text="20000017")).to_contain_text(
            "Email reminder: Valid email address needed"
        )
        # The same running scheduler must pick up a booking made after its first pass.
        reserve(2, "20000019")
        await_outcome("20000019", "Email reminder: Delivery uncertain")
        received = sorted(read_mailbox(), key=lambda item: item["to"])
        assert [item["to"] for item in received] == [
            f"200000{i}@acceptance.example.test" for i in (18, 19)
        ]
        for minute, message in zip((10, 20), received, strict=True):
            assert doctor in message["body"]
            assert day in message["body"] and f"{start:%H}:{minute}" in message["body"]
            assert zone.key in message["body"] and message["message_id"]
        expect(page.get_by_role("row").filter(has_text="20000019")).to_contain_text(
            received[1]["message_id"]
        )

    desk = page.context.browser.new_page()
    try:
        login(desk, CHECK_IN_OPERATOR)
        desk.get_by_label("Date", exact=True).fill(day)
        desk.get_by_role("button", name="Show agenda").click()
        desk.get_by_role("row").filter(has_text=dni).get_by_role(
            "link", name="Check in patient"
        ).click()
        verify_identity(desk)
        desk.get_by_role("button", name="Record arrival").click()
        expect(desk.get_by_role("row").filter(has_text=dni)).to_contain_text("Attended")
    finally:
        desk.close()
    page.reload()
    expect(visit).to_have_count(1)
    for value in (interval, doctor, "Attended", CHECK_IN_OPERATOR):
        expect(visit).to_contain_text(value)
