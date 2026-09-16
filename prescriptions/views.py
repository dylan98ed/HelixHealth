"""Authenticated API and HTML endpoints for prescriptions."""

from __future__ import annotations

from uuid import uuid4

from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from access_control.actors import actor_context_from_user
from access_control.medical_professionals import IsActiveMedicalProfessionalActor
from clinical_records.views import medical_professional_required
from patients.models import Patient
from prescriptions.forms import PrescriptionHeaderForm, PrescriptionItemForm
from prescriptions.models import Prescription
from prescriptions.serializers import (
    PrescriptionIssueSerializer,
    PrescriptionSerializer,
)
from prescriptions.services import (
    PrescriptionConflictError,
    PrescriptionInputError,
    issue_prescription,
)

PRESCRIPTIONS_PER_PAGE = 20


def _patient_or_404(patient_pk: int) -> Patient:
    return get_object_or_404(Patient.objects, pk=patient_pk)


def _prescription_or_404(patient: Patient, identifier: str) -> Prescription:
    try:
        return Prescription.objects.prefetch_related("items").get(
            patient=patient, identifier=identifier
        )
    except Prescription.DoesNotExist as error:
        raise Http404 from error


@medical_professional_required
@require_http_methods(["GET"])
def prescription_list(request: HttpRequest, patient_pk: int) -> HttpResponse:
    patient = _patient_or_404(patient_pk)
    prescriptions = Paginator(
        Prescription.objects.filter(patient=patient).prefetch_related("items"),
        PRESCRIPTIONS_PER_PAGE,
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "prescriptions/list.html",
        {"patient": patient, "prescriptions": prescriptions},
    )


@medical_professional_required
@require_http_methods(["GET", "POST"])
def prescription_issue(request: HttpRequest, patient_pk: int) -> HttpResponse:
    patient = _patient_or_404(patient_pk)
    from django.forms import formset_factory

    ItemFormSet = formset_factory(PrescriptionItemForm, extra=3)
    initial = {"request_key": uuid4()}
    header = PrescriptionHeaderForm(request.POST or None, initial=initial)
    formset = ItemFormSet(request.POST or None, prefix="items")
    if request.method == "POST" and header.is_valid() and formset.is_valid():
        item_data = []
        for form in formset:
            values = form.cleaned_data
            if not values or values.get("medication_id") is None:
                continue
            item_data.append(
                {
                    "medication_id": values["medication_id"].pk,
                    "dose_value": values["dose_value"],
                    "dose_unit": values["dose_unit"],
                    "route": values["route"],
                    "frequency": values["frequency"],
                    "duration_days": values["duration_days"],
                    "instructions": values["instructions"],
                }
            )
        try:
            result = issue_prescription(
                actor=actor_context_from_user(request.user),
                patient=patient,
                request_key=header.cleaned_data["request_key"],
                reason_entry_id=(
                    header.cleaned_data["reason_entry_id"].pk
                    if header.cleaned_data["reason_entry_id"]
                    else None
                ),
                items=item_data,
            )
        except PrescriptionInputError as error:
            header.add_error(
                None,
                "; ".join(
                    message
                    for messages in error.message_dict.values()
                    for message in messages
                ),
            )
        except PrescriptionConflictError as error:
            header.add_error(None, str(error))
        else:
            return redirect(
                "prescriptions:detail",
                patient_pk=patient.pk,
                identifier=result.prescription.identifier,
            )
    return render(
        request,
        "prescriptions/issue.html",
        {
            "patient": patient,
            "header": header,
            "formset": formset,
        },
    )


@medical_professional_required
@require_http_methods(["GET"])
def prescription_detail(
    request: HttpRequest, patient_pk: int, identifier: str
) -> HttpResponse:
    patient = _patient_or_404(patient_pk)
    return render(
        request,
        "prescriptions/detail.html",
        {
            "patient": patient,
            "prescription": _prescription_or_404(patient, identifier),
        },
    )


@medical_professional_required
@require_http_methods(["GET"])
def prescription_report(
    request: HttpRequest, patient_pk: int, identifier: str
) -> HttpResponse:
    patient = _patient_or_404(patient_pk)
    return render(
        request,
        "prescriptions/report.html",
        {
            "patient": patient,
            "prescription": _prescription_or_404(patient, identifier),
        },
    )


@medical_professional_required
@require_http_methods(["GET"])
def prescription_xml(
    request: HttpRequest, patient_pk: int, identifier: str
) -> FileResponse:
    patient = _patient_or_404(patient_pk)
    prescription = _prescription_or_404(patient, identifier)
    response = FileResponse(
        __import__("io").BytesIO(bytes(prescription.fhir_xml)),
        as_attachment=True,
        filename=f"prescription-{prescription.identifier}.xml",
        content_type="application/fhir+xml; charset=utf-8",
    )
    response["Cache-Control"] = "no-store"
    return response


class PrescriptionCollectionAPIView(GenericAPIView):
    permission_classes = [IsActiveMedicalProfessionalActor]
    serializer_class = PrescriptionIssueSerializer

    def _patient(self, patient_pk: int) -> Patient:
        return _patient_or_404(patient_pk)

    @extend_schema(responses={200: PrescriptionSerializer(many=True)})
    def get(self, request: Request, patient_pk: int) -> Response:
        patient = self._patient(patient_pk)
        page = Paginator(
            Prescription.objects.filter(patient=patient).prefetch_related("items"), 20
        ).get_page(request.query_params.get("page"))
        return Response(
            {
                "count": page.paginator.count,
                "next": page.next_page_number() if page.has_next() else None,
                "previous": page.previous_page_number()
                if page.has_previous()
                else None,
                "results": PrescriptionSerializer(
                    page.object_list, many=True, context={"request": request}
                ).data,
            }
        )

    @extend_schema(
        request=PrescriptionIssueSerializer, responses={201: PrescriptionSerializer}
    )
    def post(self, request: Request, patient_pk: int) -> Response:
        patient = self._patient(patient_pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = issue_prescription(
                actor=actor_context_from_user(request.user),
                patient=patient,
                **serializer.validated_data,
            )
        except PrescriptionInputError as error:
            return Response(error.message_dict, status=status.HTTP_400_BAD_REQUEST)
        except PrescriptionConflictError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        return Response(
            PrescriptionSerializer(
                result.prescription, context={"request": request}
            ).data,
            status=status.HTTP_201_CREATED if result.created else status.HTTP_200_OK,
        )


class PrescriptionDetailAPIView(GenericAPIView):
    permission_classes = [IsActiveMedicalProfessionalActor]

    def get(self, request: Request, patient_pk: int, identifier: str) -> Response:
        prescription = _prescription_or_404(_patient_or_404(patient_pk), identifier)
        return Response(
            PrescriptionSerializer(prescription, context={"request": request}).data
        )
