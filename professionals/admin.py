from django.contrib import admin
from django.http import HttpRequest

from professionals.models import HospitalService, Professional, Specialty


@admin.register(Specialty, HospitalService)
class ActiveReferenceDataAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Professional)
class ProfessionalAdmin(admin.ModelAdmin):
    list_display = ("user", "registration_number", "is_active")
    list_filter = ("is_active",)
    search_fields = ("user__username", "user__first_name", "user__last_name")
    readonly_fields = (
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
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: Professional | None = None,
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: Professional | None = None,
    ) -> bool:
        return False
