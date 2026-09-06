from django.contrib.auth.views import LoginView
from django.urls import reverse

from access_control.actors import actor_context_from_user
from access_control.medical_professionals import (
    has_active_medical_professional_context,
)
from access_control.policies import ADMINISTRATIVE_POLICY


class ApplicationLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_success_url(self) -> str:
        has_active_professional_context = has_active_medical_professional_context(
            self.request.user,
            provision_missing=True,
        )
        requested_url = self.get_redirect_url()
        if requested_url:
            return requested_url

        actor = actor_context_from_user(self.request.user)
        if has_active_professional_context:
            return reverse("clinical_records:dashboard")
        if ADMINISTRATIVE_POLICY.allows(actor):
            return reverse("patients:search")
        return reverse("home")
