from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from access_control.actors import ActorContext, ActorRole
from access_control.roles import MEDICAL_PROFESSIONAL_GROUP
from clinical_records.models import Admission
from interoperability.importing import ExternalImportError
from interoperability.models import ExternalClinicalRecord, ImportBatch
from interoperability.services import ImportConflictError, import_external_bundle
from patients.models import Patient
from prescriptions.models import Prescription
from professionals.models import HospitalService, Professional, Specialty

FIXTURE = Path(
    "docs/interoperability/fhir-r4/fixtures/independent-valid-observation.xml"
)
SOURCE_SYSTEM = "https://external.example/identifiers/institution"


def patient() -> Patient:
    return Patient.objects.create(
        dni="12345678",
        clinical_record_number="HC-INTEROP-01",
        first_name="Ana",
        last_name="GarcÃ­a",
        date_of_birth=date(1980, 4, 20),
        sex="unspecified",
        phone="+54 11 5555-0101",
        email="ana@example.test",
        address="Test address",
        health_insurer="Test insurer",
    )


def professional(user_factory):
    user = user_factory(username="interop-doctor")
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    specialty = Specialty.objects.create(code="interop", name="Interoperability")
    service = HospitalService.objects.create(code="interop", name="Interoperability")
    profile = Professional.objects.create(
        user=user,
        dni="70123456",
        registration_number="PR-INTEROP-0001",
        license_number="MN 000001",
        first_name="Eva",
        last_name="Doctor",
        date_of_birth=date(1985, 1, 1),
        specialty=specialty,
        hospital_service=service,
        registration_completed_at=timezone.now(),
    )
    return user, profile


def actor(user) -> ActorContext:
    return ActorContext(
        user_id=user.pk, roles=frozenset({ActorRole.MEDICAL_PROFESSIONAL})
    )


@pytest.mark.django_db
def test_import_is_atomic_idempotent_and_retains_external_provenance(user_factory):
    target = patient()
    user, _ = professional(user_factory)
    xml = FIXTURE.read_bytes()
    result = import_external_bundle(
        actor=actor(user),
        patient=target,
        source_system=SOURCE_SYSTEM,
        request_key=uuid4(),
        xml=xml,
    )
    retry = import_external_bundle(
        actor=actor(user),
        patient=target,
        source_system=SOURCE_SYSTEM,
        request_key=uuid4(),
        xml=xml,
    )

    assert result.created is True
    assert retry.created is False
    assert ImportBatch.objects.count() == 1
    assert ExternalClinicalRecord.objects.count() == 1
    record = ExternalClinicalRecord.objects.get()
    assert record.patient == target
    assert record.external_author["identifier_value"] == "EXT-001"
    assert record.content["coding"]["code"] == "8867-4"
    assert Admission.objects.count() == 0
    assert Prescription.objects.count() == 0
    with pytest.raises(ImportConflictError):
        import_external_bundle(
            actor=actor(user),
            patient=target,
            source_system=SOURCE_SYSTEM,
            request_key=result.batch.request_key,
            xml=xml.replace(b"72", b"73"),
        )
    assert ImportBatch.objects.count() == 1
    assert ExternalClinicalRecord.objects.count() == 1


@pytest.mark.django_db
def test_import_api_rejects_unsafe_or_wrong_mime_without_writes(client, user_factory):
    target = patient()
    user, _ = professional(user_factory)
    client.force_login(user)
    url = reverse("interoperability:api-imports", args=[target.pk])
    wrong_mime = client.post(
        url,
        {
            "request_key": str(uuid4()),
            "source_system": SOURCE_SYSTEM,
            "file": SimpleUploadedFile("bundle.xml", FIXTURE.read_bytes(), "text/xml"),
        },
    )
    unsafe = client.post(
        url,
        {
            "request_key": str(uuid4()),
            "source_system": SOURCE_SYSTEM,
            "file": SimpleUploadedFile(
                "bundle.xml",
                b'<!DOCTYPE x [<!ENTITY e SYSTEM "https://example.test/x">]><Bundle/>',
                "application/fhir+xml",
            ),
        },
    )

    assert wrong_mime.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    assert unsafe.status_code == status.HTTP_400_BAD_REQUEST
    assert ImportBatch.objects.count() == 0
    assert ExternalClinicalRecord.objects.count() == 0


@pytest.mark.django_db
def test_html_import_retry_reuses_the_original_request_key(client, user_factory):
    target = patient()
    user, _ = professional(user_factory)
    original = import_external_bundle(
        actor=actor(user),
        patient=target,
        source_system=SOURCE_SYSTEM,
        request_key=uuid4(),
        xml=FIXTURE.read_bytes(),
    )
    client.force_login(user)
    upload_url = reverse("interoperability:import-upload", args=[target.pk])

    form = client.get(upload_url, {"retry": original.batch.identifier})

    assert form.status_code == status.HTTP_200_OK
    assert f'value="{original.batch.request_key}"'.encode() in form.content
    assert f'value="{SOURCE_SYSTEM}"'.encode() in form.content

    retry = client.post(
        upload_url + f"?retry={original.batch.identifier}",
        {
            "request_key": str(original.batch.request_key),
            "source_system": SOURCE_SYSTEM,
            "file": SimpleUploadedFile(
                "bundle.xml", FIXTURE.read_bytes(), "application/fhir+xml"
            ),
        },
    )

    assert retry.status_code == status.HTTP_302_FOUND
    assert retry.url == reverse(
        "interoperability:import-detail", args=[target.pk, original.batch.identifier]
    )
    assert ImportBatch.objects.count() == 1
    assert ExternalClinicalRecord.objects.count() == 1


@pytest.mark.django_db
def test_import_rejects_wrong_patient_before_writing(user_factory):
    target = patient()
    user, _ = professional(user_factory)
    with pytest.raises(ExternalImportError, match="DNI and birth date"):
        import_external_bundle(
            actor=actor(user),
            patient=target,
            source_system=SOURCE_SYSTEM,
            request_key=uuid4(),
            xml=FIXTURE.read_bytes().replace(b"12345678", b"87654321"),
        )
    assert not ImportBatch.objects.exists()


@pytest.mark.django_db
def test_selected_admission_export_is_patient_scoped_and_has_fhir_mime(
    client, user_factory
):
    target = patient()
    user, profile = professional(user_factory)
    admission = Admission.objects.create(
        patient=target,
        professional=profile,
        consultation_reason="External exchange export",
        systolic_blood_pressure=120,
        diastolic_blood_pressure=80,
        heart_rate=72,
        temperature=Decimal("36.7"),
    )
    client.force_login(user)
    response = client.post(
        reverse("interoperability:api-export", args=[target.pk]),
        {"admission_ids": [admission.pk]},
        content_type="application/json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"].startswith("application/fhir+xml")
    assert b"<Bundle" in b"".join(response.streaming_content)
    missing = client.post(
        reverse("interoperability:api-export", args=[target.pk]),
        {"admission_ids": [999999]},
        content_type="application/json",
    )
    assert missing.status_code == status.HTTP_404_NOT_FOUND
