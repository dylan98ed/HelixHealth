from collections.abc import Callable
from functools import wraps
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from access_control.actors import actor_context_from_user
from access_control.policies import ADMINISTRATIVE_POLICY, IsAdministrativeActor
from clinical_records.models import Admission
from patients.forms import PatientRegistrationForm, PatientSearchForm, PatientUpdateForm
from patients.models import Patient
from patients.serializers import (
    PatientCreateSerializer,
    PatientDeactivateSerializer,
    PatientDetailSerializer,
    PatientSearchQuerySerializer,
    PatientSearchResponseSerializer,
    PatientSearchResultSerializer,
    PatientUpdateSerializer,
)
from patients.services import (
    DeactivationConfirmationRequiredError,
    DuplicateActivePatientDNIError,
    create_patient,
    deactivate_patient,
    lookup_active_patient_by_dni,
    update_patient,
)


def administrative_required(
    view_function: Callable[..., HttpResponse],
) -> Callable[..., HttpResponse]:
    @wraps(view_function)
    @login_required
    def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        actor = actor_context_from_user(request.user)
        if not ADMINISTRATIVE_POLICY.allows(actor):
            raise PermissionDenied("This operation requires an administrative actor.")
        return view_function(request, *args, **kwargs)

    return wrapped


def is_htmx(request: HttpRequest) -> bool:
    return bool(getattr(request, "htmx", False))


def patient_search_context(
    request: HttpRequest,
    *,
    bind_empty_query: bool = False,
) -> dict[str, object]:
    query = request.GET if request.GET or bind_empty_query else None
    form = PatientSearchForm(query)
    patient = None
    if form.is_bound and form.is_valid():
        patient = lookup_active_patient_by_dni(
            actor=actor_context_from_user(request.user),
            dni=form.cleaned_data["dni"],
        )
    return {"form": form, "patient": patient}


@administrative_required
@require_http_methods(["GET", "POST"])
def patient_registration(request: HttpRequest) -> HttpResponse:
    form = PatientRegistrationForm(
        request.POST or None,
        initial={"dni": request.GET.get("dni", "")},
    )
    existing_patient = None

    if request.method == "POST" and form.is_valid():
        actor = actor_context_from_user(request.user)
        try:
            patient = create_patient(actor=actor, **form.cleaned_data)
        except DuplicateActivePatientDNIError as error:
            existing_patient = error.patient
            form.add_error("dni", str(error))
        else:
            if is_htmx(request):
                return render(
                    request,
                    "patients/_registration_success.html",
                    {"patient": patient},
                )
            return redirect("patients:detail", pk=patient.pk)

    if request.method == "POST" and existing_patient is None:
        submitted_dni = request.POST.get("dni", "")
        existing_patient = Patient.objects.filter(dni=submitted_dni).first()

    context = {"form": form, "existing_patient": existing_patient}
    if is_htmx(request) and request.method == "POST":
        return render(
            request,
            "patients/_registration_form.html",
            context,
            status=422,
        )
    return render(request, "patients/registration.html", context)


@administrative_required
@require_http_methods(["GET"])
def patient_search(request: HttpRequest) -> HttpResponse:
    return render(request, "patients/search.html", patient_search_context(request))


@administrative_required
@require_http_methods(["GET"])
def patient_search_results(request: HttpRequest) -> HttpResponse:
    context = patient_search_context(request, bind_empty_query=True)
    form = context["form"]
    assert isinstance(form, PatientSearchForm)
    return render(
        request,
        "patients/_search_results.html",
        context,
        status=200 if form.is_valid() else 422,
    )


@administrative_required
@require_http_methods(["GET"])
def patient_detail(request: HttpRequest, pk: int) -> HttpResponse:
    patient = get_object_or_404(Patient.all_objects, pk=pk)
    admissions = Admission.objects.filter(patient=patient).select_related(
        "professional__user"
    )
    return render(
        request,
        "patients/detail.html",
        {"patient": patient, "admissions": admissions},
    )


