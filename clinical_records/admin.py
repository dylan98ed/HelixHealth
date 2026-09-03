from django.contrib import admin
from django.http import HttpRequest

from clinical_records.models import Admission


@admin.register(Admission)
class AdmissionAdmin(admin.ModelAdmin):
    list_display = ("patient", "professional", "created_at")
    list_filter = ("created_at",)
    search_fields = (
        "patient__clinical_record_number",
        "professional__user__username",
    )
    readonly_fields = (
        "id",
        "patient",
        "professional",
        "consultation_reason",
        "systolic_blood_pressure",
        "diastolic_blood_pressure",
        "heart_rate",
        "temperature",
        "created_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: Admission | None = None,
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: Admission | None = None,
    ) -> bool:
        return False
