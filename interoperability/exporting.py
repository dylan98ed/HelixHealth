"""Read-only selected-record FHIR export boundary."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from django.http import Http404

from clinical_records.models import Admission
from interoperability.fhir_export import FhirExportError, serialize_admission_bundle
from interoperability.limits import MAX_BUNDLE_BYTES
from patients.models import Patient
from prescriptions.models import Prescription


class ExportSelectionError(ValueError):
    """The requested selection is not a supported, patient-owned export."""


def export_selected_records(
    *, patient: Patient, admission_ids: Iterable[int], prescription_ids: Iterable[UUID]
) -> bytes:
    requested_admissions = tuple(admission_ids)
    requested_prescriptions = tuple(prescription_ids)
    admissions = tuple(
        Admission.objects.filter(
            patient=patient, pk__in=set(requested_admissions)
        ).select_related("patient", "professional")
    )
    if len(admissions) != len(requested_admissions):
        raise Http404
    prescriptions = tuple(
        Prescription.objects.filter(
            patient=patient, identifier__in=set(requested_prescriptions)
        )
    )
    if len(prescriptions) != len(requested_prescriptions):
        raise Http404
    if admissions and prescriptions:
        raise ExportSelectionError(
            "Export admissions or a prescription in separate files."
        )
    if admissions:
        try:
            return serialize_admission_bundle(admissions)
        except FhirExportError as error:
            raise ExportSelectionError(str(error)) from error
    if len(prescriptions) == 1:
        xml = bytes(prescriptions[0].fhir_xml)
        if len(xml) > MAX_BUNDLE_BYTES:
            raise ExportSelectionError("FHIR exports may not exceed 2 MiB.")
        return xml
    raise ExportSelectionError("Select at least one supported clinical record.")
