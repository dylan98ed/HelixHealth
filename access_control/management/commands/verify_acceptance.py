from datetime import UTC, datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, QuerySet

from access_control.acceptance_personas import (
    ACTIVE_PATIENT_DNI,
    ADMINISTRATIVE_ADMISSION_REASON,
    ADMINISTRATIVE_UPDATED_PHONE,
    ADMINISTRATOR_USERNAME,
    ADMISSION_REASON,
    BROWSER_CREATED_USERNAME,
    CARE_COORDINATOR,
    CATALOG_MEDICATION_CODE,
    CATALOG_SPECIALTY_CODE,
    CATALOG_TERMINOLOGY_CODE,
    CHART_REASON,
    CHECK_IN_OPERATOR,
    COMPLETED_ACTIVE_PROFESSIONAL_DNI,
    COMPLETED_INACTIVE_PROFESSIONAL_DNI,
    EXTERNAL_IMPORT_SOURCE_SYSTEM,
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
    REACTIVATION_CONFLICT_USERNAME,
    RECEPTIONIST,
    REGISTERED_PATIENT_DNI,
    REGISTERED_PROFESSIONAL_DNI,
)
from access_control.medical_professionals import (
    has_active_medical_professional_context,
)
from access_control.roles import MEDICAL_PROFESSIONAL_GROUP
from appointments.models import (
    Appointment,
    AppointmentHistory,
    BookingRequest,
    ReminderDelivery,
    WeeklyRule,
)
from audit.models import ClinicalAuditEvent
from catalogs.models import MedicationEntry, TerminologyEntry
from clinical_records.models import (
    Admission,
    CareRelationship,
    Consultation,
    HistoryRevision,
)
from interoperability.models import ExternalClinicalRecord, ImportBatch
from patients.models import Patient
from prescriptions.models import Prescription, PrescriptionItem
from professionals.models import Professional, Specialty


def attendance_verified() -> bool:
    visits = Appointment.objects.filter(patient__dni=PAGINATION_SECOND_PAGE_DNI)
    expected = {
        ("arrival", "pending", "attended", CHECK_IN_OPERATOR),
        ("arrival", "confirmed", "attended", CHECK_IN_OPERATOR),
        ("absence", "confirmed", "absent", CHECK_IN_OPERATOR),
        ("cancel", "confirmed", "canceled", RECEPTIONIST),
    }
    histories = AppointmentHistory.objects.filter(appointment__in=visits)
    final = histories.filter(
        version=2, recorded_at__isnull=False, new_state=F("appointment__state")
    )
    return (
        visits.count() == 4
        and visits.filter(version=2).count() == 4
        and histories.count() == 8
        and set(
            final.values_list(
                "operation", "old_state", "new_state", "operator__username"
            )
        )
        == expected
        and not Admission.objects.filter(
            patient__dni=PAGINATION_SECOND_PAGE_DNI
        ).exists()
        and not CareRelationship.objects.filter(
            patient__dni=PAGINATION_SECOND_PAGE_DNI
        ).exists()
        and not Prescription.objects.filter(
            patient__dni=PAGINATION_SECOND_PAGE_DNI
        ).exists()
    )


def reminder_outcomes_verified() -> bool:
    expected = [
        ("20000017", "missing", 0, "confirmed"),
        ("20000018", "sent", 1, "attended"),
        ("20000019", "review", 1, "confirmed"),
    ]
    rows = ReminderDelivery.objects.filter(
        appointment__patient__dni__in=[row[0] for row in expected],
        appointment__created_by__username=RECEPTIONIST,
        schedule_revision=F("appointment__schedule_revision"),
    ).order_by("appointment__patient__dni")
    return (
        list(
            rows.values_list(
                "appointment__patient__dni", "status", "attempts", "appointment__state"
            )
        )
        == expected
        and confirmed_arrival_verified(rows)
        and rows.filter(status="sent", sent_at__isnull=False).exists()
        and not rows.exclude(status="sent").filter(sent_at__isnull=False).exists()
    )


