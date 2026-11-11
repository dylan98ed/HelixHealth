"""Authorized HTML and JSON endpoints for external FHIR exchange."""

from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
)
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from access_control.actors import actor_context_from_user
from access_control.medical_professionals import IsActiveMedicalProfessionalActor
from clinical_records.models import Admission
from clinical_records.services import active_professional_for_actor
from clinical_records.views import medical_professional_required
from interoperability.exporting import ExportSelectionError, export_selected_records
from interoperability.forms import ExternalImportForm, JsonImportForm
from interoperability.importing import ExternalImportError
from interoperability.json_exporting import (
    JsonExportSelectionError,
    export_selected_json,
    json_export_filename,
)
from interoperability.json_importing import JsonImportError
from interoperability.json_services import JsonImportConflict, import_json_bundle
from interoperability.models import (
    ExternalClinicalRecord,
    ImportBatch,
    ImportedMedicationRequest,
    ImportedServiceRequest,
    JsonImportBatch,
)
from interoperability.serializers import (
    ExportRequestSerializer,
    ImportBatchPageSerializer,
    ImportBatchSerializer,
    ImportRequestSerializer,
    JsonExportRequestSerializer,
)
from interoperability.services import ImportConflictError, import_external_bundle
from patients.models import Patient
from prescriptions.models import Prescription

IMPORTS_PER_PAGE = 20


@medical_professional_required
@require_http_methods(["GET", "POST"])
def json_import_upload(request: HttpRequest) -> HttpResponse:
    initial: dict[str, object] = {"request_key": uuid4()}
    retry_identifier = request.GET.get("retry")
    if retry_identifier:
        prior = get_object_or_404(JsonImportBatch, identifier=retry_identifier)
        initial = {
            "request_key": prior.request_key,
            "source_system": prior.source_system,
        }
    form = JsonImportForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            result = import_json_bundle(
                actor=actor_context_from_user(request.user),
                request_key=form.cleaned_data["request_key"],
                source_system=form.cleaned_data["source_system"],
                raw_json=form.cleaned_data["file"].read(),
            )
        except (JsonImportError, JsonImportConflict) as error:
            form.add_error(None, str(error))
        else:
            return redirect(
                "interoperability:json-import-detail",
                identifier=result.batch.identifier,
            )
    recent = JsonImportBatch.objects.select_related("patient", "practitioner")[:20]
    return render(
        request,
        "interoperability/json_import_form.html",
        {"form": form, "recent": recent},
    )


@medical_professional_required
@require_http_methods(["GET"])
def json_import_detail(request: HttpRequest, identifier: str) -> HttpResponse:
    batch = get_object_or_404(
        JsonImportBatch.objects.select_related("patient", "practitioner"),
        identifier=identifier,
    )
    response = render(
        request, "interoperability/json_import_detail.html", {"batch": batch}
    )
    response["Cache-Control"] = "no-store"
    return response


@medical_professional_required
@require_http_methods(["GET"])
def json_import_file(request: HttpRequest, identifier: str) -> FileResponse:
    batch = get_object_or_404(JsonImportBatch, identifier=identifier)
    response = FileResponse(
        BytesIO(bytes(batch.raw_json)),
        as_attachment=True,
        filename=f"import-{batch.identifier}.json",
        content_type="application/fhir+json; charset=utf-8",
    )
    response["Cache-Control"] = "no-store"
    return response


def _patient_or_404(patient_pk: int) -> Patient:
    return get_object_or_404(Patient.objects, pk=patient_pk)


def _batch_or_404(patient: Patient, identifier: str) -> ImportBatch:
    try:
        return ImportBatch.objects.prefetch_related("records").get(
            patient=patient, identifier=identifier
        )
    except ImportBatch.DoesNotExist as error:
        raise Http404 from error


