from collections.abc import Callable
from functools import wraps
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from access_control.actors import actor_context_from_user
from access_control.medical_professionals import IsActiveMedicalProfessionalActor
from access_control.policies import (
    MEDICAL_PROFESSIONAL_POLICY,
)
from clinical_records.forms import AdmissionForm, PatientAdmissionSearchForm
from clinical_records.models import Admission
from clinical_records.serializers import (
    AdmissionCreateSerializer,
    AdmissionDetailSerializer,
)
from clinical_records.services import (
    InactivePatientError,
    active_professional_for_actor,
    create_admission,
    lookup_active_patient_for_admission,
)
from patients.models import Patient

PATIENTS_PER_PAGE = 20
ADMISSIONS_PER_PAGE = 20


def medical_professional_required(
    view_function: Callable[..., HttpResponse],
) -> Callable[..., HttpResponse]:
    @wraps(view_function)
    @login_required
    def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        actor = actor_context_from_user(request.user)
        if not MEDICAL_PROFESSIONAL_POLICY.allows(actor):
            raise PermissionDenied(
                "This operation requires a medical-professional actor."
            )
        active_professional_for_actor(actor)
        return view_function(request, *args, **kwargs)

    return wrapped


def is_htmx(request: HttpRequest) -> bool:
    return bool(getattr(request, "htmx", False))


def admission_search_context(
    request: HttpRequest,
    *,
    bind_empty_query: bool = False,
) -> dict[str, object]:
    query = request.GET if "dni" in request.GET or bind_empty_query else None
    form = PatientAdmissionSearchForm(query)
    patient = None
    if form.is_bound and form.is_valid():
        patient = lookup_active_patient_for_admission(
            actor=actor_context_from_user(request.user),
            dni=form.cleaned_data["dni"],
        )
    return {"form": form, "patient": patient}


@medical_professional_required
@require_http_methods(["GET"])
def clinical_workspace(request: HttpRequest) -> HttpResponse:
    active_patients = Paginator(Patient.objects.all(), PATIENTS_PER_PAGE).get_page(
        request.GET.get("page")
    )
    return render(
        request,
        "clinical_records/admission_search.html",
        {
            **admission_search_context(request),
            "active_patients": active_patients,
            "active_patients_page": active_patients,
        },
    )


@medical_professional_required
@require_http_methods(["GET"])
def admission_patient_search_results(request: HttpRequest) -> HttpResponse:
    context = admission_search_context(request, bind_empty_query=True)
    form = context["form"]
    assert isinstance(form, PatientAdmissionSearchForm)
    return render(
        request,
        "clinical_records/_admission_search_results.html",
        context,
        status=200 if form.is_valid() else 422,
    )


@medical_professional_required
@require_http_methods(["GET", "POST"])
def patient_admissions(request: HttpRequest, patient_pk: int) -> HttpResponse:
    patient = get_object_or_404(Patient.objects, pk=patient_pk)
    form = AdmissionForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            admission = create_admission(
                actor=actor_context_from_user(request.user),
                patient=patient,
                **form.cleaned_data,
            )
        except InactivePatientError as error:
            form.add_error(None, str(error))
        except ValidationError as error:
            for field_name, messages in error.message_dict.items():
                for message in messages:
                    form.add_error(field_name, message)
        else:
            if is_htmx(request):
                return render(
                    request,
                    "clinical_records/_admission_success.html",
                    {"admission": admission, "patient": patient},
                )
            return redirect(
                "clinical_records:patient-admissions",
                patient_pk=patient.pk,
            )

    admissions = Paginator(
        Admission.objects.filter(patient=patient).select_related("professional__user"),
        ADMISSIONS_PER_PAGE,
    ).get_page(request.GET.get("history_page"))
    context = {
        "patient": patient,
        "form": form,
        "admissions": admissions,
        "admissions_page": admissions,
    }
    if is_htmx(request) and request.method == "POST":
        return render(
            request,
            "clinical_records/_admission_form.html",
            context,
            status=422,
        )
    return render(request, "clinical_records/patient_admissions.html", context)


class AdmissionCreateAPIView(GenericAPIView):
    permission_classes = [IsActiveMedicalProfessionalActor]
    serializer_class = AdmissionCreateSerializer

    def get_patient(self, patient_pk: int) -> Patient:
        return get_object_or_404(Patient.objects, pk=patient_pk)

    @extend_schema(
        request=AdmissionCreateSerializer,
        responses={201: AdmissionDetailSerializer},
    )
    def post(self, request: Request, patient_pk: int) -> Response:
        patient = self.get_patient(patient_pk)
        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), "patient": patient},
        )
        serializer.is_valid(raise_exception=True)
        admission = serializer.save()
        return Response(
            AdmissionDetailSerializer(admission).data,
            status=status.HTTP_201_CREATED,
        )
