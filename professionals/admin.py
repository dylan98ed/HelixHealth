from django.contrib import admin

from professionals.models import HospitalService, Specialty


@admin.register(Specialty, HospitalService)
class ActiveReferenceDataAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
