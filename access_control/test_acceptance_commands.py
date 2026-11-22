from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone

from access_control.acceptance_personas import (
    ACCEPTANCE_PASSWORD_ENV,
    ACTIVE_PATIENT_DNI,
    ADMINISTRATIVE_ADMISSION_REASON,
    ADMINISTRATIVE_UPDATED_PHONE,
    ADMINISTRATOR_USERNAME,
    ADMISSION_REASON,
    BROWSER_CREATED_USERNAME,
    CARE_COORDINATOR,
    CATALOG_MEDICATION_CODE,
    CATALOG_MEDICATION_SYSTEM,
    CATALOG_MEDICATION_VERSION,
    CATALOG_SPECIALTY_CODE,
    CATALOG_TERMINOLOGY_CODE,
    CHART_REASON,
    CHECK_IN_OPERATOR,
    COMPLETED_ACTIVE_PROFESSIONAL_DNI,
    COMPLETED_INACTIVE_PROFESSIONAL_DNI,
    DJANGO_ADMIN_USERNAME,
    EXTERNAL_IMPORT_SOURCE_SYSTEM,
    INACTIVE_PATIENT_DNI,
    LEGACY_COMPLETE_ACTIVE_DNI,
    LEGACY_COMPLETE_ACTIVE_LICENSE,
    LEGACY_COMPLETE_ACTIVE_REGISTRATION_NUMBER,
    LEGACY_COMPLETE_ACTIVE_USERNAME,
    LEGACY_COMPLETE_INACTIVE_DNI,
    LEGACY_COMPLETE_INACTIVE_LICENSE,
    LEGACY_COMPLETE_INACTIVE_REGISTRATION_NUMBER,
    LEGACY_COMPLETE_INACTIVE_USERNAME,
    MEDICAL_ACTIVE_USERNAME,
    MEDICAL_INACTIVE_USERNAME,
    MEDICAL_LEGACY_STAFF_DNI,
    MEDICAL_LEGACY_STAFF_LICENSE,
    MEDICAL_LEGACY_STAFF_USERNAME,
    MEDICAL_UNPROVISIONED_DNI,
    MEDICAL_UNPROVISIONED_LICENSE,
    MEDICAL_UNPROVISIONED_USERNAME,
    PAGED_ACTIVE_USERNAME_PREFIX,
    PAGED_INACTIVE_USERNAME_PREFIX,
    PAGED_INCOMPLETE_USERNAME_PREFIX,
    PAGINATION_SECOND_PAGE_DNI,
    REACTIVATION_CONFLICT_LICENSE,
    REACTIVATION_CONFLICT_USERNAME,
    RECEPTIONIST,
    REGISTERED_PATIENT_DNI,
    REGISTERED_PROFESSIONAL_DNI,
)
from access_control.actors import actor_context_from_user
from access_control.roles import (
    ADMINISTRATIVE_GROUP,
    MEDICAL_PROFESSIONAL_GROUP,
    RECEPTION_GROUP,
)
from appointments.availability import clinic_today, free_slots
from appointments.models import AppointmentState, WeeklyRule
from appointments.services import (
    change_booking,
    confirm_request,
    create_request,
    record_attendance,
    record_unanswered,
    reserve,
)
from catalogs.models import MedicationEntry, TerminologyEntry
from catalogs.services import create_catalog_entry, create_specialty, delete_specialty
from clinical_records.care_services import (
    assign_care_relationship,
    revoke_care_relationship,
)
from clinical_records.documentation import (
    add_progress_note,
    save_consultation,
    save_history,
)
from clinical_records.models import Admission
from clinical_records.services import create_admission
from interoperability.json_services import import_json_bundle
from interoperability.models import ExternalClinicalRecord, ImportBatch
from interoperability.services import import_external_bundle
from patients.models import Patient
from prescriptions.models import Prescription
from prescriptions.services import issue_prescription
from professionals.models import Professional
from professionals.services import (
    ProfessionalConflictError,
    reactivate_professional,
    register_professional,
    update_professional,
)
from tests.chart_review_journey import EXCHANGE_SOURCE, chart_exchange_file