def confirmed_arrival_verified(rows: QuerySet[ReminderDelivery]) -> bool:
    delivery = rows.select_related("appointment__request").get(
        appointment__patient__dni="20000018"
    )
    visit = delivery.appointment
    intake = visit.request
    if (
        intake is None
        or intake.patient_id != visit.patient_id
        or delivery.sent_at is None
    ):
        return False
    history = list(visit.history.select_related("operator").order_by("version"))
    return (
        Appointment.objects.filter(patient_id=visit.patient_id).count() == 1
        and BookingRequest.objects.filter(patient_id=visit.patient_id).count() == 1
        and intake.status == "confirmed"
        and intake.channel == "phone"
        and list(
            intake.contactattempt_set.order_by("pk").values_list(
                "channel", "outcome", "operator__username"
            )
        )
        == [("phone", "unanswered", RECEPTIONIST), ("phone", "confirmed", RECEPTIONIST)]
        and [
            (event.operation, event.new_state, event.operator.username)
            for event in history
        ]
        == [
            ("reserve", "pending", RECEPTIONIST),
            ("confirm", "confirmed", RECEPTIONIST),
            ("arrival", "attended", CHECK_IN_OPERATOR),
        ]
        and all(
            (event.new_professional_id, event.new_start, event.new_end)
            == (visit.professional_id, visit.start, visit.end)
            for event in history
        )
        and history[1].recorded_at <= delivery.sent_at <= history[2].recorded_at
    )


def chart_documentation_verified() -> bool:
    visits = Consultation.objects.filter(patient__dni="20000016")
    if visits.count() != 1:
        return False
    visit = visits.get()
    notes = list(visit.notes.values_list("author__dni", "text"))
    revisions = HistoryRevision.objects.filter(entry__patient=visit.patient).order_by(
        "entry__category", "version"
    )
    events = ClinicalAuditEvent.objects.filter(patient=visit.patient)
    return (
        visit.reason == "Follow-up after arrival"
        and visit.author.dni == "31000000"
        and visit.visited_at == datetime(2026, 1, 15, 12, 45, tzinfo=UTC)
        and notes == [("31000001", "Follow-up completed by the second physician.")]
        and list(
            revisions.values_list(
                "entry__category",
                "version",
                "relationship",
                "description",
                "author__dni",
            )
        )
        == [
            ("family", 1, "Mother", "Family history reported at intake.", "31000000"),
            (
                "family",
                2,
                "Sister",
                "Family history clarified at follow-up.",
                "31000001",
            ),
            ("personal", 1, "", "Previous outpatient follow-up.", "31000000"),
        ]
        and sorted(events.values_list("source_type", "operation"))
        == [
            ("clinical_records.admission", "create"),
            ("clinical_records.consultation", "create"),
            ("clinical_records.historyentry", "create"),
            ("clinical_records.historyentry", "create"),
            ("clinical_records.historyentry", "revise"),
            ("clinical_records.progressnote", "create"),
            ("interoperability.importedmedicationrequest", "import"),
            ("interoperability.importedservicerequest", "import"),
        ]
    )


def chart_access_verified() -> bool:
    team = CareRelationship.objects.filter(patient__dni__in=["20000015", "20000016"])
    assignments = team.order_by("patient__dni", "professional__dni").values_list(
        "patient__dni",
        "professional__dni",
        "is_active",
        "assigned_by__username",
        "revoked_by__username",
    )
    visits = Appointment.objects.filter(
        patient__dni="20000016",
        professional__dni="31000000",
        created_by__username=RECEPTIONIST,
    )
    return (
        chart_documentation_verified()
        and list(assignments)
        == [
            ("20000015", "31000000", True, CARE_COORDINATOR, None),
            ("20000016", "31000000", False, CARE_COORDINATOR, CARE_COORDINATOR),
            ("20000016", "31000001", True, CARE_COORDINATOR, None),
        ]
        and list(visits.order_by("start").values_list("state", flat=True))
        == ["attended", "canceled"]
        and Admission.objects.filter(
            patient__dni="20000016",
            recorded_by__username=CARE_COORDINATOR,
            consultation_reason=CHART_REASON,
            systolic_blood_pressure=118,
            diastolic_blood_pressure=76,
        ).count()
        == 1
    )


