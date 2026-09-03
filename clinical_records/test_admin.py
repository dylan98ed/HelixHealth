from django.contrib import admin

from clinical_records.admin import AdmissionAdmin
from clinical_records.models import Admission


def test_admission_admin_is_view_only(rf):
    admission_admin = AdmissionAdmin(Admission, admin.site)
    request = rf.get("/admin/clinical_records/admission/")

    assert not admission_admin.has_add_permission(request)
    assert not admission_admin.has_change_permission(request)
    assert not admission_admin.has_delete_permission(request)
    assert set(admission_admin.readonly_fields) == {
        "id",
        "patient",
        "professional",
        "consultation_reason",
        "systolic_blood_pressure",
        "diastolic_blood_pressure",
        "heart_rate",
        "temperature",
        "created_at",
    }
