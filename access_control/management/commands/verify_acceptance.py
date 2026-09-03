from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from access_control.acceptance_personas import (
    ADMISSION_REASON,
    BROWSER_CREATED_USERNAME,
    MEDICAL_ACTIVE_USERNAME,
    MEDICAL_INACTIVE_USERNAME,
    MEDICAL_LEGACY_STAFF_USERNAME,
    MEDICAL_UNPROVISIONED_USERNAME,
    REGISTERED_PATIENT_DNI,
)
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

        if not user_model.objects.filter(username=BROWSER_CREATED_USERNAME).exists():
            failures.append("the Django Admin user creation was not persisted")

        if failures:
            raise CommandError("; ".join(failures))

        self.stdout.write(
            self.style.SUCCESS(
                "Acceptance persistence verified: provisioned identities, inactive "
                "state, admission, patient, and Django user."
            )
        )
