from django.contrib import admin

from patients.models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        "clinical_record_number",
        "dni",
        "last_name",
        "first_name",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = ("dni", "clinical_record_number", "last_name", "first_name")
    readonly_fields = ("clinical_record_number",)
