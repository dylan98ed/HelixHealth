import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date

import pytest
from django.contrib.auth.models import Group, User
from django.db import connections
from playwright.sync_api import expect

from access_control.acceptance_personas import (
    ACTIVE_PATIENT_DNI,
    DJANGO_ADMIN_USERNAME,
    INACTIVE_PATIENT_DNI,
    PAGED_ACTIVE_USERNAME_PREFIX,
    PAGED_INACTIVE_USERNAME_PREFIX,
    PAGINATION_SECOND_PAGE_DNI,
)
from access_control.actors import actor_context_from_user
from access_control.management.commands.verify_acceptance import (
    attendance_verified,
    chart_access_verified,
    reminder_outcomes_verified,
)
from access_control.roles import (
    ADMINISTRATIVE_GROUP,
    MEDICAL_PROFESSIONAL_GROUP,
    RECEPTION_GROUP,
)
from appointments.models import Appointment, WeeklyRule
from patients.models import Patient
from professionals.models import HospitalService, Specialty
from professionals.services import deactivate_professional, register_professional
from tests.appointment_journeys import (
    DOCTORS,
    RECEPTIONIST,
    SCHEDULE_MANAGER,
    scheduling_journeys,
)
from tests.reminder_mailbox import local_mailbox

PASSWORD = "Booking-fixture-password-2026!"


