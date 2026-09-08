import os
from datetime import UTC, date, datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from access_control.acceptance_personas import (
    ACCEPTANCE_PASSWORD_ENV,
    ACTIVE_PATIENT_DNI,
    ADMINISTRATOR_USERNAME,
    DJANGO_ADMIN_USERNAME,
    INACTIVE_PATIENT_DNI,
    LEGACY_COMPLETE_ACTIVE_DNI,
    LEGACY_COMPLETE_ACTIVE_REGISTRATION_NUMBER,
    LEGACY_COMPLETE_ACTIVE_USERNAME,
    LEGACY_COMPLETE_INACTIVE_DNI,
    LEGACY_COMPLETE_INACTIVE_REGISTRATION_NUMBER,
    LEGACY_COMPLETE_INACTIVE_USERNAME,
    MEDICAL_ACTIVE_USERNAME,
    MEDICAL_INACTIVE_USERNAME,
    MEDICAL_LEGACY_STAFF_USERNAME,
    MEDICAL_UNPROVISIONED_USERNAME,
)
from access_control.roles import ADMINISTRATIVE_GROUP, MEDICAL_PROFESSIONAL_GROUP
from clinical_records.models import Admission
from patients.models import Patient
from professionals.models import HospitalService, Professional, Specialty


class Command(BaseCommand):
    help = "Seed deterministic personas for the disposable acceptance stack."

    def handle(self, *args: object, **options: object) -> None:
        environment = getattr(settings, "ENVIRONMENT", "production")
        if environment not in {"development", "test"}:
            raise CommandError(
                "Acceptance personas may be seeded only in development or test."
            )

        password = os.environ.get(ACCEPTANCE_PASSWORD_ENV, "")
        if len(password) < 12:
            raise CommandError(
                f"{ACCEPTANCE_PASSWORD_ENV} must contain at least 12 characters."
            )

        user_model = get_user_model()
        administrative_group = Group.objects.get(name=ADMINISTRATIVE_GROUP)
        medical_group = Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP)

        django_admin, _ = user_model.objects.update_or_create(
            username=DJANGO_ADMIN_USERNAME,
            defaults={
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        django_admin.set_password(password)
        django_admin.save(update_fields=["password"])

        administrator, _ = user_model.objects.update_or_create(
            username=ADMINISTRATOR_USERNAME,
            defaults={
                "is_active": True,
                "is_staff": False,
                "is_superuser": False,
            },
        )
        administrator.set_password(password)
        administrator.save(update_fields=["password"])
        administrator.groups.set([administrative_group])

        medical_users = {}
        for username, is_staff in (
            (MEDICAL_UNPROVISIONED_USERNAME, False),
            (MEDICAL_LEGACY_STAFF_USERNAME, True),
            (MEDICAL_ACTIVE_USERNAME, False),
            (MEDICAL_INACTIVE_USERNAME, False),
        ):
            user, _ = user_model.objects.update_or_create(
                username=username,
                defaults={
                    "is_active": True,
                    "is_staff": is_staff,
                    "is_superuser": False,
                },
            )
            user.set_password(password)
            user.save(update_fields=["password"])
            user.groups.set([medical_group])
            medical_users[username] = user

        Professional.objects.update_or_create(
            user=medical_users[MEDICAL_ACTIVE_USERNAME],
            defaults={"is_active": True},
        )
        Professional.objects.update_or_create(
            user=medical_users[MEDICAL_INACTIVE_USERNAME],
            defaults={"is_active": False},
        )

        specialty = Specialty.objects.get(code="general-medicine")
        hospital_service = HospitalService.objects.get(code="inpatient-ward")
        completed_at = datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC)
        legacy_profiles = []
        for username, dni, registration_number, is_active in (
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
            user, _ = user_model.objects.update_or_create(
                username=username,
                defaults={"is_active": True, "is_staff": False, "is_superuser": False},
            )
            user.set_password(password)
            user.save(update_fields=["password"])
            user.groups.set([medical_group])
            profile, _ = Professional.objects.update_or_create(
                user=user,
                defaults={
                    "is_active": is_active,
                    "dni": dni,
                    "registration_number": registration_number,
                    "license_number": None,
                    "first_name": "Legacy",
                    "last_name": "Completed",
                    "date_of_birth": date(1990, 1, 1),
                    "specialty": specialty,
                    "hospital_service": hospital_service,
                    "registration_completed_at": completed_at,
                },
            )
            legacy_profiles.append(profile)

        for username in (
            MEDICAL_UNPROVISIONED_USERNAME,
            MEDICAL_LEGACY_STAFF_USERNAME,
        ):
            if Professional.objects.filter(user=medical_users[username]).exists():
                raise CommandError(
                    f"{username} must not have a professional profile in a fresh "
                    "acceptance database."
                )

        self._upsert_patient(
            dni=ACTIVE_PATIENT_DNI,
            clinical_record_number="HC-ACCEPTANCE-ACTIVE",
            first_name="Acceptance",
            last_name="Patient",
            is_active=True,
        )
        self._upsert_patient(
            dni=INACTIVE_PATIENT_DNI,
            clinical_record_number="HC-ACCEPTANCE-INACTIVE",
            first_name="Inactive",
            last_name="Patient",
            is_active=False,
        )
        for offset in range(21):
            self._upsert_patient(
                dni=f"200000{offset:02d}",
                clinical_record_number=f"HC-ACCEPTANCE-PAGE-{offset:02d}",
                first_name=f"Patient {offset:02d}",
                last_name="Zpagination",
                is_active=True,
            )

        for profile in legacy_profiles:
            patient = Patient.objects.get(dni=ACTIVE_PATIENT_DNI)
            Admission.objects.get_or_create(
                patient=patient,
                professional=profile,
                consultation_reason=f"Legacy completed history {profile.user.username}",
                defaults={
                    "systolic_blood_pressure": 120,
                    "diastolic_blood_pressure": 80,
                    "heart_rate": 72,
                    "temperature": "36.7",
                },
            )

        self.stdout.write(self.style.SUCCESS("Acceptance personas seeded."))

    def _upsert_patient(
        self,
        *,
        dni: str,
        clinical_record_number: str,
        first_name: str,
        last_name: str,
        is_active: bool,
    ) -> None:
        Patient.all_objects.update_or_create(
            dni=dni,
            defaults={
                "clinical_record_number": clinical_record_number,
                "first_name": first_name,
                "last_name": last_name,
                "date_of_birth": date(1990, 1, 1),
                "sex": "unspecified",
                "phone": "+54 11 5555-0100",
                "email": f"{dni}@acceptance.example.test",
                "address": "Acceptance Test Street 123",
                "health_insurer": "Acceptance Health",
                "is_active": is_active,
            },
        )
