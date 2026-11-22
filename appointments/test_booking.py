from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, time, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.urls import reverse
from django.utils import timezone

from access_control.roles import (
    ADMINISTRATIVE_GROUP,
    MEDICAL_PROFESSIONAL_GROUP,
    RECEPTION_GROUP,
)
from appointments.availability import (
    affected_bookings,
    clinic_today,
    clinic_zone,
    eligible_professionals,
    free_slots,
    save_window,
)
from appointments.models import (
    Appointment,
    AppointmentHistory,
    AppointmentState,
    BookingRequest,
    ScheduleException,
    WeeklyRule,
)
from appointments.services import (
    BookingConflict,
    change_booking,
    confirm_request,
    create_request,
    record_attendance,
    record_unanswered,
    reserve,
)
from clinical_records.models import Admission, CareRelationship
from patients.models import Patient
from professionals.models import HospitalService, Professional, Specialty


@pytest.fixture
def practice(db):
    # Serialized transaction tests can flush post-migrate permissions; restore
    # the app's declared permissions using Django's provisioning hook.
    create_permissions(apps.get_app_config("appointments"), verbosity=0)

    def account(name, group):
        user = User.objects.create_user(username=name)
        user.groups.add(Group.objects.get_or_create(name=group)[0])
        return user

    operator = account("operator", RECEPTION_GROUP)
    manager = account("manager", ADMINISTRATIVE_GROUP)
    manager.user_permissions.add(Permission.objects.get(codename="manage_availability"))
    specialty = Specialty.objects.create(name="Booking specialty", code="booking")
    service = HospitalService.objects.create(name="Booking service", code="booking")
    doctors = [
        Professional.objects.create(
            user=account(f"doctor-{i}", MEDICAL_PROFESSIONAL_GROUP),
            first_name="Doctor",
            last_name=str(i),
            dni=f"7700000{i}",
            date_of_birth=date(1980, 1, 1),
            registration_number=f"BOOK-{i}",
            specialty=specialty,
            hospital_service=service,
            registration_completed_at=timezone.now(),
        )
        for i in range(2)
    ]
    patient = Patient.objects.create(
        dni="12003456",
        first_name="Ana",
        last_name="Ruiz",
        date_of_birth=date(1990, 1, 1),
    )
    day = clinic_today() + timedelta(days=7)
    for doctor in doctors:
        save_window(
            manager.pk,
            WeeklyRule(
                professional=doctor,
                weekday=day.weekday(),
                opens=time(19),
                closes=time(23),
                minutes=30,
                effective_from=day,
            ),
        )
    return manager, operator, doctors, patient, day


def book(operator, patient, slot, **kwargs):
    return reserve(
        user_id=operator.pk,
        dni=patient.dni,
        birth_date=patient.date_of_birth,
        token=kwargs.pop("token", uuid4()),
        confirmed=kwargs.pop("confirmed", True),
        slot=slot,
        **kwargs,
    )


@pytest.mark.django_db(transaction=True)
def test_two_postgres_connections_race_for_the_same_opening(practice):
    _, operator, doctors, patient, day = practice
    other = User.objects.create(username="second-operator")
    other.groups.add(Group.objects.get(name=RECEPTION_GROUP))
    slot = free_slots(day, [doctors[1]])[0]
    ready = Barrier(2, timeout=15)

    def compete(user):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend = cursor.fetchone()[0]
            ready.wait()
            try:
                book(user, patient, slot)
                return backend, "saved"
            except BookingConflict:
                return backend, "conflict"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(compete, [operator, other]))
    assert len({pid for pid, _ in results}) == 2
    assert sorted(result for _, result in results) == ["conflict", "saved"]
    assert Appointment.objects.count() == AppointmentHistory.objects.count() == 1
    assert slot not in free_slots(day, [doctors[1]])
    assert book(operator, patient, free_slots(day, [doctors[0]])[0]).start == slot.start


@pytest.mark.django_db(transaction=True)
def test_database_excludes_concurrent_partial_overlaps(practice):
    _, operator, doctors, patient, day = practice
    slot = free_slots(day, doctors)[0]
    ready = Barrier(2, timeout=15)

    def write(offset):
        try:
            with transaction.atomic():
                # The first insert exists uncommitted when the competing
                # transaction reaches the barrier. PostgreSQL arbitrates the overlap.
                if offset:
                    ready.wait()
                Appointment.objects.create(
                    patient=patient,
                    professional_id=slot.professional_id,
                    created_by=operator,
                    state="pending",
                    start=slot.start + offset,
                    end=slot.end + offset,
                )
                if not offset:
                    ready.wait()
            return "saved"
        except IntegrityError as error:
            assert (
                error.__cause__.diag.constraint_name
                == "appointment_no_occupied_overlap"
            )
            return "excluded"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, (timedelta(), timedelta(minutes=15)))) == [
            "excluded",
            "saved",
        ]
    assert Appointment.objects.count() == 1