ACCEPTANCE_PASSWORD = "Acceptance-test-password-2026!"


@pytest.mark.django_db
def test_seed_acceptance_creates_deterministic_personas(monkeypatch):
    monkeypatch.setenv(ACCEPTANCE_PASSWORD_ENV, ACCEPTANCE_PASSWORD)

    call_command("seed_acceptance")
    call_command("seed_acceptance")
    assert not MedicationEntry.objects.exists()
    assert not TerminologyEntry.objects.exists()
    assert not Prescription.objects.exists()
    assert not ImportBatch.objects.exists()
    assert not ExternalClinicalRecord.objects.exists()
    assert not Admission.objects.filter(
        patient__dni=ACTIVE_PATIENT_DNI, consultation_reason=ADMISSION_REASON
    ).exists()

    user_model = get_user_model()
    django_admin = user_model.objects.get(username=DJANGO_ADMIN_USERNAME)
    assert django_admin.is_staff
    assert django_admin.is_superuser
    assert django_admin.check_password(ACCEPTANCE_PASSWORD)

    administrator = user_model.objects.get(username=ADMINISTRATOR_USERNAME)
    assert set(administrator.groups.values_list("name", flat=True)) == {
        ADMINISTRATIVE_GROUP
    }

    for username in (
        MEDICAL_UNPROVISIONED_USERNAME,
        MEDICAL_LEGACY_STAFF_USERNAME,
        MEDICAL_ACTIVE_USERNAME,
        MEDICAL_INACTIVE_USERNAME,
    ):
        user = user_model.objects.get(username=username)
        assert set(user.groups.values_list("name", flat=True)) == {
            MEDICAL_PROFESSIONAL_GROUP
        }
        assert user.check_password(ACCEPTANCE_PASSWORD)

    assert not Professional.objects.filter(
        user__username=MEDICAL_UNPROVISIONED_USERNAME
    ).exists()
    assert not Professional.objects.filter(
        user__username=MEDICAL_LEGACY_STAFF_USERNAME
    ).exists()
    assert Professional.objects.get(user__username=MEDICAL_ACTIVE_USERNAME).is_active
    assert not Professional.objects.get(
        user__username=MEDICAL_INACTIVE_USERNAME
    ).is_active
    for username, dni, registration_number, active in (
        (
            LEGACY_COMPLETE_ACTIVE_USERNAME,
            LEGACY_COMPLETE_ACTIVE_DNI,
            LEGACY_COMPLETE_ACTIVE_REGISTRATION_NUMBER,
            True,
        ),
        (
            LEGACY_COMPLETE_INACTIVE_USERNAME,
            LEGACY_COMPLETE_INACTIVE_DNI,
            LEGACY_COMPLETE_INACTIVE_REGISTRATION_NUMBER,
            False,
        ),
    ):
        profile = Professional.objects.get(user__username=username)
        assert profile.is_registration_complete
        assert profile.license_number is None
        assert (profile.dni, profile.registration_number, profile.is_active) == (
            dni,
            registration_number,
            active,
        )
        assert profile.admissions.count() == 1
    assert Patient.objects.get(dni=ACTIVE_PATIENT_DNI).is_active
    assert not Patient.all_objects.get(dni=INACTIVE_PATIENT_DNI).is_active
    assert (
        Professional.objects.filter(
            user__username__startswith=PAGED_ACTIVE_USERNAME_PREFIX,
            registration_completed_at__isnull=False,
            license_number__startswith="SYN-ACTIVE-",
            is_active=True,
        ).count()
        == 21
    )
    assert (
        Professional.objects.filter(
            user__username__startswith=PAGED_INACTIVE_USERNAME_PREFIX,
            registration_completed_at__isnull=False,
            license_number__startswith="SYN-INACTIVE-",
            is_active=False,
        ).count()
        == 21
    )
    assert (
        Professional.objects.filter(
            user__username__startswith=PAGED_INCOMPLETE_USERNAME_PREFIX,
            registration_completed_at__isnull=True,
        ).count()
        == 21
    )


