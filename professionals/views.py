from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from drf_spectacular.utils import extend_schema
from rest_framework import status as http_status
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from access_control.actors import actor_context_from_user
from access_control.medical_professionals import has_active_medical_professional_context
from access_control.policies import IsAdministrativeActor
from patients.views import administrative_required, is_htmx
from professionals.forms import (
    ProfessionalConfirmationForm,
    ProfessionalRegistrationForm,
    ProfessionalSearchForm,
)
from professionals.models import Professional
from professionals.serializers import (
    ProfessionalConfirmationSerializer,
    ProfessionalCreateSerializer,
    ProfessionalDetailSerializer,
    ProfessionalSearchQuerySerializer,
    ProfessionalSearchResponseSerializer,
    ProfessionalSearchResultSerializer,
    ProfessionalUpdateSerializer,
)
from professionals.services import (
    ConfirmationRequiredError,
    ProfessionalConflictError,
    deactivate_professional,
    lookup_professional_by_dni,
    professional_index_queryset,
    reactivate_professional,
    register_professional,
    update_professional,
)


def _profile(pk: int) -> Professional:
    return get_object_or_404(
        Professional.objects.select_related("user", "specialty", "hospital_service"),
        pk=pk,
    )


def _form_errors(
    form: ProfessionalRegistrationForm | ProfessionalConfirmationForm,
    error: ValidationError,
) -> None:
    for field, messages in getattr(
        error, "message_dict", {"__all__": error.messages}
    ).items():
        form.add_error(field if field in form.fields else None, messages)


@administrative_required
@require_http_methods(["GET"])
def professional_index(request: HttpRequest) -> HttpResponse:
    status = request.GET.get("status", "active")
    if status not in {"active", "inactive", "incomplete"}:
        status = "active"
    profiles = professional_index_queryset(
        actor=actor_context_from_user(request.user),
        status=status,
    )
    page = Paginator(profiles, 20).get_page(request.GET.get("page"))
    return render(
        request, "professionals/index.html", {"page_obj": page, "status": status}
    )


@administrative_required
@require_http_methods(["GET"])
def professional_search(request: HttpRequest) -> HttpResponse:
    form = ProfessionalSearchForm(request.GET if "dni" in request.GET else None)
    professional = None
    if form.is_bound and form.is_valid():
        professional = lookup_professional_by_dni(
            actor=actor_context_from_user(request.user),
            dni=form.cleaned_data["dni"],
        )
    fragment = (
        request.resolver_match is not None
        and request.resolver_match.url_name == "search-results"
    )
    return render(
        request,
        "professionals/_search_results.html"
        if fragment
        else "professionals/search.html",
        {"form": form, "professional": professional},
        status=422 if fragment and form.errors else 200,
    )


@administrative_required
@require_http_methods(["GET"])
def professional_detail(request: HttpRequest, pk: int) -> HttpResponse:
    professional = _profile(pk)
    return render(
        request,
        "professionals/detail.html",
        {
            "professional": professional,
            "clinically_eligible": has_active_medical_professional_context(
                professional.user
            ),
        },
    )


@administrative_required
@require_http_methods(["GET", "POST"])
def professional_registration(
    request: HttpRequest, pk: int | None = None
) -> HttpResponse:
    professional = _profile(pk) if pk is not None else None
    if professional is not None and professional.is_registration_complete:
        return redirect("professionals:detail", pk=professional.pk)
    form = ProfessionalRegistrationForm(
        request.POST if request.method == "POST" else None,
        professional=professional,
        initial={"dni": request.GET.get("dni", "")},
    )
    existing = None
    if request.method == "POST" and form.is_valid():
        try:
            saved = register_professional(
                actor=actor_context_from_user(request.user), **form.cleaned_data
            )
        except ProfessionalConflictError as error:
            field = error.field
            form.add_error(field, str(error))
            if error.existing_professional_id is not None:
                existing = Professional.objects.filter(
                    pk=error.existing_professional_id
                ).first()
        except ValidationError as error:
            _form_errors(form, error)
        else:
            if is_htmx(request):
                return render(
                    request,
                    "professionals/_registration_success.html",
                    {"professional": saved},
                )
            return redirect("professionals:detail", pk=saved.pk)
    context = {
        "form": form,
        "professional": professional,
        "existing_professional": existing,
        "heading": "Complete registration" if professional else "Register professional",
        "submit_label": "Complete registration"
        if professional
        else "Register professional",
    }
    fragment = request.method == "POST" and is_htmx(request)
    return render(
        request,
        "professionals/_form.html" if fragment else "professionals/form.html",
        context,
        status=422 if fragment else 200,
    )


@administrative_required
@require_http_methods(["GET", "POST"])
def professional_update(request: HttpRequest, pk: int) -> HttpResponse:
    professional = _profile(pk)
    if not professional.is_registration_complete:
        return redirect("professionals:complete", pk=pk)
    form = ProfessionalRegistrationForm(
        request.POST if request.method == "POST" else None,
        professional=professional,
        editing=True,
    )
    if request.method == "POST" and form.is_valid():
        try:
            changes = dict(form.cleaned_data)
            if changes.get("license_number") is None:
                changes.pop("license_number")
            update_professional(
                actor=actor_context_from_user(request.user),
                professional=professional,
                changes=changes,
            )
        except ValidationError as error:
            _form_errors(form, error)
        else:
            return redirect("professionals:detail", pk=pk)
    return render(
        request,
        "professionals/form.html",
        {
            "form": form,
            "professional": professional,
            "heading": "Edit professional",
            "submit_label": "Save changes",
            "ordinary_post": True,
        },
    )


