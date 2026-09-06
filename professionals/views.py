from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from access_control.actors import actor_context_from_user
from access_control.medical_professionals import has_active_medical_professional_context
from patients.views import administrative_required, is_htmx
from professionals.forms import (
    ProfessionalConfirmationForm,
    ProfessionalRegistrationForm,
    ProfessionalSearchForm,
)
from professionals.models import Professional
from professionals.services import (
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
            update_professional(
                actor=actor_context_from_user(request.user),
                professional=professional,
                changes=form.cleaned_data,
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