class Command(BaseCommand):
    help = "Verify persisted outcomes from the Compose acceptance journeys."

    def handle(self, *args: object, **options: object) -> None:
        user_model = get_user_model()
        failures: list[str] = []
        if not chart_access_verified():
            failures.append(
                "the expected chart documentation, audit, care assignments or appointment states did not persist"
            )
        if not reminder_outcomes_verified():
            failures.append(
                "the confirmed phone request, reminder, arrival history or other delivery outcomes did not persist"
            )
        if not attendance_verified():
            failures.append(
                "attendance, operator history or the check-in patient's clinical record differed from the expected outcomes"
            )

        bookings = Appointment.objects.filter(
            created_by__username=RECEPTIONIST,
            request__isnull=True,
            patient__dni=ACTIVE_PATIENT_DNI,
        )
        selected = bookings.filter(
            patient__dni=ACTIVE_PATIENT_DNI,
            state="confirmed",
            professional__user__username=f"{PAGED_ACTIVE_USERNAME_PREFIX}-01",
            history__operation="reserve",
            history__operator__username=RECEPTIONIST,
        )
        if (
            bookings.count() != 1
            or not selected.exists()
            or AppointmentHistory.objects.filter(appointment__in=bookings).count() != 1
            or WeeklyRule.objects.filter(
                professional__user__username__in=[
                    f"{PAGED_ACTIVE_USERNAME_PREFIX}-00",
                    f"{PAGED_ACTIVE_USERNAME_PREFIX}-01",
                ]
            ).count()
            != 2
        ):
            failures.append(
                "the chosen professional, confirmed booking, operator history or weekly hours did not persist"
            )

        for channel in ("phone", "whatsapp"):
            linked = Appointment.objects.select_related("request").filter(
                request__channel=channel,
                request__created_by__username=RECEPTIONIST,
                request__status="confirmed",
                state="confirmed",
                patient__dni=ACTIVE_PATIENT_DNI,
            )
            row = linked.first()
            if linked.count() != 1 or row is None or row.request is None:
                failures.append(
                    f"{channel} request did not retain exactly one confirmed appointment"
                )
                continue
            contacts = row.request.contactattempt_set.order_by("pk").values_list(
                "channel", "outcome", "operator__username"
            )
            expected = [
                (channel, outcome, RECEPTIONIST)
                for outcome in ("unanswered", "confirmed")
            ]
            operations = list(
                row.history.order_by("version").values_list("operation", flat=True)
            )
            if list(contacts) != expected or operations != (
                ["reserve", "confirm"] if channel == "phone" else ["reserve"]
            ):
                failures.append(
                    f"{channel} contact history or booking history did not persist"
                )

        care_history = CareRelationship.objects.filter(
            patient__dni=ACTIVE_PATIENT_DNI,
            professional__dni=LEGACY_COMPLETE_ACTIVE_DNI,
        )
        if (
            care_history.count() != 1
            or not care_history.filter(
                is_active=False,
                assigned_at__isnull=False,
                assigned_by__username=ADMINISTRATOR_USERNAME,
                revoked_at__isnull=False,
                revoked_by__username=ADMINISTRATOR_USERNAME,
            ).exists()
        ):
            failures.append(
                "the care-team assignment and revocation were not persisted"
            )

        if not Professional.objects.filter(
            user__username=MEDICAL_INACTIVE_USERNAME,
            is_active=False,
        ).exists():
            failures.append("the inactive professional state was not preserved")

        if not Admission.objects.filter(
            professional__user__username=MEDICAL_ACTIVE_USERNAME,
            consultation_reason=ADMISSION_REASON,
        ).exists():
            failures.append("the medical admission was not persisted")

        if not Admission.objects.filter(
            patient__dni=ACTIVE_PATIENT_DNI,
            professional__isnull=True,
            recorded_by__username=ADMINISTRATOR_USERNAME,
            consultation_reason=ADMINISTRATIVE_ADMISSION_REASON,
            created_at__isnull=False,
        ).exists():
            failures.append("the administrative admission was not persisted")

        if not Patient.objects.filter(dni=REGISTERED_PATIENT_DNI).exists():
            failures.append("the administrative patient registration was not persisted")

        if not Patient.all_objects.filter(
            dni=ACTIVE_PATIENT_DNI,
            phone=ADMINISTRATIVE_UPDATED_PHONE,
            is_active=False,
        ).exists():
            failures.append("the administrative patient update and deactivation failed")

        if not user_model.objects.filter(username=BROWSER_CREATED_USERNAME).exists():
            failures.append("the Django Admin user creation was not persisted")

        if Specialty.objects.filter(code=CATALOG_SPECIALTY_CODE).exists():
            failures.append("the unreferenced catalog specialty was not deleted")
        if not TerminologyEntry.objects.filter(code=CATALOG_TERMINOLOGY_CODE).exists():
            failures.append("the catalog terminology entry was not persisted")
        medication = MedicationEntry.objects.filter(
            code=CATALOG_MEDICATION_CODE
        ).first()
        if medication is None or medication.name != "Compose prescription medication":
            failures.append("the catalog medication entry was not persisted")

        if (
            MedicationEntry.objects.filter(
                system="https://acceptance.example.test/upload",
                code__startswith="UPLOAD-",
            ).count()
            != 21
            or MedicationEntry.objects.filter(code="REJECTED-UPLOAD").exists()
        ):
            failures.append("catalog upload retry or atomic rejection failed")

        acceptance_patient = Patient.all_objects.filter(dni=ACTIVE_PATIENT_DNI).first()
        if acceptance_patient is None:
            failures.append("the acceptance patient is missing for clinical checks")
        else:
            prescriptions = Prescription.objects.filter(
                patient=acceptance_patient,
                prescriber__user__username=MEDICAL_ACTIVE_USERNAME,
            )
            if (
                prescriptions.count() != 1
                or PrescriptionItem.objects.filter(
                    prescription__in=prescriptions,
                    medication__code=CATALOG_MEDICATION_CODE,
                ).count()
                != 2
            ):
                failures.append("the medical prescription issue was not persisted")
            imports = ImportBatch.objects.filter(patient=acceptance_patient)
            if (
                imports.count() != 1
                or not imports.filter(
                    source_system=EXTERNAL_IMPORT_SOURCE_SYSTEM
                ).exists()
            ):
                failures.append(
                    "the matching external FHIR import was not persisted once"
                )
            if (
                ExternalClinicalRecord.objects.filter(
                    patient=acceptance_patient
                ).count()
                != 1
            ):
                failures.append("the external FHIR record was not persisted once")

        record = ExternalClinicalRecord.objects.filter(
            patient=acceptance_patient
        ).first()
        if record is None or (
            record.external_author.get("identifier_value") != "EXT-001"
            or record.content.get("coding", {}).get("code") != "8867-4"
            or record.source_system != EXTERNAL_IMPORT_SOURCE_SYSTEM
        ):
            failures.append("external provenance or observation coding changed")
        if (
            Admission.objects.filter(
                patient=acceptance_patient, consultation_reason=ADMISSION_REASON
            ).count()
            != 1
        ):
            failures.append("external import changed local admission count")

        for username, dni, license_number, active, is_staff in (
            (
                BROWSER_CREATED_USERNAME,
                REGISTERED_PROFESSIONAL_DNI,
                "MN 123456",
                True,
                False,
            ),
            (
                MEDICAL_ACTIVE_USERNAME,
                COMPLETED_ACTIVE_PROFESSIONAL_DNI,
                "MN 123456",
                True,
                False,
            ),
            (
                MEDICAL_INACTIVE_USERNAME,
                COMPLETED_INACTIVE_PROFESSIONAL_DNI,
                "MN 123456",
                False,
                False,
            ),
            (
                MEDICAL_UNPROVISIONED_USERNAME,
                MEDICAL_UNPROVISIONED_DNI,
                MEDICAL_UNPROVISIONED_LICENSE,
                True,
                False,
            ),
            (
                MEDICAL_LEGACY_STAFF_USERNAME,
                MEDICAL_LEGACY_STAFF_DNI,
                MEDICAL_LEGACY_STAFF_LICENSE,
                True,
                True,
            ),
        ):
            if not Professional.objects.filter(
                user__username=username,
                user__is_staff=is_staff,
                user__groups__name=MEDICAL_PROFESSIONAL_GROUP,
                dni=dni,
                is_active=active,
                registration_completed_at__isnull=False,
                registration_number__isnull=False,
                license_number=license_number,
            ).exists():
                failures.append(
                    f"professional registration/completion was not persisted for {username}"
                )

        eligible_usernames = (
            BROWSER_CREATED_USERNAME,
            MEDICAL_ACTIVE_USERNAME,
            MEDICAL_UNPROVISIONED_USERNAME,
            MEDICAL_LEGACY_STAFF_USERNAME,
        )
        for username in eligible_usernames:
            user = user_model.objects.get(username=username)
            if not has_active_medical_professional_context(user):
                failures.append(
                    f"clinical eligibility was not established for {username}"
                )
        if has_active_medical_professional_context(
            user_model.objects.get(username=MEDICAL_INACTIVE_USERNAME)
        ):
            failures.append("the inactive professional became clinically eligible")

        completed_at = datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC)
        for username, dni, registration_number, active, initial_license in (
            (
                LEGACY_COMPLETE_ACTIVE_USERNAME,
                LEGACY_COMPLETE_ACTIVE_DNI,
                LEGACY_COMPLETE_ACTIVE_REGISTRATION_NUMBER,
                True,
                LEGACY_COMPLETE_ACTIVE_LICENSE,
            ),
            (
                LEGACY_COMPLETE_INACTIVE_USERNAME,
                LEGACY_COMPLETE_INACTIVE_DNI,
                LEGACY_COMPLETE_INACTIVE_REGISTRATION_NUMBER,
                True,
                LEGACY_COMPLETE_INACTIVE_LICENSE,
            ),
        ):
            profile = (
                Professional.objects.select_related("user")
                .filter(user__username=username)
                .first()
            )
            if profile is None:
                failures.append(f"completed legacy profile is missing for {username}")
                continue
            if (
                profile.dni != dni
                or profile.registration_number != registration_number
                or profile.registration_completed_at != completed_at
                or profile.is_active != active
                or profile.license_number != f"{initial_license} corrected"
                or profile.first_name != "Updated legacy"
                or profile.last_name != "Completed"
                or profile.specialty is None
                or profile.specialty.code != "general-medicine"
                or profile.hospital_service is None
                or profile.hospital_service.code != "inpatient-ward"
                or profile.user is None
                or not profile.user.is_active
                or profile.user.is_staff
                or profile.user.is_superuser
                or set(profile.user.groups.values_list("name", flat=True))
                != {MEDICAL_PROFESSIONAL_GROUP}
            ):
                failures.append(
                    f"completed legacy identity/state was not preserved for {username}"
                )
            if (
                Admission.objects.filter(
                    professional=profile,
                    consultation_reason=f"Legacy completed history {username}",
                ).count()
                != 1
            ):
                failures.append(
                    f"completed legacy history was not preserved for {username}"
                )

        if Professional.objects.filter(
            user__username=REACTIVATION_CONFLICT_USERNAME,
            dni=LEGACY_COMPLETE_INACTIVE_DNI,
        ).exists():
            failures.append("the inactive professional DNI was duplicated")

        if (
            Professional.objects.filter(
                user__username__startswith=PAGED_ACTIVE_USERNAME_PREFIX,
                is_active=True,
                registration_completed_at__isnull=False,
                registration_number__isnull=False,
                license_number__startswith="SYN-ACTIVE-",
            ).count()
            != 21
        ):
            failures.append("the 21 active pagination professionals are incomplete")
        if (
            Professional.objects.filter(
                user__username__startswith=PAGED_INACTIVE_USERNAME_PREFIX,
                is_active=False,
                registration_completed_at__isnull=False,
                registration_number__isnull=False,
                license_number__startswith="SYN-INACTIVE-",
            ).count()
            != 21
        ):
            failures.append("the 21 inactive pagination professionals are incomplete")
        if (
            Professional.objects.filter(
                user__username__startswith=PAGED_INCOMPLETE_USERNAME_PREFIX,
                registration_completed_at__isnull=True,
                registration_number__isnull=True,
                license_number__isnull=True,
            ).count()
            != 21
        ):
            failures.append("the 21 incomplete pagination professionals changed state")

        managed_patient = Patient.all_objects.filter(dni=ACTIVE_PATIENT_DNI).first()
        expected_patient = {
            "clinical_record_number": "HC-ACCEPTANCE-ACTIVE",
            "first_name": "Acceptance",
            "last_name": "Patient",
            "date_of_birth": datetime(1990, 1, 1).date(),
            "sex": "unspecified",
            "phone": ADMINISTRATIVE_UPDATED_PHONE,
            "email": f"{ACTIVE_PATIENT_DNI}@acceptance.example.test",
            "address": "Acceptance Test Street 123",
            "health_insurer": "Acceptance Health",
            "is_active": False,
        }
        if managed_patient is None or any(
            getattr(managed_patient, field) != value
            for field, value in expected_patient.items()
        ):
            failures.append("the patient journey did not preserve every existing field")

        if failures:
            raise CommandError("; ".join(failures))

        self.stdout.write(
            self.style.SUCCESS(
                "Acceptance persistence verified: registered identities and generated "
                "numbers, strict clinical eligibility, pagination fixtures, legacy "
                "history, every patient field, and Django user. Verified booking, "
                "phone confirmation, reminder delivery, attendance, chart revisions and audit events."
            )
        )