def test_intervals_requests_retries_and_atomic_moves(practice):
    _, operator, doctors, patient, day = practice
    a, b, c = free_slots(day, [doctors[0]])[:3]
    request = BookingRequest.objects.create(
        patient=patient, channel="phone", contact="1234567", created_by=operator
    )
    token = uuid4()
    booking = book(
        operator, patient, a, token=token, confirmed=False, request_id=request.pk
    )
    assert (
        book(operator, patient, a, token=token, confirmed=False, request_id=request.pk)
        == booking
    )
    with pytest.raises(BookingConflict):
        book(operator, patient, b, request_id=request.pk)
    adjacent = book(operator, patient, b)
    with pytest.raises(IntegrityError), transaction.atomic():
        Appointment.objects.filter(pk=adjacent.pk).update(request=request)
    with pytest.raises(IntegrityError), transaction.atomic():
        Appointment.objects.filter(pk=adjacent.pk).update(end=b.start)
    args = dict(user_id=operator.pk, booking_id=booking.pk, version=1)
    with pytest.raises(BookingConflict):
        change_booking(**args, destination=b, token=uuid4())
    booking.refresh_from_db()
    assert booking.start == a.start and booking.version == booking.history.count() == 1
    change_booking(**args, destination=c, token=uuid4())
    with pytest.raises(BookingConflict):
        change_booking(**args, destination=None, token=uuid4())
    assert a in free_slots(day, doctors) and c not in free_slots(day, doctors)
    token = uuid4()
    for _ in range(2):
        change_booking(**{**args, "version": 2}, destination=None, token=token)
    assert c in free_slots(day, doctors)
    assert list(
        booking.history.order_by("version").values_list("operation", flat=True)
    ) == ["reserve", "move", "cancel"]
    moved = booking.history.get(operation="move")
    assert (moved.old_start, moved.new_start, moved.old_state, moved.new_state) == (
        a.start,
        c.start,
        "pending",
        "pending",
    )
    assert moved.operator == operator and moved.recorded_at


def test_availability_dates_exceptions_and_retained_bookings(practice, monkeypatch):
    manager, operator, doctors, patient, day = practice
    doctor = doctors[0]
    base = WeeklyRule.objects.get(professional=doctor)
    slots = free_slots(day, [doctor])
    assert slots[-1].end.astimezone(UTC).date() == day + timedelta(days=1)
    booking = book(operator, patient, slots[-1])
    assert free_slots(day - timedelta(days=7), [doctor]) == []
    assert len(free_slots(day + timedelta(days=7), [doctor])) == 8
    adjacent = WeeklyRule(
        professional=doctor,
        weekday=day.weekday(),
        opens=time(18),
        closes=time(19),
        minutes=30,
        effective_from=day,
        effective_until=day,
    )
    save_window(manager.pk, adjacent)
    assert len(free_slots(day, [doctor])) == 9
    for opens, closes, minutes in [
        (time(18, 30), time(20), 30),
        (time(19), time(18), 30),
        (time(18), time(19), 0),
    ]:
        adjacent.opens, adjacent.closes, adjacent.minutes = opens, closes, minutes
        with pytest.raises(ValidationError):
            save_window(manager.pk, adjacent)
    adjacent.refresh_from_db()
    assert (
        adjacent.opens == time(18)
        and adjacent.closes == time(19)
        and adjacent.minutes == 30
    )
    base.closes = time(21)
    save_window(manager.pk, base)
    assert affected_bookings(doctor.pk) == [booking]
    assert free_slots(day, [doctor])[-1].end.time() == time(21)
    closure = ScheduleException(professional=doctor, day=day)
    with pytest.raises(PermissionDenied):
        save_window(operator.pk, closure)
    save_window(manager.pk, closure)
    assert free_slots(day, [doctor]) == []
    save_window(
        manager.pk,
        ScheduleException(
            professional=doctor, day=day, opens=time(9), closes=time(10, 10), minutes=30
        ),
    )
    assert [s.start.time() for s in free_slots(day, [doctor])] == [time(9), time(9, 30)]
    monkeypatch.setattr(
        timezone, "now", lambda: datetime.combine(day, time(9), clinic_zone())
    )
    assert [s.start.time() for s in free_slots(day, [doctor])] == [time(9, 30)]
    monkeypatch.setattr(timezone, "now", lambda: datetime.combine(day, time(1), UTC))
    assert clinic_today() == day - timedelta(days=1)
    booking.refresh_from_db()
    assert booking.start == slots[-1].start and booking.state == "confirmed"