@override_settings(ENVIRONMENT="production")
def test_seed_acceptance_refuses_non_test_or_development_environment(monkeypatch):
    monkeypatch.setenv(ACCEPTANCE_PASSWORD_ENV, ACCEPTANCE_PASSWORD)

    with pytest.raises(CommandError, match="only in development or test"):
        call_command("seed_acceptance")


@pytest.mark.django_db
def test_verify_acceptance_checks_persisted_browser_outcomes(monkeypatch):
    monkeypatch.setenv(ACCEPTANCE_PASSWORD_ENV, ACCEPTANCE_PASSWORD)
    call_command("seed_acceptance")
    user_model = get_user_model()

    Patient.objects.create(
        dni=REGISTERED_PATIENT_DNI,
        clinical_record_number="HC-ACCEPTANCE-REGISTERED",
        first_name="Compose",
        last_name="Registered",
        date_of_birth="1990-01-01",
        sex="unspecified",
        phone="+54 11 5555-0199",
        email="compose.patient@example.test",
        address="Compose Test Street 123",
        health_insurer="Compose Health",
    )
    user_model.objects.create_user(username=BROWSER_CREATED_USERNAME)
    Admission.objects.create(
        patient=Patient.objects.get(dni=ACTIVE_PATIENT_DNI),
        professional=Professional.objects.get(user__username=MEDICAL_ACTIVE_USERNAME),
        consultation_reason=ADMISSION_REASON,
        systolic_blood_pressure=120,
        diastolic_blood_pressure=80,
        heart_rate=72,
        temperature=Decimal("36.7"),
    )
    Admission.objects.create(
        patient=Patient.objects.get(dni=ACTIVE_PATIENT_DNI),
        recorded_by=user_model.objects.get(username=ADMINISTRATOR_USERNAME),
        consultation_reason=ADMINISTRATIVE_ADMISSION_REASON,
        systolic_blood_pressure=120,
        diastolic_blood_pressure=80,
        heart_rate=72,
        temperature=Decimal("36.7"),
    )
    managed_patient = Patient.all_objects.get(dni=ACTIVE_PATIENT_DNI)
    care_actor = actor_context_from_user(
        user_model.objects.get(username=ADMINISTRATOR_USERNAME)
    )
    receptionist = user_model.objects.create_user(username=RECEPTIONIST)
    receptionist.groups.add(Group.objects.get(name=RECEPTION_GROUP))
    booking_day = clinic_today() + timedelta(days=7)
    for offset in range(2):
        doctor = Professional.objects.get(
            user__username=f"{PAGED_ACTIVE_USERNAME_PREFIX}-{offset:02d}"
        )
        WeeklyRule.objects.create(
            professional=doctor,
            weekday=booking_day.weekday(),
            opens=time(19),
            closes=time(20),
            minutes=30,
            effective_from=booking_day,
        )
    reserve(
        user_id=receptionist.pk,
        slot=free_slots(booking_day, [doctor])[0],
        dni=managed_patient.dni,
        birth_date=managed_patient.date_of_birth,
        confirmed=True,
        token=uuid4(),
    )
    for weeks, channel in enumerate(("phone", "whatsapp"), start=1):
        intake = create_request(
            user_id=receptionist.pk,
            dni=managed_patient.dni,
            channel=channel,
            contact="555-0130",
            preference="Evening",
            token=uuid4(),
        )
        record_unanswered(user_id=receptionist.pk, request_id=intake.pk, token=uuid4())
        linked = reserve(
            user_id=receptionist.pk,
            request_id=intake.pk,
            slot=free_slots(booking_day + timedelta(weeks=weeks), [doctor])[0],
            dni=managed_patient.dni,
            birth_date=managed_patient.date_of_birth,
            confirmed=channel == "whatsapp",
            token=uuid4(),
        )
        if channel == "phone":
            confirm_request(
                user_id=receptionist.pk,
                request_id=intake.pk,
                dni=managed_patient.dni,
                birth_date=managed_patient.date_of_birth,
                version=linked.version,
                token=uuid4(),
            )
    check_in = user_model.objects.create_user(username=CHECK_IN_OPERATOR)
    check_in.groups.add(Group.objects.get(name=RECEPTION_GROUP))
    visitor = Patient.objects.get(dni=PAGINATION_SECOND_PAGE_DNI)
    for weeks, (confirmed, state) in enumerate(
        [
            (False, AppointmentState.ATTENDED),
            (True, AppointmentState.ATTENDED),
            (True, AppointmentState.ABSENT),
            (True, AppointmentState.CANCELED),
        ],
        start=4,
    ):
        slot = free_slots(booking_day + timedelta(weeks=weeks), [doctor])[0]
        visit = reserve(
            user_id=receptionist.pk,
            slot=slot,
            dni=visitor.dni,
            birth_date=visitor.date_of_birth,
            confirmed=confirmed,
            token=uuid4(),
        )
        if state == AppointmentState.CANCELED:
            change_booking(
                user_id=receptionist.pk,
                booking_id=visit.pk,
                version=1,
                token=uuid4(),
                destination=None,
            )
        else:
            with monkeypatch.context() as clock:
                clock.setattr(timezone, "now", lambda instant=slot.start: instant)
                record_attendance(
                    user_id=check_in.pk,
                    booking_id=visit.pk,
                    version=1,
                    token=uuid4(),
                    state=state,
                    dni=visitor.dni,
                    birth_date=visitor.date_of_birth,
                )
    for weeks, (dni, outcome) in enumerate(
        [("20000017", "missing"), ("20000018", "sent"), ("20000019", "review")], start=9
    ):
        patient = Patient.objects.get(dni=dni)
        request_id = None
        if outcome == "sent":
            intake = create_request(
                user_id=receptionist.pk,
                dni=dni,
                channel="phone",
                contact="555-0118",
                preference="Next available appointment",
                token=uuid4(),
            )
            request_id = intake.pk
            record_unanswered(
                user_id=receptionist.pk, request_id=request_id, token=uuid4()
            )
        visit = reserve(
            user_id=receptionist.pk,
            slot=free_slots(booking_day + timedelta(weeks=weeks), [doctor])[0],
            dni=dni,
            birth_date=patient.date_of_birth,
            request_id=request_id,
            confirmed=request_id is None,
            token=uuid4(),
        )
        if request_id is not None:
            confirm_request(
                user_id=receptionist.pk,
                request_id=request_id,
                dni=dni,
                birth_date=patient.date_of_birth,
                version=visit.version,
                token=uuid4(),
            )
            visit.refresh_from_db()
        visit.reminders.update(
            status=outcome,
            attempts=int(outcome != "missing"),
            attempted_at=timezone.now() if outcome != "missing" else None,
            sent_at=timezone.now() if outcome == "sent" else None,
        )
        if outcome == "sent":
            record_attendance(
                user_id=check_in.pk,
                booking_id=visit.pk,
                version=visit.version,
                token=uuid4(),
                state=AppointmentState.ATTENDED,
                dni=dni,
                birth_date=patient.date_of_birth,
            )
    coordinator = user_model.objects.create_user(username=CARE_COORDINATOR)
    coordinator.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))
    chart_actor = actor_context_from_user(coordinator)
    chart_patient = Patient.objects.get(dni="20000016")
    create_admission(
        patient=chart_patient,
        actor=chart_actor,
        consultation_reason=CHART_REASON,
        systolic_blood_pressure=118,
        diastolic_blood_pressure=76,
        heart_rate=68,
        temperature=Decimal("36.6"),
    )
    assign_care_relationship(
        actor=chart_actor,
        patient=Patient.objects.get(dni="20000015"),
        professional_dni="31000000",
    )
    assign_care_relationship(
        actor=chart_actor, patient=chart_patient, professional_dni="31000001"
    )
    assignment, _ = assign_care_relationship(
        actor=chart_actor, patient=chart_patient, professional_dni="31000000"
    )
    chart_doctor = assignment.professional
    primary = dict(
        actor=actor_context_from_user(chart_doctor.user), patient_pk=chart_patient.pk
    )
    colleague = dict(
        actor=actor_context_from_user(Professional.objects.get(dni="31000001").user),
        patient_pk=chart_patient.pk,
    )
    import_json_bundle(
        actor=primary["actor"],
        source_system=EXCHANGE_SOURCE,
        request_key=uuid4(),
        raw_json=chart_exchange_file(),
    )
    consultation = save_consultation(
        **primary,
        reason="Follow-up after arrival",
        initial_evolution="Reviewed symptoms at the visit.",
        visited_at=datetime(2026, 1, 15, 12, 45, tzinfo=UTC),
        operation_key=uuid4(),
    )
    add_progress_note(
        **colleague,
        consultation_pk=consultation.pk,
        text="Follow-up completed by the second physician.",
        operation_key=uuid4(),
    )
    save_history(
        **primary,
        category="personal",
        relationship="",
        description="Previous outpatient follow-up.",
        expected_version=0,
        operation_key=uuid4(),
    )
    family = save_history(
        **primary,
        category="family",
        relationship="Mother",
        description="Family history reported at intake.",
        expected_version=0,
        operation_key=uuid4(),
    )
    save_history(
        **colleague,
        entry_pk=family.pk,
        category="family",
        relationship="Sister",
        description="Family history clarified at follow-up.",
        expected_version=1,
        operation_key=uuid4(),
    )
    for slot, attended in zip(
        free_slots(booking_day + timedelta(weeks=6), [chart_doctor]),
        [True, False],
        strict=True,
    ):
        visit = reserve(
            user_id=receptionist.pk,
            slot=slot,
            dni=chart_patient.dni,
            birth_date=chart_patient.date_of_birth,
            confirmed=True,
            token=uuid4(),
        )
        action = dict(
            user_id=receptionist.pk, booking_id=visit.pk, version=1, token=uuid4()
        )
        if attended:
            record_attendance(
                **action,
                state=AppointmentState.ATTENDED,
                dni=chart_patient.dni,
                birth_date=chart_patient.date_of_birth,
            )
        else:
            change_booking(**action, destination=None)
    revoke_care_relationship(
        actor=chart_actor,
        patient=chart_patient,
        relationship=assignment,
        confirmed=True,
    )
    assignment, _ = assign_care_relationship(
        actor=care_actor,
        patient=managed_patient,
        professional_dni=LEGACY_COMPLETE_ACTIVE_DNI,
    )
    revoke_care_relationship(
        actor=care_actor,
        patient=managed_patient,
        relationship=assignment,
        confirmed=True,
    )

    actor = actor_context_from_user(
        user_model.objects.get(username=ADMINISTRATOR_USERNAME)
    )
    for username, dni, license_number in (
        (BROWSER_CREATED_USERNAME, REGISTERED_PROFESSIONAL_DNI, "MN 123456"),
        (MEDICAL_ACTIVE_USERNAME, COMPLETED_ACTIVE_PROFESSIONAL_DNI, "MN 123456"),
        (
            MEDICAL_INACTIVE_USERNAME,
            COMPLETED_INACTIVE_PROFESSIONAL_DNI,
            "MN 123456",
        ),
        (
            MEDICAL_UNPROVISIONED_USERNAME,
            MEDICAL_UNPROVISIONED_DNI,
            MEDICAL_UNPROVISIONED_LICENSE,
        ),
        (
            MEDICAL_LEGACY_STAFF_USERNAME,
            MEDICAL_LEGACY_STAFF_DNI,
            MEDICAL_LEGACY_STAFF_LICENSE,
        ),
    ):
        register_professional(
            actor=actor,
            username=username,
            dni=dni,
            license_number=license_number,
            first_name="Test",
            last_name="Professional",
            date_of_birth=date(1990, 1, 1),
            specialty_code="general-medicine",
            hospital_service_code="inpatient-ward",
        )

    for username, initial_license in (
        (LEGACY_COMPLETE_ACTIVE_USERNAME, LEGACY_COMPLETE_ACTIVE_LICENSE),
        (LEGACY_COMPLETE_INACTIVE_USERNAME, LEGACY_COMPLETE_INACTIVE_LICENSE),
    ):
        profile = Professional.objects.get(user__username=username)
        update_professional(
            actor=actor,
            professional=profile,
            changes={"first_name": "Updated legacy"},
        )
        profile.refresh_from_db()
        assert profile.license_number is None
        update_professional(
            actor=actor,
            professional=profile,
            changes={
                "license_number": f"{initial_license} corrected",
                **(
                    {"specialty_code": "general-medicine"}
                    if username == LEGACY_COMPLETE_INACTIVE_USERNAME
                    else {}
                ),
            },
        )

    with pytest.raises(ProfessionalConflictError):
        register_professional(
            actor=actor,
            username=REACTIVATION_CONFLICT_USERNAME,
            dni=LEGACY_COMPLETE_INACTIVE_DNI,
            license_number=REACTIVATION_CONFLICT_LICENSE,
            first_name="Conflict",
            last_name="Replacement",
            date_of_birth=date(1990, 1, 1),
            specialty_code="general-medicine",
            hospital_service_code="inpatient-ward",
        )
    reactivate_professional(
        actor=actor,
        professional=Professional.objects.get(
            user__username=LEGACY_COMPLETE_INACTIVE_USERNAME
        ),
        confirmed=True,
    )

    temporary_specialty = create_specialty(
        actor=actor,
        code=CATALOG_SPECIALTY_CODE,
        name="Compose catalog specialty",
    )
    delete_specialty(actor=actor, specialty=temporary_specialty)
    terminology, _ = create_catalog_entry(
        actor=actor,
        model=TerminologyEntry,
        values={
            "system": "https://acceptance.example.test/terminology",
            "version": CATALOG_MEDICATION_VERSION,
            "code": CATALOG_TERMINOLOGY_CODE,
            "display": "Compose terminology",
            "source_label": "Compose acceptance source",
        },
    )
    medication, _ = create_catalog_entry(
        actor=actor,
        model=MedicationEntry,
        values={
            "system": CATALOG_MEDICATION_SYSTEM,
            "version": CATALOG_MEDICATION_VERSION,
            "code": CATALOG_MEDICATION_CODE,
            "name": "Compose prescription medication",
            "presentation": "500 mg tablet",
            "source_label": "Compose acceptance source",
        },
    )
    for index in range(21):
        create_catalog_entry(
            actor=actor,
            model=MedicationEntry,
            values={
                "system": "https://acceptance.example.test/upload",
                "version": "2026-09",
                "code": f"UPLOAD-{index:02d}",
                "name": f"Uploaded medication {index:02d}",
                "presentation": "10 mg tablet",
                "source_label": "Acceptance upload",
            },
        )
    acceptance_patient = Patient.objects.get(dni=ACTIVE_PATIENT_DNI)
    medical_actor = actor_context_from_user(
        user_model.objects.get(username=MEDICAL_ACTIVE_USERNAME)
    )
    issue_prescription(
        actor=medical_actor,
        patient=acceptance_patient,
        request_key=uuid4(),
        reason_entry_id=terminology.pk,
        items=[
            {
                "medication_id": medication.pk,
                "dose_value": "500",
                "dose_unit": "mg",
                "route": "oral",
                "frequency": "every 8 hours",
                "duration_days": 5,
                "instructions": "",
            },
            {
                "medication_id": medication.pk,
                "dose_value": "250",
                "dose_unit": "mg",
                "route": "oral",
                "frequency": "at night",
                "duration_days": 3,
                "instructions": "",
            },
        ],
    )
    import_external_bundle(
        actor=medical_actor,
        patient=acceptance_patient,
        request_key=uuid4(),
        source_system=EXTERNAL_IMPORT_SOURCE_SYSTEM,
        xml=(
            Path(
                "docs/interoperability/fhir-r4/fixtures/independent-valid-observation.xml"
            )
            .read_bytes()
            .replace(b"12345678", ACTIVE_PATIENT_DNI.encode())
            .replace(b"1980-04-20", b"1990-01-01")
        ),
    )

    managed_patient = Patient.all_objects.get(dni=ACTIVE_PATIENT_DNI)
    managed_patient.phone = ADMINISTRATIVE_UPDATED_PHONE
    managed_patient.is_active = False
    managed_patient.save(update_fields=["phone", "is_active"])

    call_command("verify_acceptance")
