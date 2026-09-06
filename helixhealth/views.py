from typing import Any

from django.http import HttpRequest
from django.http.response import HttpResponseBase
from django.shortcuts import redirect
from django.views.generic import TemplateView

from access_control.medical_professionals import (
    has_active_medical_professional_context,
)


class HomeView(TemplateView):
    template_name = "home.html"

    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseBase:
        if has_active_medical_professional_context(
            request.user,
            provision_missing=True,
        ):
            return redirect("clinical_records:dashboard")
        return super().dispatch(request, *args, **kwargs)