def test_identity_eligibility_and_permission_rechecks(practice, client):
    manager, operator, doctors, patient, day = practice
    client.force_login(operator)
    hours = reverse("appointments:availability", query={"professional": doctors[0].pk})
    response = client.post(
        hours, {"kind": "exception", "exception-day": day, "exception-mode": "closed"}
    )
    assert response.status_code == 403 and not ScheduleException.objects.exists()
    slot = free_slots(day, doctors)[0]
    for dob in [None, date(1970, 2, 3)]:
        with pytest.raises(ValidationError):
            reserve(
                user_id=operator.pk,
                slot=slot,
                dni=patient.dni,
                birth_date=dob,
                confirmed=True,
                token=uuid4(),
            )
    Patient.objects.filter(pk=patient.pk).update(is_active=False)
    with pytest.raises(ValidationError):
        book(operator, patient, slot)
    Patient.all_objects.filter(pk=patient.pk).update(is_active=True)
    doctors[0].user.groups.clear()
    assert doctors[0] not in eligible_professionals()
    with pytest.raises(BookingConflict):
        book(operator, patient, slot)
    operator.groups.clear()
    with pytest.raises(PermissionDenied):
        book(operator, patient, slot)
    manager.user_permissions.clear()
    client.force_login(manager)
    assert client.get(reverse("appointments:availability")).status_code == 403
    assert AppointmentHistory.objects.count() == Appointment.objects.count() == 0


def test_request_replays_stale_confirmation_and_slot_release(practice, client):
    manager, operator, doctors, patient, day = practice
    args = dict(
        user_id=operator.pk,
        dni=patient.dni,
        channel="phone",
        contact="555-0130",
        preference="Evening",
        token=uuid4(),
    )
    with pytest.raises(PermissionDenied):
        create_request(**{**args, "user_id": manager.pk})
    intake = create_request(**args)
    assert create_request(**args).pk == intake.pk
    with pytest.raises(BookingConflict):
        create_request(**{**args, "channel": "whatsapp"})
    client.force_login(manager)
    url = reverse("appointments:request-detail", args=[intake.pk])
    assert (
        client.get(url).status_code
        == client.post(url, {"action": "unanswered"}).status_code
        == 403
    )
    assert not Appointment.objects.exists()
    contact = dict(user_id=operator.pk, request_id=intake.pk, token=uuid4())
    for _ in range(2):
        record_unanswered(**contact)
    first, later = free_slots(day, [doctors[0]])[:2]
    booking = book(operator, patient, first, request_id=intake.pk, confirmed=False)
    change_booking(
        user_id=operator.pk,
        booking_id=booking.pk,
        version=1,
        token=uuid4(),
        destination=later,
    )
    confirmation = dict(
        user_id=operator.pk,
        request_id=intake.pk,
        dni=patient.dni,
        birth_date=patient.date_of_birth,
        token=uuid4(),
        version=1,
    )
    with pytest.raises(BookingConflict):
        confirm_request(**confirmation)
    confirmation["version"] = 2
    Patient.objects.filter(pk=patient.pk).update(is_active=False)
    with pytest.raises(ValidationError):
        confirm_request(**confirmation)
    Patient.all_objects.filter(pk=patient.pk).update(is_active=True)
    # A contact token collision occurs after the appointment write. Both writes must roll back.
    with pytest.raises(BookingConflict):
        confirm_request(**{**confirmation, "token": contact["token"]})
    booking.refresh_from_db()
    assert (
        booking.state == "pending"
        and booking.version == 2
        and booking.history.count() == 2
    )
    for _ in range(2):
        assert confirm_request(**confirmation).pk == booking.pk
    assert list(
        intake.contactattempt_set.order_by("pk").values_list("outcome", flat=True)
    ) == ["unanswered", "confirmed"]
    with pytest.raises(BookingConflict):
        record_unanswered(**{**contact, "token": uuid4()})
    change_booking(
        user_id=operator.pk,
        booking_id=booking.pk,
        version=3,
        token=uuid4(),
        destination=None,
    )
    intake.refresh_from_db()
    assert intake.status == "canceled" and later in free_slots(day, [doctors[0]])
    assert Appointment.objects.filter(request=intake).count() == 1