@administrative_required
@require_http_methods(["GET", "POST"])
def patient_update(request: HttpRequest, pk: int) -> HttpResponse:
    patient = get_object_or_404(Patient.all_objects, pk=pk)
    form = PatientUpdateForm(request.POST or None, instance=patient)

    if request.method == "POST" and form.is_valid():
        actor = actor_context_from_user(request.user)
        try:
            patient = update_patient(
                actor=actor,
                patient=patient,
                changes={
                    field_name: form.cleaned_data[field_name]
                    for field_name in form.fields
                },
            )
        except ValidationError as error:
            for field_name, messages in error.message_dict.items():
                for message in messages:
                    form.add_error(field_name, message)
        else:
            return redirect("patients:detail", pk=patient.pk)

    return render(
        request,
        "patients/update.html",
        {"form": form, "patient": patient},
    )


@administrative_required
@require_http_methods(["GET", "POST"])
def patient_deactivate(request: HttpRequest, pk: int) -> HttpResponse:
    patient = get_object_or_404(Patient.all_objects, pk=pk)
    error_message = None

    if request.method == "POST":
        actor = actor_context_from_user(request.user)
        try:
            deactivate_patient(
                actor=actor,
                patient=patient,
                confirmed=request.POST.get("confirm") == "yes",
            )
        except DeactivationConfirmationRequiredError as error:
            error_message = str(error)
        else:
            return redirect("patients:detail", pk=patient.pk)

    return render(
        request,
        "patients/deactivate_confirm.html",
        {"patient": patient, "error_message": error_message},
        status=400 if error_message else 200,
    )


class PatientCreateAPIView(GenericAPIView):
    permission_classes = [IsAdministrativeActor]
    serializer_class = PatientCreateSerializer

    @extend_schema(responses={201: PatientDetailSerializer})
    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            patient = serializer.save()
        except DuplicateActivePatientDNIError as error:
            return Response(
                {
                    "dni": [str(error)],
                    "existing_patient_id": error.patient.pk,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            PatientDetailSerializer(patient).data,
            status=status.HTTP_201_CREATED,
        )


class PatientSearchAPIView(GenericAPIView):
    permission_classes = [IsAdministrativeActor]
    serializer_class = PatientSearchQuerySerializer

    @extend_schema(
        parameters=[PatientSearchQuerySerializer],
        responses={200: PatientSearchResponseSerializer},
    )
    def get(self, request: Request) -> Response:
        query = self.get_serializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        patient = lookup_active_patient_by_dni(
            actor=actor_context_from_user(request.user),
            dni=query.validated_data["dni"],
        )
        results = (
            PatientSearchResultSerializer([patient], many=True).data
            if patient is not None
            else []
        )
        return Response({"results": results})


class PatientDetailUpdateAPIView(GenericAPIView):
    permission_classes = [IsAdministrativeActor]
    serializer_class = PatientDetailSerializer

    def get_patient(self, pk: int) -> Patient:
        return get_object_or_404(Patient.all_objects, pk=pk)

    def get(self, request: Request, pk: int) -> Response:
        return Response(PatientDetailSerializer(self.get_patient(pk)).data)

    @extend_schema(
        request=PatientUpdateSerializer,
        responses=PatientDetailSerializer,
    )
    def patch(self, request: Request, pk: int) -> Response:
        patient = self.get_patient(pk)
        serializer = PatientUpdateSerializer(
            patient,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        patient = serializer.save()
        return Response(PatientDetailSerializer(patient).data)


class PatientDeactivateAPIView(GenericAPIView):
    permission_classes = [IsAdministrativeActor]
    serializer_class = PatientDeactivateSerializer

    @extend_schema(responses=PatientDetailSerializer)
    def post(self, request: Request, pk: int) -> Response:
        patient = get_object_or_404(Patient.all_objects, pk=pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            deactivate_patient(
                actor=actor_context_from_user(request.user),
                patient=patient,
                confirmed=serializer.validated_data["confirm"],
            )
        except DeactivationConfirmationRequiredError as error:
            return Response(
                {"confirm": [str(error)]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(PatientDetailSerializer(patient).data)
