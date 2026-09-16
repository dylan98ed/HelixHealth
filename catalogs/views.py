"""Session-authenticated catalog HTTP endpoints."""

from collections.abc import Callable
from functools import wraps
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from access_control.actors import actor_context_from_user
from access_control.policies import ADMINISTRATIVE_POLICY
from catalogs.forms import (
    CatalogImportForm,
    MedicationEntryForm,
    SpecialtyCreateForm,
    SpecialtyDeleteForm,
    SpecialtyEditForm,
    TerminologyEntryForm,
)
from catalogs.models import MedicationEntry, TerminologyEntry
from catalogs.serializers import (
    CatalogImportResultSerializer,
    CatalogImportSerializer,
    MedicationSerializer,
    SpecialtySerializer,
    TerminologySerializer,
)
from catalogs.services import (
    MAX_IMPORT_BYTES,
    CatalogConflictError,
    CatalogInputError,
    create_catalog_entry,
    create_specialty,
    delete_specialty,
    import_entries,
    require_administrative_actor,
    retire_specialty,
    update_specialty,
)
from clinical_records.services import active_professional_for_actor
from professionals.models import Specialty

CATALOGS_PER_PAGE = 20


def catalog_administrative_required(
    view_function: Callable[..., HttpResponse],
) -> Callable[..., HttpResponse]:
    """Gate HTML catalog maintenance to active, non-staff admin actors."""

    @wraps(view_function)
    @login_required
    def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            require_administrative_actor(actor_context_from_user(request.user))
        except (PermissionDenied, PermissionError) as error:
            raise PermissionDenied(
                "This operation requires an active administrative actor."
            ) from error
        return view_function(request, *args, **kwargs)

    return wrapped


def _form_validation_errors(form: Any, error: ValidationError) -> None:
    for field, messages in error.message_dict.items():
        target = field if field in form.fields else None
        for message in messages:
            form.add_error(target, message)


def _catalog_page(
    request: HttpRequest,
    *,
    entries: QuerySet[Any],
    search_fields: tuple[str, ...],
    heading: str,
    description: str,
    create_url: str,
    import_url: str,
    kind: str,
) -> HttpResponse:
    query = request.GET.get("search", "").strip()
    if query:
        search_query = Q()
        for field in search_fields:
            search_query |= Q(**{f"{field}__icontains": query})
        entries = entries.filter(search_query)
    page_obj = Paginator(entries, CATALOGS_PER_PAGE).get_page(request.GET.get("page"))
    return render(
        request,
        "catalogs/entry_index.html",
        {
            "page_obj": page_obj,
            "query": query,
            "heading": heading,
            "description": description,
            "create_url": create_url,
            "import_url": import_url,
            "kind": kind,
        },
    )


@catalog_administrative_required
@require_http_methods(["GET"])
def catalog_home(request: HttpRequest) -> HttpResponse:
    return render(request, "catalogs/home.html")


