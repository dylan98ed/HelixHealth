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
from clinical_records.views import medical_professional_required
from interoperability.exporting import ExportSelectionError, export_selected_records
from interoperability.forms import ExternalImportForm
from interoperability.importing import ExternalImportError
from interoperability.models import ImportBatch
from interoperability.serializers import (
    ExportRequestSerializer,
    ImportBatchPageSerializer,
    ImportBatchSerializer,
    ImportRequestSerializer,
)
from interoperability.services import ImportConflictError, import_external_bundle
from patients.models import Patient
from prescriptions.models import Prescription

IMPORTS_PER_PAGE = 20


def _patient_or_404(patient_pk: int) -> Patient:
    return get_object_or_404(Patient.objects, pk=patient_pk)


def _batch_or_404(patient: Patient, identifier: str) -> ImportBatch:
    try:
        return ImportBatch.objects.prefetch_related("records").get(
            patient=patient, identifier=identifier
        )
    except ImportBatch.DoesNotExist as error:
        raise Http404 from error


@medical_professional_required
@require_http_methods(["GET"])
def exchange_home(request: HttpRequest, patient_pk: int) -> HttpResponse:
    patient = _patient_or_404(patient_pk)
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
            "prescriptions": Prescription.objects.filter(patient=patient),
        },
    )


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
    serializer = ExportRequestSerializer(
        data={
            "admission_ids": request.POST.getlist("admission_ids"),
            "prescription_ids": request.POST.getlist("prescription_ids"),
        }
    )
    if not serializer.is_valid():
        return HttpResponse(str(serializer.errors), status=400)
    try:
        xml = export_selected_records(patient=patient, **serializer.validated_data)
    except ExportSelectionError as error:
        return HttpResponse(str(error), status=400)
    response = FileResponse(
        BytesIO(xml),
        as_attachment=True,
        filename=f"clinical-export-{patient.clinical_record_number}.xml",
        content_type="application/fhir+xml; charset=utf-8",
    )
    response["Cache-Control"] = "no-store"
    return response


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
