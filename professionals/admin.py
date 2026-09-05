from django.contrib import admin

from professionals.models import HospitalService, Professional, Specialty


@admin.register(Specialty, HospitalService)
class ActiveReferenceDataAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Professional)
class ProfessionalAdmin(admin.ModelAdmin):
    list_display = ("user", "is_active")
    list_filter = ("is_active",)
    search_fields = ("user__username", "user__first_name", "user__last_name")
