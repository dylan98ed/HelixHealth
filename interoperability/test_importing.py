from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from lxml import etree
from rest_framework import status

from access_control.actors import ActorContext, ActorRole
from access_control.roles import MEDICAL_PROFESSIONAL_GROUP
from clinical_records.models import Admission
from interoperability.importing import ExternalImportError, parse_external_bundle
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
def test_import_rejects_reused_external_record_with_changed_author(user_factory):
    target = patient()
    user, _ = professional(user_factory)
    xml = FIXTURE.read_bytes()
    import_external_bundle(
        actor=actor(user),
        patient=target,
        source_system=SOURCE_SYSTEM,
        request_key=uuid4(),
        xml=xml,
    )

    with pytest.raises(ImportConflictError, match="different content"):
        import_external_bundle(
            actor=actor(user),
            patient=target,
            source_system=SOURCE_SYSTEM,
            request_key=uuid4(),
            xml=xml.replace(b"EXT-001", b"EXT-002"),
        )

    assert ImportBatch.objects.count() == 1
    assert (
        ExternalClinicalRecord.objects.get().external_author["identifier_value"]
        == "EXT-001"
    )


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

    mixed_selection = client.post(
        reverse("interoperability:export", args=[target.pk]),
        {"admission_ids": [admission.pk], "prescription_ids": [str(uuid4())]},
    )
    assert mixed_selection.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        b"Export admissions or one prescription in a separate file."
        in mixed_selection.content
    )
    assert b"non_field_errors" not in mixed_selection.content


@pytest.mark.django_db
@pytest.mark.parametrize("identifier_case", ["wrong-system", "duplicate", "dni-second"])
def test_import_selects_one_identifier_from_the_agreed_dni_system(
    client, user_factory, identifier_case
):
    target = patient()
    user, _ = professional(user_factory)
    client.force_login(user)
    root = etree.fromstring(FIXTURE.read_bytes())
    ns = {"f": "http://hl7.org/fhir"}
    patient_node = root.find("f:entry/f:resource/f:Patient", ns)
    identifier = patient_node.find("f:identifier", ns)
    if identifier_case == "wrong-system":
        identifier.find("f:system", ns).set(
            "value", "https://external.example/identifiers/mrn"
        )
    else:
        extra = etree.fromstring(etree.tostring(identifier))
        if identifier_case == "dni-second":
            extra.find("f:system", ns).set(
                "value", "https://external.example/identifiers/mrn"
            )
            extra.find("f:value", ns).set("value", "99999999")
        patient_node.insert(patient_node.index(identifier), extra)
    response = client.post(
        reverse("interoperability:api-imports", args=[target.pk]),
        {
            "request_key": str(uuid4()),
            "source_system": SOURCE_SYSTEM,
            "file": SimpleUploadedFile(
                "bundle.xml", etree.tostring(root), "application/fhir+xml"
            ),
        },
    )
    if identifier_case == "dni-second":
        assert response.status_code == 201, response.content
        assert ExternalClinicalRecord.objects.get().patient_id == target.pk
    else:
        assert response.status_code == 400, response.content
        assert b"exactly one DNI identifier" in response.content
        assert not ImportBatch.objects.exists()
        assert not ExternalClinicalRecord.objects.exists()


def _export_admission(target, profile):
    return Admission(
        patient=target,
        professional=profile,
        consultation_reason="Review export",
        systolic_blood_pressure=120,
        diastolic_blood_pressure=80,
        heart_rate=72,
        temperature=Decimal("36.7"),
    )


@pytest.mark.django_db
def test_export_reports_different_authors_in_html_and_api(client, user_factory):
    target = patient()
    user, profile = professional(user_factory)
    other = Professional.objects.create(
        user=user_factory(username="other-export-author")
    )
    admissions = Admission.objects.bulk_create(
        [_export_admission(target, profile), _export_admission(target, other)]
    )
    client.force_login(user)
    payload = {"admission_ids": [record.pk for record in admissions]}
    for route in ("api-export", "export"):
        kwargs = {"content_type": "application/json"} if route == "api-export" else {}
        response = client.post(
            reverse(f"interoperability:{route}", args=[target.pk]), payload, **kwargs
        )
        assert response.status_code == 400
        assert (
            b"Admissions with different authors require separate exports."
            in response.content
        )
    assert Admission.objects.count() == 2


@pytest.mark.django_db
def test_export_admission_boundary_produces_an_importable_bundle(client, user_factory):
    target = patient()
    user, profile = professional(user_factory)
    admissions = Admission.objects.bulk_create(
        [_export_admission(target, profile) for _ in range(166)]
    )
    client.force_login(user)
    url = reverse("interoperability:api-export", args=[target.pk])
    accepted = client.post(
        url,
        {"admission_ids": [a.pk for a in admissions[:165]]},
        content_type="application/json",
    )
    assert accepted.status_code == 200
    xml = b"".join(accepted.streaming_content)
    parsed = parse_external_bundle(
        xml, source_system=settings.INTEROPERABILITY_INSTITUTION_SYSTEM
    )
    assert len(parsed.records) == 495
    rejected = client.post(
        url,
        {"admission_ids": [a.pk for a in admissions]},
        content_type="application/json",
    )
    assert rejected.status_code == 400
    assert b"Select at most 165 admissions" in rejected.content
    assert Admission.objects.count() == 166


@pytest.mark.django_db
def test_export_byte_limit_returns_feedback(client, user_factory, monkeypatch):
    target = patient()
    user, profile = professional(user_factory)
    admission = _export_admission(target, profile)
    admission.save()
    client.force_login(user)
    monkeypatch.setattr("interoperability.fhir_export.MAX_BUNDLE_BYTES", 100)
    response = client.post(
        reverse("interoperability:api-export", args=[target.pk]),
        {"admission_ids": [admission.pk]},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert b"select fewer records" in response.content
    assert Admission.objects.count() == 1