def _render_exchange_home(
    request: HttpRequest,
    patient: Patient,
    *,
    export_error: str | None = None,
    selected_admission_ids: tuple[str, ...] = (),
    selected_prescription_ids: tuple[str, ...] = (),
    status_code: int = 200,
    json_export_error: str | None = None,
    selected_service_request_ids: tuple[str, ...] = (),
    selected_medication_request_ids: tuple[str, ...] = (),
    selected_json_prescription_ids: tuple[str, ...] = (),
    selected_observation_ids: tuple[str, ...] = (),
    selected_json_admission_ids: tuple[str, ...] = (),
) -> HttpResponse:
    batches = Paginator(
        ImportBatch.objects.filter(patient=patient).prefetch_related("records"),
        IMPORTS_PER_PAGE,
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "interoperability/home.html",
        {
            "patient": patient,
            "batches": batches,
            "admissions": Admission.objects.filter(patient=patient),
            "prescriptions": Prescription.objects.filter(
                patient=patient
            ).select_related("prescriber"),
            "export_error": export_error,
            "selected_admission_ids": selected_admission_ids,
            "selected_prescription_ids": selected_prescription_ids,
            "service_requests": ImportedServiceRequest.objects.filter(
                patient=patient
            ).select_related("requester"),
            "medication_requests": ImportedMedicationRequest.objects.filter(
                patient=patient
            ).select_related("requester"),
            "json_observations": ExternalClinicalRecord.objects.filter(
                patient=patient,
                resource_type="Observation",
                content__resourceType="Observation",
            ),
            "json_export_error": json_export_error,
            "selected_service_request_ids": selected_service_request_ids,
            "selected_medication_request_ids": selected_medication_request_ids,
            "selected_json_prescription_ids": selected_json_prescription_ids,
            "selected_observation_ids": selected_observation_ids,
            "selected_json_admission_ids": selected_json_admission_ids,
        },
        status=status_code,
    )


@medical_professional_required
@require_http_methods(["GET"])
def exchange_home(request: HttpRequest, patient_pk: int) -> HttpResponse:
    patient = _patient_or_404(patient_pk)
    return _render_exchange_home(request, patient)


