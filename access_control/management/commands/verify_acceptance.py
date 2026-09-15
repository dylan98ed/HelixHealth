from datetime import UTC, datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from access_control.acceptance_personas import (
    ACTIVE_PATIENT_DNI,
    ADMINISTRATIVE_UPDATED_PHONE,
    ADMISSION_REASON,
    BROWSER_CREATED_USERNAME,
    COMPLETED_ACTIVE_PROFESSIONAL_DNI,
    COMPLETED_INACTIVE_PROFESSIONAL_DNI,
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
    REACTIVATION_CONFLICT_LICENSE,
    REACTIVATION_CONFLICT_USERNAME,
    REGISTERED_PATIENT_DNI,
    REGISTERED_PROFESSIONAL_DNI,
)
from access_control.medical_professionals import (
    has_active_medical_professional_context,
)
from access_control.roles import MEDICAL_PROFESSIONAL_GROUP
from clinical_records.models import Admission
from patients.models import Patient
from professionals.models import Professional


class Command(BaseCommand):
    help = "Verify persisted outcomes from the Compose acceptance journeys."

    def handle(self, *args: object, **options: object) -> None:
        user_model = get_user_model()
        failures: list[str] = []

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
                False,
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

        conflicting = Professional.objects.filter(
            user__username=REACTIVATION_CONFLICT_USERNAME,
            dni=LEGACY_COMPLETE_INACTIVE_DNI,
            license_number=REACTIVATION_CONFLICT_LICENSE,
            is_active=True,
            registration_completed_at__isnull=False,
        ).first()
        if conflicting is None or not conflicting.registration_number:
            failures.append("the visible DNI-conflict registration was not preserved")

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
                "history, every patient field, and Django user."
            )
        )