@administrative_required
@require_http_methods(["GET", "POST"])
def professional_status(request: HttpRequest, pk: int) -> HttpResponse:
    professional = _profile(pk)
    assert request.resolver_match is not None
    reactivating = request.resolver_match.url_name == "reactivate"
    if reactivating and not professional.is_registration_complete:
        return redirect("professionals:complete", pk=pk)
    form = ProfessionalConfirmationForm(
        request.POST if request.method == "POST" else None
    )
    if request.method == "POST" and form.is_valid():
        operation = reactivate_professional if reactivating else deactivate_professional
        try:
            operation(
                actor=actor_context_from_user(request.user),
                professional=professional,
                confirmed=True,
            )
        except ValidationError as error:
            _form_errors(form, error)
        except ProfessionalConflictError as error:
            form.add_error(None, str(error))
        else:
            return redirect("professionals:detail", pk=pk)
    label = "Reactivate professional" if reactivating else "Deactivate professional"
    return render(
        request,
        "professionals/form.html",
        {
            "form": form,
            "professional": professional,
            "heading": label,
            "submit_label": label,
            "ordinary_post": True,
        },
    )


def _conflict_response(error: ProfessionalConflictError) -> Response:
    field = error.field or "non_field_errors"
    data: dict[str, object] = {field: [str(error)]}
    if error.existing_professional_id is not None:
        data["existing_professional_id"] = error.existing_professional_id
    return Response(data, status=http_status.HTTP_409_CONFLICT)


class ProfessionalCreateAPIView(GenericAPIView):
    permission_classes = [IsAdministrativeActor]
    serializer_class = ProfessionalCreateSerializer

    @extend_schema(
        responses={
            200: ProfessionalDetailSerializer,
            201: ProfessionalDetailSerializer,
        }
    )
    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        completes_existing_profile = Professional.objects.filter(
            user__username=serializer.validated_data["username"]
        ).exists()
        try:
            professional = serializer.save()
        except ProfessionalConflictError as error:
            return _conflict_response(error)
        return Response(
            ProfessionalDetailSerializer(professional).data,
            status=(
                http_status.HTTP_200_OK
                if completes_existing_profile
                else http_status.HTTP_201_CREATED
            ),
        )


class ProfessionalSearchAPIView(GenericAPIView):
    permission_classes = [IsAdministrativeActor]
    serializer_class = ProfessionalSearchQuerySerializer

    @extend_schema(
        parameters=[ProfessionalSearchQuerySerializer],
        responses={200: ProfessionalSearchResponseSerializer},
    )
    def get(self, request: Request) -> Response:
        query = self.get_serializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        professional = lookup_professional_by_dni(
            actor=actor_context_from_user(request.user),
            dni=query.validated_data["dni"],
        )
        results = (
            ProfessionalSearchResultSerializer([professional], many=True).data
            if professional is not None
            else []
        )
        return Response({"results": results})


class ProfessionalDetailUpdateAPIView(GenericAPIView):
    permission_classes = [IsAdministrativeActor]
    serializer_class = ProfessionalDetailSerializer

    def get_professional(self, pk: int) -> Professional:
        return get_object_or_404(
            Professional.objects.select_related(
                "user", "specialty", "hospital_service"
            ),
            pk=pk,
        )

    def get(self, request: Request, pk: int) -> Response:
        return Response(ProfessionalDetailSerializer(self.get_professional(pk)).data)

    @extend_schema(
        request=ProfessionalUpdateSerializer,
        responses=ProfessionalDetailSerializer,
    )
    def patch(self, request: Request, pk: int) -> Response:
        professional = self.get_professional(pk)
        serializer = ProfessionalUpdateSerializer(
            professional,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        professional = serializer.save()
        return Response(ProfessionalDetailSerializer(professional).data)


class ProfessionalStatusAPIView(GenericAPIView):
    permission_classes = [IsAdministrativeActor]
    serializer_class = ProfessionalConfirmationSerializer
    operation = ""

    @extend_schema(responses=ProfessionalDetailSerializer)
    def post(self, request: Request, pk: int) -> Response:
        professional = get_object_or_404(Professional.objects, pk=pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        operation = (
            reactivate_professional
            if self.operation == "reactivate"
            else deactivate_professional
        )
        try:
            professional = operation(
                actor=actor_context_from_user(request.user),
                professional=professional,
                confirmed=serializer.validated_data["confirm"],
            )
        except ConfirmationRequiredError as error:
            return Response(
                {"confirm": [str(error)]},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        except ProfessionalConflictError as error:
            return _conflict_response(error)
        except ValidationError as error:
            detail = getattr(
                error, "message_dict", {"non_field_errors": error.messages}
            )
            return Response(detail, status=http_status.HTTP_400_BAD_REQUEST)
        return Response(ProfessionalDetailSerializer(professional).data)