@medical_professional_required
@require_http_methods(["GET", "POST"])
def import_upload(request: HttpRequest, patient_pk: int) -> HttpResponse:
    patient = _patient_or_404(patient_pk)
    initial: dict[str, object] = {"request_key": uuid4()}
    retry_identifier = request.GET.get("retry")
    if retry_identifier:
        retry = _batch_or_404(patient, retry_identifier)
        initial = {
            "request_key": retry.request_key,
            "source_system": retry.source_system,
        }
    form = ExternalImportForm(
        request.POST or None,
        request.FILES or None,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        try:
            result = import_external_bundle(
                actor=actor_context_from_user(request.user),
                patient=patient,
                request_key=form.cleaned_data["request_key"],
                source_system=form.cleaned_data["source_system"],
                xml=form.cleaned_data["file"].read(),
            )
        except ExternalImportError as error:
            form.add_error(None, str(error))
        except ImportConflictError as error:
            form.add_error(None, str(error))
        else:
            return redirect(
                "interoperability:import-detail",
                patient_pk=patient.pk,
                identifier=result.batch.identifier,
            )
    return render(
        request, "interoperability/import_form.html", {"patient": patient, "form": form}
    )


@medical_professional_required
@require_http_methods(["GET"])
def import_detail(
    request: HttpRequest, patient_pk: int, identifier: str
) -> HttpResponse:
    patient = _patient_or_404(patient_pk)
    return render(
        request,
        "interoperability/import_detail.html",
        {"patient": patient, "batch": _batch_or_404(patient, identifier)},
    )


@medical_professional_required
@require_http_methods(["GET"])
def import_xml(request: HttpRequest, patient_pk: int, identifier: str) -> FileResponse:
    patient = _patient_or_404(patient_pk)
    batch = _batch_or_404(patient, identifier)
    response = FileResponse(
        BytesIO(bytes(batch.raw_xml)),
        as_attachment=True,
        filename=f"import-{batch.identifier}.xml",
        content_type="application/fhir+xml; charset=utf-8",
    )
    response["Cache-Control"] = "no-store"
    return response


@medical_professional_required
@require_http_methods(["POST"])
def export_selected(
    request: HttpRequest, patient_pk: int
) -> FileResponse | HttpResponse:
    patient = _patient_or_404(patient_pk)
    admission_ids = tuple(request.POST.getlist("admission_ids"))
    prescription_ids = tuple(request.POST.getlist("prescription_ids"))
    serializer = ExportRequestSerializer(
        data={
            "admission_ids": admission_ids,
            "prescription_ids": prescription_ids,
        }
    )
    if not serializer.is_valid():
        messages = [
            str(message)
            for field_errors in serializer.errors.values()
            for message in field_errors
        ]
        return _render_exchange_home(
            request,
            patient,
            export_error=messages[0] if messages else "Select valid clinical records.",
            selected_admission_ids=admission_ids,
            selected_prescription_ids=prescription_ids,
            status_code=400,
        )
    try:
        xml = export_selected_records(patient=patient, **serializer.validated_data)
    except ExportSelectionError as error:
        return _render_exchange_home(
            request,
            patient,
            export_error=str(error),
            selected_admission_ids=admission_ids,
            selected_prescription_ids=prescription_ids,
            status_code=400,
        )
    response = FileResponse(
        BytesIO(xml),
        as_attachment=True,
        filename=f"clinical-export-{patient.clinical_record_number}.xml",
        content_type="application/fhir+xml; charset=utf-8",
    )
    response["Cache-Control"] = "no-store"
    return response


@medical_professional_required
@require_http_methods(["POST"])
def export_selected_json_file(
    request: HttpRequest, patient_pk: int
) -> FileResponse | HttpResponse:
    patient = _patient_or_404(patient_pk)
    selections = {
        "admission_ids": tuple(request.POST.getlist("json_admission_ids")),
        "service_request_ids": tuple(request.POST.getlist("service_request_ids")),
        "medication_request_ids": tuple(request.POST.getlist("medication_request_ids")),
        "prescription_ids": tuple(request.POST.getlist("json_prescription_ids")),
        "observation_ids": tuple(request.POST.getlist("observation_ids")),
    }
    serializer = JsonExportRequestSerializer(data=selections)
    error: str | None = None
    if serializer.is_valid():
        try:
            raw = export_selected_json(patient=patient, **serializer.validated_data)
        except JsonExportSelectionError as exc:
            error = str(exc)
        else:
            exporter = active_professional_for_actor(
                actor_context_from_user(request.user)
            )
            response = FileResponse(
                BytesIO(raw),
                as_attachment=True,
                filename=json_export_filename(
                    raw, student_last_name=exporter.last_name or ""
                ),
                content_type="application/fhir+json",
            )
            response["Cache-Control"] = "no-store"
            return response
    else:
        error = str(next(iter(serializer.errors.values()))[0])
    return _render_exchange_home(
        request,
        patient,
        json_export_error=error,
        selected_service_request_ids=selections["service_request_ids"],
        selected_medication_request_ids=selections["medication_request_ids"],
        selected_json_prescription_ids=selections["prescription_ids"],
        selected_observation_ids=selections["observation_ids"],
        status_code=400,
        selected_json_admission_ids=selections["admission_ids"],
    )


class ImportCollectionAPIView(GenericAPIView):
    permission_classes = [IsActiveMedicalProfessionalActor]
    serializer_class = ImportRequestSerializer

    def _patient(self, patient_pk: int) -> Patient:
        return _patient_or_404(patient_pk)

    @extend_schema(
        operation_id="external_import_history",
        description="Return external-import summaries in stable 20-item pages.",
        responses={200: ImportBatchPageSerializer},
    )
    def get(self, request: Request, patient_pk: int) -> Response:
        patient = self._patient(patient_pk)
        page = Paginator(
            ImportBatch.objects.filter(patient=patient).prefetch_related("records"),
            IMPORTS_PER_PAGE,
        ).get_page(request.query_params.get("page"))
        return Response(
            {
                "count": page.paginator.count,
                "next": page.next_page_number() if page.has_next() else None,
                "previous": page.previous_page_number()
                if page.has_previous()
                else None,
                "results": ImportBatchSerializer(page.object_list, many=True).data,
            }
        )

    @extend_schema(
        operation_id="external_import_issue",
        description=(
            "Validate and atomically import one bounded HelixHealth FHIR R4 XML "
            "collection Bundle. A same-file retry returns the original batch."
        ),
        request=ImportRequestSerializer,
        examples=[
            OpenApiExample(
                "FHIR import request",
                request_only=True,
                value={
                    "request_key": "6c593e85-6a93-4ef4-9bce-9a2ac049c877",
                    "source_system": "https://external.example/identifiers/institution",
                    "file": "independent-valid-observation.xml",
                },
            ),
            OpenApiExample(
                "FHIR import result",
                response_only=True,
                status_codes=["201"],
                value={
                    "identifier": "a81c7e6a-2b6f-4e53-91e7-f4e9d1746a46",
                    "received_at": "2026-09-22T12:00:00Z",
                    "source_system": "https://external.example/identifiers/institution",
                    "bundle_identifier": "external-bundle-001",
                    "summary": {"record_count": 1},
                    "records": [],
                    "original_file_url": "/clinical-records/api/patients/9/exchange/imports/a81c7e6a-2b6f-4e53-91e7-f4e9d1746a46/xml/",
                },
            ),
        ],
        responses={
            200: ImportBatchSerializer,
            201: ImportBatchSerializer,
            400: OpenApiResponse(
                description="Unsafe, malformed, unsupported, or wrong-patient XML."
            ),
            409: OpenApiResponse(
                description="A retry key or external source identifier conflicts."
            ),
            415: OpenApiResponse(
                description="The uploaded file is not application/fhir+xml."
            ),
        },
    )
    def post(self, request: Request, patient_pk: int) -> Response:
        patient = self._patient(patient_pk)
        uploaded_file = request.FILES.get("file")
        if uploaded_file is not None:
            content_type = (uploaded_file.content_type or "").split(";", 1)[0]
            if content_type != "application/fhir+xml":
                return Response(
                    {"file": ["Upload an application/fhir+xml file."]},
                    status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded = serializer.validated_data["file"]
        try:
            result = import_external_bundle(
                actor=actor_context_from_user(request.user),
                patient=patient,
                request_key=serializer.validated_data["request_key"],
                source_system=serializer.validated_data["source_system"],
                xml=uploaded.read(),
            )
        except ExternalImportError as error:
            return Response({"file": [str(error)]}, status=status.HTTP_400_BAD_REQUEST)
        except ImportConflictError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        return Response(
            ImportBatchSerializer(result.batch).data,
            status=status.HTTP_201_CREATED if result.created else status.HTTP_200_OK,
        )


class ImportDetailAPIView(GenericAPIView):
    permission_classes = [IsActiveMedicalProfessionalActor]
    serializer_class = ImportBatchSerializer

    @extend_schema(operation_id="external_import_detail")
    def get(self, request: Request, patient_pk: int, identifier: str) -> Response:
        return Response(
            ImportBatchSerializer(
                _batch_or_404(_patient_or_404(patient_pk), identifier)
            ).data
        )


class ImportXmlAPIView(GenericAPIView):
    """Serve the protected original bytes through the documented API URL."""

    permission_classes = [IsActiveMedicalProfessionalActor]

    @extend_schema(
        description=(
            "Download the protected original imported file as UTF-8 "
            "application/fhir+xml."
        ),
        responses={(200, "application/fhir+xml"): OpenApiTypes.BINARY},
    )
    def get(self, request: Request, patient_pk: int, identifier: str) -> FileResponse:
        return import_xml(request._request, patient_pk, identifier)


class ExportAPIView(GenericAPIView):
    permission_classes = [IsActiveMedicalProfessionalActor]
    serializer_class = ExportRequestSerializer

    @extend_schema(
        operation_id="external_clinical_record_export",
        description=(
            "Export selected local admissions or one issued prescription as a "
            "self-contained FHIR R4 XML collection Bundle; this creates no records."
        ),
        request=ExportRequestSerializer,
        examples=[
            OpenApiExample(
                "Admission export request",
                request_only=True,
                value={"admission_ids": [42], "prescription_ids": []},
            )
        ],
        responses={
            (200, "application/fhir+xml"): OpenApiTypes.BINARY,
            400: OpenApiResponse(
                description="Empty, oversized, duplicate, or mixed selection."
            ),
            404: OpenApiResponse(
                description="The active patient or selected record was not found."
            ),
        },
    )
    def post(self, request: Request, patient_pk: int) -> FileResponse | Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            xml = export_selected_records(
                patient=_patient_or_404(patient_pk), **serializer.validated_data
            )
        except Http404:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except ExportSelectionError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        response = FileResponse(
            BytesIO(xml),
            as_attachment=True,
            filename="clinical-export.xml",
            content_type="application/fhir+xml; charset=utf-8",
        )
        response["Cache-Control"] = "no-store"
        return response


class JsonExportAPIView(GenericAPIView):
    permission_classes = [IsActiveMedicalProfessionalActor]
    serializer_class = JsonExportRequestSerializer

    @extend_schema(
        operation_id="fhir_json_export",
        description=(
            "Export patient-owned ServiceRequests with medication requests, or local admission "
            "and imported vital-sign Observations, optionally alongside medication requests, "
            "as one FHIR R4 JSON Bundle. All selected records must have the same practitioner."
        ),
        request=JsonExportRequestSerializer,
        responses={
            (200, "application/fhir+json"): OpenApiTypes.BINARY,
            400: OpenApiResponse(description="Incomplete or incompatible selection."),
            404: OpenApiResponse(
                description="A selected resource is not owned by this patient."
            ),
        },
    )
    def post(self, request: Request, patient_pk: int) -> FileResponse | Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            raw = export_selected_json(
                patient=_patient_or_404(patient_pk), **serializer.validated_data
            )
        except JsonExportSelectionError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        exporter = active_professional_for_actor(actor_context_from_user(request.user))
        response = FileResponse(
            BytesIO(raw),
            as_attachment=True,
            filename=json_export_filename(
                raw, student_last_name=exporter.last_name or ""
            ),
            content_type="application/fhir+json",
        )
        response["Cache-Control"] = "no-store"
        return response