@catalog_administrative_required
@require_http_methods(["GET"])
def specialty_index(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("search", "").strip()
    specialties = Specialty.objects.all()
    if query:
        specialties = specialties.filter(
            Q(code__icontains=query) | Q(name__icontains=query)
        )
    page_obj = Paginator(
        specialties.order_by("name", "id"), CATALOGS_PER_PAGE
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "catalogs/specialty_index.html",
        {"page_obj": page_obj, "query": query},
    )


@catalog_administrative_required
@require_http_methods(["GET", "POST"])
def specialty_create(request: HttpRequest) -> HttpResponse:
    form = SpecialtyCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            create_specialty(
                actor=actor_context_from_user(request.user), **form.cleaned_data
            )
        except ValidationError as error:
            _form_validation_errors(form, error)
        except CatalogConflictError as error:
            form.add_error(None, str(error))
        else:
            return redirect("catalogs:specialty-index")
    return render(
        request,
        "catalogs/specialty_form.html",
        {"form": form, "heading": "Add specialty", "specialty": None},
    )


@catalog_administrative_required
@require_http_methods(["GET", "POST"])
def specialty_edit(request: HttpRequest, pk: int) -> HttpResponse:
    specialty = get_object_or_404(Specialty, pk=pk)
    form = SpecialtyEditForm(
        request.POST or None,
        initial={"name": specialty.name, "is_active": specialty.is_active},
    )
    if request.method == "POST" and form.is_valid():
        try:
            update_specialty(
                actor=actor_context_from_user(request.user),
                specialty=specialty,
                **form.cleaned_data,
            )
        except ValidationError as error:
            _form_validation_errors(form, error)
        except CatalogConflictError as error:
            form.add_error(None, str(error))
        else:
            return redirect("catalogs:specialty-index")
    return render(
        request,
        "catalogs/specialty_form.html",
        {"form": form, "heading": "Edit specialty", "specialty": specialty},
    )


@catalog_administrative_required
@require_http_methods(["GET", "POST"])
def specialty_delete(request: HttpRequest, pk: int) -> HttpResponse:
    specialty = get_object_or_404(Specialty, pk=pk)
    form = SpecialtyDeleteForm(request.POST or None)
    error_message = None
    if request.method == "POST" and form.is_valid():
        try:
            if request.POST.get("action") == "retire":
                retire_specialty(
                    actor=actor_context_from_user(request.user), specialty=specialty
                )
            else:
                delete_specialty(
                    actor=actor_context_from_user(request.user), specialty=specialty
                )
        except CatalogConflictError as error:
            error_message = str(error)
        else:
            return redirect("catalogs:specialty-index")
    return render(
        request,
        "catalogs/specialty_delete.html",
        {"specialty": specialty, "form": form, "error_message": error_message},
        status=409 if error_message else 200,
    )


@catalog_administrative_required
@require_http_methods(["GET"])
def terminology_index(request: HttpRequest) -> HttpResponse:
    return _catalog_page(
        request,
        entries=TerminologyEntry.objects.order_by("display", "id"),
        search_fields=("code", "display"),
        heading="Nomenclature",
        description="Append-only terminology entries retain their source and version.",
        create_url="catalogs:terminology-create",
        import_url="catalogs:terminology-import",
        kind="terminology",
    )


@catalog_administrative_required
@require_http_methods(["GET", "POST"])
def terminology_create(request: HttpRequest) -> HttpResponse:
    form = TerminologyEntryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            create_catalog_entry(
                actor=actor_context_from_user(request.user),
                model=TerminologyEntry,
                values=form.cleaned_data,
            )
        except ValidationError as error:
            _form_validation_errors(form, error)
        except CatalogConflictError as error:
            form.add_error(None, str(error))
        else:
            return redirect("catalogs:terminology-index")
    return render(
        request,
        "catalogs/entry_form.html",
        {"form": form, "heading": "Add nomenclature entry", "kind": "terminology"},
    )


@catalog_administrative_required
@require_http_methods(["GET"])
def medication_index(request: HttpRequest) -> HttpResponse:
    return _catalog_page(
        request,
        entries=MedicationEntry.objects.select_related("terminology_entry").order_by(
            "name", "id"
        ),
        search_fields=("code", "name"),
        heading="Medications",
        description="Append-only medication entries retain their source and version.",
        create_url="catalogs:medication-create",
        import_url="catalogs:medication-import",
        kind="medication",
    )


@catalog_administrative_required
@require_http_methods(["GET", "POST"])
def medication_create(request: HttpRequest) -> HttpResponse:
    form = MedicationEntryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        values = dict(form.cleaned_data)
        terminology = values.pop("terminology_entry")
        if terminology is not None:
            values["terminology_entry_id"] = terminology.pk
        try:
            create_catalog_entry(
                actor=actor_context_from_user(request.user),
                model=MedicationEntry,
                values=values,
            )
        except ValidationError as error:
            _form_validation_errors(form, error)
        except CatalogConflictError as error:
            form.add_error(None, str(error))
        else:
            return redirect("catalogs:medication-index")
    return render(
        request,
        "catalogs/entry_form.html",
        {"form": form, "heading": "Add medication entry", "kind": "medication"},
    )


def _import_catalog(
    request: HttpRequest,
    *,
    model: type[TerminologyEntry] | type[MedicationEntry],
    heading: str,
    back_url: str,
) -> HttpResponse:
    form = CatalogImportForm(request.POST or None, request.FILES or None)
    result = None
    row_errors = None
    if request.method == "POST" and form.is_valid():
        upload = form.cleaned_data["file"]
        if upload.size > MAX_IMPORT_BYTES:
            form.add_error("file", "The import must not exceed 2 MiB.")
        else:
            try:
                result = import_entries(
                    actor=actor_context_from_user(request.user),
                    model=model,
                    payload=upload.read(),
                )
            except CatalogInputError as error:
                row_errors = error.errors.get("entries")
                form.add_error("file", "The upload contains invalid rows.")
            except ValidationError as error:
                _form_validation_errors(form, error)
            except CatalogConflictError as error:
                form.add_error("file", str(error))
    return render(
        request,
        "catalogs/import_form.html",
        {
            "form": form,
            "heading": heading,
            "back_url": back_url,
            "result": result,
            "row_errors": row_errors,
        },
    )


@catalog_administrative_required
@require_http_methods(["GET", "POST"])
def terminology_import(request: HttpRequest) -> HttpResponse:
    return _import_catalog(
        request,
        model=TerminologyEntry,
        heading="Import nomenclature JSON",
        back_url="catalogs:terminology-index",
    )


@catalog_administrative_required
@require_http_methods(["GET", "POST"])
def medication_import(request: HttpRequest) -> HttpResponse:
    return _import_catalog(
        request,
        model=MedicationEntry,
        heading="Import medication JSON",
        back_url="catalogs:medication-index",
    )


class CatalogReadPermission(BasePermission):
    message = "This operation requires an administrative or active medical-professional actor."

    def has_permission(self, request: Request, view: APIView) -> bool:
        actor = actor_context_from_user(request.user)
        if ADMINISTRATIVE_POLICY.allows(actor):
            try:
                require_administrative_actor(actor)
            except (PermissionDenied, PermissionError):
                return False
            return True
        try:
            active_professional_for_actor(actor)
        except (PermissionDenied, PermissionError):
            return False
        return True


class CatalogWritePermission(BasePermission):
    message = "This operation requires an active administrative actor."

    def has_permission(self, request: Request, view: APIView) -> bool:
        try:
            require_administrative_actor(actor_context_from_user(request.user))
        except (PermissionDenied, PermissionError):
            return False
        return True


def _paged(
    queryset: QuerySet[Any], request: Request, serializer: Callable[..., Any]
) -> Response:
    page = Paginator(queryset, 20).get_page(request.query_params.get("page"))
    return Response(
        {
            "count": page.paginator.count,
            "next": page.next_page_number() if page.has_next() else None,
            "previous": page.previous_page_number() if page.has_previous() else None,
            "results": serializer(page.object_list, many=True).data,
        }
    )


@extend_schema_view(
    get=extend_schema(operation_id="catalogs_specialties_list"),
    post=extend_schema(operation_id="catalogs_specialties_create"),
)
class SpecialtyListAPIView(GenericAPIView):
    serializer_class = SpecialtySerializer

    def get_permissions(self) -> list[BasePermission]:
        permission = (
            CatalogWritePermission
            if self.request.method == "POST"
            else CatalogReadPermission
        )
        return [permission()]

    def get(self, request: Request) -> Response:
        query = request.query_params.get("search", "").strip()
        specialties = Specialty.objects.all()
        if query:
            specialties = specialties.filter(
                Q(code__icontains=query) | Q(name__icontains=query)
            )
        return _paged(specialties.order_by("name", "id"), request, SpecialtySerializer)

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            specialty = create_specialty(
                actor=actor_context_from_user(request.user),
                code=serializer.validated_data["code"],
                name=serializer.validated_data["name"],
            )
        except CatalogConflictError as error:
            return Response(
                {"non_field_errors": [str(error)]}, status=status.HTTP_409_CONFLICT
            )
        return Response(
            SpecialtySerializer(specialty).data, status=status.HTTP_201_CREATED
        )


@extend_schema_view(
    get=extend_schema(operation_id="catalogs_specialties_retrieve"),
    patch=extend_schema(operation_id="catalogs_specialties_partial_update"),
    delete=extend_schema(operation_id="catalogs_specialties_destroy"),
)
class SpecialtyDetailAPIView(GenericAPIView):
    serializer_class = SpecialtySerializer

    def get_permissions(self) -> list[BasePermission]:
        permission = (
            CatalogWritePermission
            if self.request.method in {"PATCH", "DELETE"}
            else CatalogReadPermission
        )
        return [permission()]

    def _specialty(self, pk: int) -> Specialty:
        try:
            return Specialty.objects.get(pk=pk)
        except Specialty.DoesNotExist as error:
            raise Http404 from error

    def get(self, request: Request, pk: int) -> Response:
        return Response(SpecialtySerializer(self._specialty(pk)).data)

    def patch(self, request: Request, pk: int) -> Response:
        specialty = self._specialty(pk)
        data = {
            "code": specialty.code,
            "name": specialty.name,
            "is_active": specialty.is_active,
        } | request.data
        if data["code"] != specialty.code:
            return Response({"code": ["This field is immutable."]}, status=400)
        serializer = SpecialtySerializer(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            saved = update_specialty(
                actor=actor_context_from_user(request.user),
                specialty=specialty,
                name=serializer.validated_data["name"],
                is_active=serializer.validated_data["is_active"],
            )
        except CatalogConflictError as error:
            return Response({"name": [str(error)]}, status=status.HTTP_409_CONFLICT)
        return Response(SpecialtySerializer(saved).data)

    def delete(self, request: Request, pk: int) -> Response:
        try:
            delete_specialty(
                actor=actor_context_from_user(request.user),
                specialty=self._specialty(pk),
            )
        except CatalogConflictError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CatalogListAPIView(GenericAPIView):
    model: type[TerminologyEntry] | type[MedicationEntry]
    serializer_class: type[MedicationSerializer] | type[TerminologySerializer]
    search_fields: tuple[str, ...] = ()

    def get_permissions(self) -> list[BasePermission]:
        permission = (
            CatalogWritePermission
            if self.request.method == "POST"
            else CatalogReadPermission
        )
        return [permission()]

    def get(self, request: Request) -> Response:
        query = request.query_params.get("search", "").strip()
        entries = self.model.objects.all()
        if query:
            search_query = Q()
            for field in self.search_fields:
                search_query |= Q(**{f"{field}__icontains": query})
            entries = entries.filter(search_query)
        return _paged(entries, request, self.serializer_class)

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        if "terminology_entry" in values:
            terminology = values.pop("terminology_entry")
            if terminology is not None:
                values["terminology_entry_id"] = terminology.pk
        try:
            entry, created = create_catalog_entry(
                actor=actor_context_from_user(request.user),
                model=self.model,
                values=values,
            )
        except ValidationError as error:
            return Response(error.message_dict, status=status.HTTP_400_BAD_REQUEST)
        except CatalogConflictError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        return Response(
            self.serializer_class(entry).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


@extend_schema_view(
    get=extend_schema(operation_id="catalogs_terminology_list"),
    post=extend_schema(operation_id="catalogs_terminology_create"),
)
class TerminologyListAPIView(CatalogListAPIView):
    model = TerminologyEntry
    serializer_class = TerminologySerializer
    search_fields = ("code", "display")


@extend_schema_view(
    get=extend_schema(operation_id="catalogs_medications_list"),
    post=extend_schema(operation_id="catalogs_medications_create"),
)
class MedicationListAPIView(CatalogListAPIView):
    model = MedicationEntry
    serializer_class = MedicationSerializer
    search_fields = ("code", "name")


class ImmutableDetailAPIView(GenericAPIView):
    model: type[TerminologyEntry] | type[MedicationEntry]
    serializer_class: type[MedicationSerializer] | type[TerminologySerializer]
    permission_classes = [CatalogReadPermission]

    def get(self, request: Request, pk: int) -> Response:
        try:
            return Response(self.serializer_class(self.model.objects.get(pk=pk)).data)
        except self.model.DoesNotExist as error:
            raise Http404 from error


@extend_schema_view(
    get=extend_schema(operation_id="catalogs_terminology_retrieve"),
)
class TerminologyDetailAPIView(ImmutableDetailAPIView):
    model = TerminologyEntry
    serializer_class = TerminologySerializer


@extend_schema_view(
    get=extend_schema(operation_id="catalogs_medications_retrieve"),
)
class MedicationDetailAPIView(ImmutableDetailAPIView):
    model = MedicationEntry
    serializer_class = MedicationSerializer


class CatalogImportAPIView(GenericAPIView):
    model: type[TerminologyEntry] | type[MedicationEntry]
    serializer_class = CatalogImportSerializer
    permission_classes = [CatalogWritePermission]

    @extend_schema(responses=CatalogImportResultSerializer)
    def post(self, request: Request) -> Response:
        content_type = request.content_type.partition(";")[0]
        if content_type != "application/json":
            return Response(status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        payload = request.body
        if len(payload) > MAX_IMPORT_BYTES:
            return Response(
                {"file": ["The import must not exceed 2 MiB."]},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        try:
            result = import_entries(
                actor=actor_context_from_user(request.user),
                model=self.model,
                payload=payload,
            )
        except CatalogInputError as error:
            return Response(error.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as error:
            return Response(error.message_dict, status=status.HTTP_400_BAD_REQUEST)
        except CatalogConflictError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        return Response({"created": result.created, "unchanged": result.unchanged})


@extend_schema_view(
    post=extend_schema(operation_id="catalogs_terminology_import"),
)
class TerminologyImportAPIView(CatalogImportAPIView):
    model = TerminologyEntry


@extend_schema_view(
    post=extend_schema(operation_id="catalogs_medications_import"),
)
class MedicationImportAPIView(CatalogImportAPIView):
    model = MedicationEntry