def test_arrival_requires_active_identity_and_reception_and_is_idempotent(
    practice, client
):
    manager, operator, doctors, patient, day = practice
    opening = free_slots(day, [doctors[0]])[0]
    Admission.objects.create(
        patient=patient,
        professional=doctors[1],
        consultation_reason="Prior visit",
        systolic_blood_pressure=120,
        diastolic_blood_pressure=80,
        heart_rate=72,
        temperature="36.5",
    )
    CareRelationship.objects.create(
        patient=patient, professional=doctors[1], assigned_by=manager
    )
    admissions = list(patient.admissions.values())
    assignments = list(patient.care_relationships.values())
    intake = create_request(
        user_id=operator.pk,
        dni=patient.dni,
        channel="phone",
        contact="555-0100",
        preference="Evening",
        token=uuid4(),
    )
    visit = book(operator, patient, opening, confirmed=False, request_id=intake.pk)
    arrival = dict(
        user_id=operator.pk,
        booking_id=visit.pk,
        version=visit.version,
        token=uuid4(),
        state=AppointmentState.ATTENDED,
        dni=patient.dni,
        birth_date=patient.date_of_birth,
    )
    with pytest.raises(PermissionDenied):
        record_attendance(**{**arrival, "user_id": manager.pk})
    client.force_login(manager)
    url = reverse("appointments:arrival", args=[visit.pk])
    assert client.get(url).status_code == client.post(url).status_code == 403
    assert (
        client.post(reverse("appointments:absence", args=[visit.pk])).status_code == 403
    )
    with pytest.raises(ValidationError):
        record_attendance(**{**arrival, "dni": "70000000"})
    Patient.objects.filter(pk=patient.pk).update(is_active=False)
    with pytest.raises(ValidationError):
        record_attendance(**arrival)
    visit.refresh_from_db()
    assert visit.state == "pending" and visit.history.count() == 1
    Patient.all_objects.filter(pk=patient.pk).update(is_active=True)
    for _ in range(2):
        assert record_attendance(**arrival).pk == visit.pk
    visit.refresh_from_db()
    assert visit.state == "attended" and visit.version == visit.history.count() == 2
    intake.refresh_from_db()
    assert intake.status == "closed" and not intake.contactattempt_set.exists()
    assert list(patient.admissions.values()) == admissions
    assert list(patient.care_relationships.values()) == assignments
    assert opening not in free_slots(day, [doctors[0]])
    with pytest.raises(BookingConflict):
        change_booking(
            user_id=operator.pk,
            booking_id=visit.pk,
            version=2,
            token=uuid4(),
            destination=None,
        )


def test_absence_rejected_before_start_and_allowed_at_start(
    practice, client, monkeypatch
):
    _, operator, doctors, patient, day = practice
    opening = free_slots(day, [doctors[0]])[0]
    visit = book(operator, patient, opening)
    client.force_login(operator)
    url = reverse("appointments:absence", args=[visit.pk])
    data = {"version": visit.version, "token": uuid4()}
    monkeypatch.setattr(
        timezone, "now", lambda: opening.start - timedelta(microseconds=1)
    )
    response = client.post(url, data, follow=True)
    assert b"Absence can be recorded once the appointment starts." in response.content
    visit.refresh_from_db()
    assert visit.state == "confirmed" and visit.version == visit.history.count() == 1
    monkeypatch.setattr(timezone, "now", lambda: opening.start)
    for _ in range(2):
        assert client.post(url, data).status_code == 302
    visit.refresh_from_db()
    event = visit.history.get(operation="absence")
    assert visit.state == "absent" and visit.version == visit.history.count() == 2
    assert (event.old_state, event.new_state, event.recorded_at, event.operator) == (
        "confirmed",
        "absent",
        opening.start,
        operator,
    )


def test_daily_agenda_all_states_order_and_filters(practice, client, monkeypatch):
    _, operator, doctors, patient, day = practice
    slots = free_slots(day, [doctors[0]])
    first = book(operator, patient, slots[0])
    change_booking(
        user_id=operator.pk,
        booking_id=first.pk,
        version=1,
        token=uuid4(),
        destination=None,
    )
    book(operator, patient, slots[0])
    book(operator, patient, free_slots(day, [doctors[1]])[0])
    book(operator, patient, slots[1], confirmed=False)
    for index, outcome in [
        (2, AppointmentState.ATTENDED),
        (3, AppointmentState.ABSENT),
    ]:
        booking = book(operator, patient, slots[index])
        with monkeypatch.context() as clock:
            clock.setattr(timezone, "now", lambda instant=booking.start: instant)
            record_attendance(
                user_id=operator.pk,
                booking_id=booking.pk,
                version=1,
                token=uuid4(),
                state=outcome,
                dni=patient.dni,
                birth_date=patient.date_of_birth,
            )
    client.force_login(operator)
    url = reverse("appointments:agenda")
    response = client.get(url, {"day": day, "professional": doctors[0].pk})
    rows = [booking for booking, _ in response.context["bookings"]]
    assert [r.state for r in rows] == [
        "canceled",
        "confirmed",
        "pending",
        "attended",
        "absent",
    ]
    for state in AppointmentState.labels:
        assert state in response.content.decode()
    assert all(r.professional_id == doctors[0].pk for r in rows)
    assert (
        b"No appointments for this day"
        in client.get(url, {"day": day + timedelta(days=1)}).content
    )
