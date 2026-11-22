from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from appointments import reminders
from appointments.availability import free_slots
from appointments.models import AppointmentState, ReminderDelivery
from appointments.services import (
    change_booking,
    confirm_request,
    create_request,
    record_attendance,
)
from appointments.test_booking import book
from appointments.test_booking import practice as practice
from patients.models import Patient
from tests.reminder_mailbox import LOST_REPLY_ADDRESS, local_mailbox

Status = ReminderDelivery.Status


@pytest.fixture
def mailbox(tmp_path, settings):
    with local_mailbox(tmp_path) as (port, inbox):
        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        settings.EMAIL_HOST, settings.EMAIL_PORT = "127.0.0.1", port
        settings.EMAIL_HOST_USER = settings.EMAIL_HOST_PASSWORD = ""
        settings.EMAIL_USE_SSL = settings.EMAIL_USE_TLS = False
        yield inbox


def freeze(monkeypatch, instant):
    monkeypatch.setattr(timezone, "now", lambda: instant)


def test_boundary_late_confirmation_and_repeated_command(
    practice, monkeypatch, mailbox
):
    _, operator, doctors, patient, day = practice
    patient.email = "first@example.test"
    patient.save()
    early, late = free_slots(day, [doctors[0]])[:2]
    first = book(operator, patient, early)
    request = create_request(
        user_id=operator.pk,
        dni=patient.dni,
        channel="phone",
        contact="5550101",
        preference="",
        token=uuid4(),
    )
    pending = book(operator, patient, late, confirmed=False, request_id=request.pk)
    freeze(monkeypatch, early.start - timedelta(hours=24, microseconds=1))
    call_command("send_appointment_reminders")
    assert mailbox.messages() == []
    freeze(monkeypatch, early.start - timedelta(hours=24))
    call_command("send_appointment_reminders")
    delivery = first.reminders.get()
    assert delivery.status == Status.SENT and delivery.sent_at == timezone.now()
    assert mailbox.messages() == [
        dict(
            to=patient.email,
            message_id=f"<{delivery.message_id}@reminders.helixhealth>",
            body=f"Your appointment with {doctors[0]} is on {day} at 19:00 (America/Argentina/Buenos_Aires).\r\n",
        )
    ]
    freeze(monkeypatch, late.start - timedelta(hours=1))
    call_command("send_appointment_reminders")
    assert len(mailbox.messages()) == 1
    confirm_request(
        user_id=operator.pk,
        request_id=request.pk,
        dni=patient.dni,
        birth_date=patient.date_of_birth,
        version=1,
        token=uuid4(),
    )
    for _ in range(2):
        call_command("send_appointment_reminders")
    assert pending.reminders.get().attempts == 1
    assert len(mailbox.messages()) == 2


@pytest.mark.parametrize("action", ["move", "cancel", "arrival"])
def test_schedule_changed_after_claim(practice, monkeypatch, mailbox, action):
    _, operator, doctors, patient, day = practice
    patient.email = "visit@example.test"
    patient.save()
    slot = free_slots(day, [doctors[0]])[0]
    destination = free_slots(day, [doctors[1]])[0]
    visit = book(operator, patient, slot)
    freeze(monkeypatch, slot.start - timedelta(hours=1))
    old = visit.reminders.get()
    assert reminders._claim(old.pk)
    values = dict(user_id=operator.pk, booking_id=visit.pk, version=1, token=uuid4())
    if action == "arrival":
        record_attendance(
            **values,
            state=AppointmentState.ATTENDED,
            dni=patient.dni,
            birth_date=patient.date_of_birth,
        )
    else:
        change_booking(**values, destination=destination if action == "move" else None)
    reminders._dispatch(old.pk, visit.pk, patient.pk)
    call_command("send_appointment_reminders")
    old.refresh_from_db()
    assert old.status == Status.OBSOLETE and old.sent_at is None
    if action == "move":
        (message,) = mailbox.messages()
        assert str(doctors[1]) in message["body"]
        assert visit.reminders.get(schedule_revision=2).status == Status.SENT
    else:
        assert mailbox.messages() == []


def test_missing_email_rejection_lost_reply_and_recovery(
    practice, monkeypatch, mailbox
):
    _, operator, doctors, patient, day = practice
    slots = free_slots(day, [doctors[0]])
    recipients = [
        "bad-address",
        "retry@example.test",
        LOST_REPLY_ADDRESS,
        "healthy@example.test",
    ]
    visits = []
    for index, address in enumerate(recipients):
        person = Patient.objects.create(
            dni=f"6000000{index}",
            first_name="Test",
            last_name="Patient",
            date_of_birth=patient.date_of_birth,
            email=address,
        )
        visits.append(book(operator, person, slots[index]))
    mailbox.refuse_once.add(recipients[1])
    freeze(monkeypatch, slots[0].start - timedelta(hours=1))
    call_command("send_appointment_reminders")
    assert [v.reminders.get().status for v in visits] == [
        Status.MISSING,
        Status.RETRY,
        Status.REVIEW,
        Status.SENT,
    ]
    Patient.objects.filter(pk=visits[0].patient_id).update(email="updated@example.test")
    for _ in range(2):
        call_command("send_appointment_reminders")
    assert [v.reminders.get().attempts for v in visits] == [1, 2, 1, 1]
    assert sorted(m["to"] for m in mailbox.messages()) == sorted(
        ["updated@example.test", *recipients[1:]]
    )
    assert all(
        v.reminders.get().status == Status.SENT
        for v in (visits[0], visits[1], visits[3])
    )


def test_lost_worker_and_past_or_absent_appointments(practice, monkeypatch, mailbox):
    _, operator, doctors, patient, day = practice
    patient.email = "patient@example.test"
    patient.save()
    past, absent, future = free_slots(day, [doctors[0]])[:3]
    past_visit, missed, later = [
        book(operator, patient, slot) for slot in (past, absent, future)
    ]
    freeze(monkeypatch, absent.start)
    record_attendance(
        user_id=operator.pk,
        booking_id=missed.pk,
        version=1,
        token=uuid4(),
        state=AppointmentState.ABSENT,
    )
    assert reminders._claim(later.reminders.get().pk)
    freeze(monkeypatch, absent.start + timedelta(minutes=6))
    call_command("send_appointment_reminders")
    assert past_visit.reminders.get().attempts == 0
    assert missed.reminders.get().status == Status.OBSOLETE
    assert later.reminders.get().status == Status.REVIEW
    assert mailbox.messages() == []


@pytest.mark.django_db(transaction=True)
def test_independent_workers_claim_once(practice, monkeypatch, mailbox):
    _, operator, doctors, patient, day = practice
    patient.email = "race@example.test"
    patient.save()
    slot = free_slots(day, [doctors[0]])[0]
    visit = book(operator, patient, slot)
    freeze(monkeypatch, slot.start - timedelta(hours=1))
    ready = Barrier(2, timeout=15)
    claim = reminders._claim

    def compete(delivery_id):
        ready.wait()
        return claim(delivery_id)

    monkeypatch.setattr(reminders, "_claim", compete)

    def worker():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                (pid,) = cursor.fetchone()
            call_command("send_appointment_reminders")
            return pid
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        workers = [pool.submit(worker) for _ in range(2)]
        assert len({worker.result() for worker in workers}) == 2
    assert len(mailbox.messages()) == visit.reminders.get().attempts == 1
