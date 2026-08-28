from typing import ClassVar

from django.db import migrations

SPECIALTIES = (
    ("cardiology", "Cardiology"),
    ("emergency-medicine", "Emergency Medicine"),
    ("general-medicine", "General Medicine"),
    ("general-surgery", "General Surgery"),
    ("gynecology-obstetrics", "Gynecology and Obstetrics"),
    ("pediatrics", "Pediatrics"),
)

HOSPITAL_SERVICES = (
    ("emergency-department", "Emergency Department"),
    ("inpatient-ward", "Inpatient Ward"),
    ("intensive-care-unit", "Intensive Care Unit"),
    ("operating-room", "Operating Room"),
    ("outpatient-clinic", "Outpatient Clinic"),
)


def seed_reference_data(apps, schema_editor):
    specialty_model = apps.get_model("professionals", "Specialty")
    service_model = apps.get_model("professionals", "HospitalService")

    for code, name in SPECIALTIES:
        specialty_model.objects.get_or_create(
            code=code,
            defaults={"name": name, "is_active": True},
        )
    for code, name in HOSPITAL_SERVICES:
        service_model.objects.get_or_create(
            code=code,
            defaults={"name": name, "is_active": True},
        )


def remove_seeded_reference_data(apps, schema_editor):
    specialty_model = apps.get_model("professionals", "Specialty")
    service_model = apps.get_model("professionals", "HospitalService")

    specialty_model.objects.filter(
        code__in=[code for code, _name in SPECIALTIES]
    ).delete()
    service_model.objects.filter(
        code__in=[code for code, _name in HOSPITAL_SERVICES]
    ).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar = [("professionals", "0001_initial")]

    operations: ClassVar = [
        migrations.RunPython(
            seed_reference_data,
            remove_seeded_reference_data,
        )
    ]