@pytest.fixture
def booking_prerequisites(transactional_db):
    # Transactional test flushes can remove reference rows seeded by migrations.
    for role in (ADMINISTRATIVE_GROUP, MEDICAL_PROFESSIONAL_GROUP, RECEPTION_GROUP):
        Group.objects.get_or_create(name=role)
    User.objects.create_superuser(username=DJANGO_ADMIN_USERNAME, password=PASSWORD)
    background_admin = User.objects.create(username="prerequisite-operator")
    background_admin.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))
    Specialty.objects.get_or_create(
        code="general-medicine", defaults={"name": "General Medicine"}
    )
    HospitalService.objects.get_or_create(
        code="inpatient-ward", defaults={"name": "Inpatient Ward"}
    )
    for index, username in enumerate(
        [
            f"{PAGED_ACTIVE_USERNAME_PREFIX}-00",
            f"{PAGED_ACTIVE_USERNAME_PREFIX}-01",
            f"{PAGED_INACTIVE_USERNAME_PREFIX}-00",
        ]
    ):
        user = User.objects.create_user(username=username, password=PASSWORD)
        profile = register_professional(
            actor=actor_context_from_user(background_admin),
            username=user.username,
            dni=f"3100000{index}",
            first_name=f"Paged 0{index}",
            last_name="Zpagination active",
            date_of_birth=date(1980, 1, 1),
            license_number=f"MN-2700{index}",
            specialty_code="general-medicine",
            hospital_service_code="inpatient-ward",
        )
        if username.startswith(PAGED_INACTIVE_USERNAME_PREFIX):
            deactivate_professional(
                actor=actor_context_from_user(background_admin),
                professional=profile,
                confirmed=True,
            )
    for dni, active in [(ACTIVE_PATIENT_DNI, True), (INACTIVE_PATIENT_DNI, False)]:
        Patient.all_objects.create(
            dni=dni,
            first_name="Acceptance",
            last_name="Patient",
            date_of_birth=date(1990, 1, 1),
            is_active=active,
        )
    Patient.objects.create(
        dni=PAGINATION_SECOND_PAGE_DNI,
        first_name="Patient 20",
        last_name="Zpagination",
        date_of_birth=date(1990, 1, 1),
    )
    for number in (15, 16, 17, 18, 19):
        dni = f"200000{number}"
        Patient.objects.create(
            dni=dni,
            first_name=f"Patient {number}",
            last_name="Zpagination",
            date_of_birth=date(1990, 1, 1),
            email="" if number == 17 else f"{dni}@acceptance.example.test",
        )
    assert not WeeklyRule.objects.exists() and not Appointment.objects.exists()


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_signed_out_availability_booking_and_agenda(
    booking_prerequisites, live_server, browser, tmp_path
):
    @contextmanager
    def worker():
        db = connections["default"].settings_dict
        with local_mailbox(tmp_path) as (port, inbox):
            env = {
                **os.environ,
                **{
                    f"DB_{key}": str(db[key])
                    for key in ("NAME", "HOST", "USER", "PASSWORD", "PORT")
                },
                "EMAIL_HOST": "127.0.0.1",
                "EMAIL_PORT": str(port),
                "EMAIL_USE_TLS": "false",
                "EMAIL_USE_SSL": "false",
                "EMAIL_HOST_USER": "",
                "EMAIL_HOST_PASSWORD": "",
                "REMINDER_POLL_SECONDS": "1",
            }
            process = subprocess.Popen(
                [sys.executable, "manage.py", "send_appointment_reminders", "--watch"],
                env=env,
            )
            try:
                yield inbox.messages
                assert process.poll() is None
            finally:
                process.terminate()
                process.wait(timeout=15)

    for _, journey in scheduling_journeys(live_server.url, PASSWORD, worker):
        context = browser.new_context()
        try:
            journey(context.new_page())
        finally:
            context.close()

    def verify():
        try:
            reception = User.objects.get(username=RECEPTIONIST)
            manager = User.objects.get(username=SCHEDULE_MANAGER)
            assert not reception.is_staff and not reception.is_superuser
            assert list(reception.groups.values_list("name", flat=True)) == [
                RECEPTION_GROUP
            ]
            assert reception.get_all_permissions() == set()
            assert not manager.is_staff and not manager.is_superuser
            assert manager.get_all_permissions() == {"appointments.manage_availability"}
            assert attendance_verified()
            assert reminder_outcomes_verified()
            booking = Appointment.objects.get(
                request__isnull=True, patient__dni=ACTIVE_PATIENT_DNI
            )
            assert booking.professional.dni == "31000001"
            assert (
                booking.state == "confirmed"
                and booking.patient.dni == ACTIVE_PATIENT_DNI
            )
            assert booking.history.get().operator == booking.created_by == reception
            linked = Appointment.objects.filter(
                patient__dni=ACTIVE_PATIENT_DNI, request__isnull=False
            )
            assert linked.count() == 2
            for row in linked.select_related("request"):
                assert row.state == row.request.status == "confirmed"
                assert list(
                    row.request.contactattempt_set.order_by("pk").values_list(
                        "channel", "outcome", "operator_id"
                    )
                ) == [
                    (row.request.channel, "unanswered", reception.pk),
                    (row.request.channel, "confirmed", reception.pk),
                ]
            assert WeeklyRule.objects.count() == 2
            assert chart_access_verified()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(verify).result()

    manager_page = browser.new_page()
    try:
        manager_page.goto(live_server.url)
        manager_page.get_by_role("link", name="Sign in").click()
        manager_page.get_by_label("Username").fill(SCHEDULE_MANAGER)
        manager_page.get_by_label("Password").fill(PASSWORD)
        manager_page.get_by_role("button", name="Sign in").click()
        manager_page.get_by_role("link", name="Manage availability").click()
        selector = manager_page.get_by_label("Professional", exact=True)
        label = selector.locator("option").filter(has_text=DOCTORS[1]).inner_text()
        selector.select_option(label=label)
        manager_page.get_by_role("button", name="Open schedule").click()
        manager_page.get_by_role("link", name="Edit hours").click()
        booked_day = manager_page.get_by_label("Effective from").input_value()
        manager_page.get_by_label("Exception date").fill(booked_day)
        manager_page.get_by_role("button", name="Save dated exception").click()
        affected = manager_page.locator("section").filter(
            has=manager_page.get_by_role(
                "heading", name="Upcoming appointments outside configured hours"
            )
        )
        expect(affected).to_contain_text(ACTIVE_PATIENT_DNI)
        expect(affected).to_contain_text("19:00–19:30")
        expect(affected).to_contain_text("Confirmed")
    finally:
        manager_page.close()

    # Reopen the saved daily agenda from a new reception session, move the
    # appointment across doctors, then release it and reuse its exact interval.
    page = browser.new_page()
    try:
        page.goto(live_server.url)
        page.get_by_role("link", name="Sign in").click()
        page.get_by_label("Username").fill(RECEPTIONIST)
        page.get_by_label("Password").fill(PASSWORD)
        page.get_by_role("button", name="Sign in").click()
        day_field = page.get_by_label("Date", exact=True)
        day = date.fromisoformat(booked_day)
        day_field.fill(day.isoformat())
        page.get_by_role("button", name="Show agenda").click()
        page.get_by_role("link", name="Reschedule").click()
        day_field.fill(day.isoformat())
        page.get_by_role("button", name="Search openings").click()
        expect(
            page.get_by_role("link", name=f"{DOCTORS[1]} · {day} 19:30–20:00")
        ).to_have_count(0)
        opening = f"{DOCTORS[0]} · {day} 19:30–20:00"
        page.get_by_role("link", name=opening).click()
        page.get_by_role("button", name="Move appointment").click()
        expect(page.get_by_role("status")).to_contain_text("Appointment moved")
        row = page.get_by_role("row").filter(has_text=ACTIVE_PATIENT_DNI)
        expect(row).to_contain_text(DOCTORS[0])
        expect(row).to_contain_text("19:30–20:00")
        row.get_by_role("button", name="Cancel appointment").click()
        expect(row).to_contain_text("Canceled")
        page.get_by_role("link", name="Find an opening").click()
        day_field.fill(day.isoformat())
        page.get_by_label("Specialty").select_option(label="General Medicine")
        page.get_by_role("button", name="Search openings").click()
        page.get_by_role("link", name=opening).click()
        page.get_by_label("Patient DNI").fill(ACTIVE_PATIENT_DNI)
        page.get_by_role("button", name="Find patient").click()
        page.get_by_label("Patient-supplied date of birth").fill("1990-01-01")
        page.get_by_label("Status").select_option(label="Pending")
        page.get_by_role("button", name="Reserve appointment").click()
        page.reload()
        expect(row).to_have_count(2)
        expect(row.filter(has_text="Canceled")).to_have_count(1)
        expect(row.filter(has_text="Pending")).to_have_count(1)
    finally:
        page.close()
