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
    MEDICAL_LEGACY_STAFF_USERNAME,
    MEDICAL_UNPROVISIONED_USERNAME,
    REGISTERED_PATIENT_DNI,
    REGISTERED_PROFESSIONAL_DNI,
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

        for username in (
            MEDICAL_UNPROVISIONED_USERNAME,
            MEDICAL_LEGACY_STAFF_USERNAME,
        ):
            if not Professional.objects.filter(
                user__username=username,
                is_active=True,
            ).exists():
                failures.append(f"{username} was not provisioned as active")

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

        for username, dni, active in (
            (BROWSER_CREATED_USERNAME, REGISTERED_PROFESSIONAL_DNI, True),
            (MEDICAL_ACTIVE_USERNAME, COMPLETED_ACTIVE_PROFESSIONAL_DNI, True),
            (MEDICAL_INACTIVE_USERNAME, COMPLETED_INACTIVE_PROFESSIONAL_DNI, False),
        ):
            if not Professional.objects.filter(
                user__username=username,
                user__is_staff=False,
                user__groups__name=MEDICAL_PROFESSIONAL_GROUP,
                dni=dni,
                is_active=active,
                registration_completed_at__isnull=False,
                registration_number__isnull=False,
                license_number="MN 123456",
            ).exists():
                failures.append(
                    f"professional registration/completion was not persisted for {username}"
                )

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

        if failures:
            raise CommandError("; ".join(failures))

        self.stdout.write(
            self.style.SUCCESS(
                "Acceptance persistence verified: provisioned identities, inactive "
                "state, completed legacy identities/history, patient management, and Django user."
            )
        )
