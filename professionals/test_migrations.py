from datetime import datetime

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

OLD_PROFESSIONAL = ("professionals", "0003_professional_admission_identity")
NEW_PROFESSIONAL = ("professionals", "0006_professional_license_number")


@pytest.mark.django_db(transaction=True)
def test_professional_upgrade_preserves_legacy_profiles_and_admissions():
    executor = MigrationExecutor(connection)
    latest_migrations = executor.loader.graph.leaf_nodes()

    try:
        old_targets = [("clinical_records", "0001_initial"), OLD_PROFESSIONAL]
        new_targets = [("clinical_records", "0001_initial"), NEW_PROFESSIONAL]
        executor.migrate(old_targets)
        old_apps = executor.loader.project_state(old_targets).apps
        user_model = old_apps.get_model("auth", "User")
        professional_model = old_apps.get_model("professionals", "Professional")
        patient_model = old_apps.get_model("patients", "Patient")
        admission_model = old_apps.get_model("clinical_records", "Admission")

        active_user = user_model.objects.create(username="legacy-active")
        inactive_user = user_model.objects.create(username="legacy-inactive")
        active_profile = professional_model.objects.create(
            user=active_user, is_active=True
        )
        inactive_profile = professional_model.objects.create(
            user=inactive_user, is_active=False
        )
        patient = patient_model.objects.create(
            dni="12345678",
            clinical_record_number="HC-00000001",
            first_name="Test",
            last_name="Patient",
            date_of_birth=datetime(1990, 1, 1).date(),
            sex="unspecified",
            phone="5550101",
            email="test@example.test",
            address="Test street",
            health_insurer="Test insurer",
            is_active=True,
        )
        admission = admission_model.objects.create(
            patient=patient,
            professional=active_profile,
            consultation_reason="Legacy admission",
            systolic_blood_pressure=120,
            diastolic_blood_pressure=80,
            heart_rate=70,
            temperature="36.5",
            created_at=timezone.now(),
        )

        executor = MigrationExecutor(connection)
        executor.migrate(new_targets)
        new_apps = executor.loader.project_state(new_targets).apps
        new_professional = new_apps.get_model("professionals", "Professional")
        new_admission = new_apps.get_model("clinical_records", "Admission")

        active_after = new_professional.objects.get(pk=active_profile.pk)
        inactive_after = new_professional.objects.get(pk=inactive_profile.pk)
        assert active_after.user_id == active_user.pk
        assert active_after.is_active is True
        assert inactive_after.user_id == inactive_user.pk
        assert inactive_after.is_active is False
        for profile in (active_after, inactive_after):
            assert profile.dni is None
            assert profile.registration_number is None
            assert profile.license_number is None
            assert profile.first_name is None
            assert profile.last_name is None
            assert profile.date_of_birth is None
            assert profile.specialty_id is None
            assert profile.hospital_service_id is None
            assert profile.registration_completed_at is None
        assert (
            new_admission.objects.get(pk=admission.pk).professional_id
            == active_profile.pk
        )
        assert new_professional.objects.count() == 2
    finally:
        MigrationExecutor(connection).migrate(latest_migrations)


@pytest.mark.django_db(transaction=True)
def test_professional_upgrade_reverses_and_reapplies_on_empty_database():
    executor = MigrationExecutor(connection)
    latest_migrations = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate([OLD_PROFESSIONAL])
        executor = MigrationExecutor(connection)
        executor.migrate([NEW_PROFESSIONAL])
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT to_regclass('professionals_registration_number_seq')"
            )
            assert cursor.fetchone() == ("professionals_registration_number_seq",)
    finally:
        MigrationExecutor(connection).migrate(latest_migrations)
