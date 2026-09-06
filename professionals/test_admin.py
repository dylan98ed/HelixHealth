import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model

from professionals.admin import ProfessionalAdmin
from professionals.models import Professional


@pytest.mark.django_db
def test_professional_admin_is_view_only_even_for_a_superuser(rf):
    superuser = get_user_model().objects.create_superuser(
        username="administrator",
        password="test-pass",
        email="administrator@example.test",
    )
    professional = Professional.objects.create(
        user=get_user_model().objects.create_user(
            username="professional", password="test-pass"
        )
    )
    professional_admin = ProfessionalAdmin(Professional, admin.site)
    request = rf.get("/admin/professionals/professional/")
    request.user = superuser

    assert not professional_admin.has_add_permission(request)
    assert not professional_admin.has_change_permission(request, professional)
    assert not professional_admin.has_delete_permission(request, professional)
    assert set(professional_admin.readonly_fields) == {
        "id",
        "user",
        "is_active",
        "dni",
        "registration_number",
        "first_name",
        "last_name",
        "date_of_birth",
        "specialty",
        "hospital_service",
        "registration_completed_at",
    }
