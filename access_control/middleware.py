from collections.abc import Callable
from typing import cast

from django.contrib.auth.models import AbstractUser
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from access_control.medical_professionals import (
    has_active_medical_professional_context,
)


class MedicalProfessionalAdminRedirectMiddleware:
    """Move clinical-only staff accounts out of Django's empty admin index."""

    admin_index_path = "/admin/"

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path_info == self.admin_index_path and request.user.is_authenticated:
            user = cast(AbstractUser, request.user)
            if (
                not user.is_superuser
                and not user.get_all_permissions()
                and has_active_medical_professional_context(
                    user,
                    provision_missing=True,
                )
            ):
                return redirect("clinical_records:dashboard")

        return self.get_response(request)
