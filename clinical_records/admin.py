from django.contrib import admin

from clinical_records.models import Admission


@admin.register(Admission)
class AdmissionAdmin(admin.ModelAdmin):
    list_display = ("patient", "professional", "created_at")
    list_filter = ("created_at",)
    search_fields = (
        "patient__clinical_record_number",
        "professional__user__username",
    )
    readonly_fields = ("patient", "professional", "created_at")
