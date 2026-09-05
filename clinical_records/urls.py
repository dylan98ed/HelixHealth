from django.urls import path

from clinical_records import views

app_name = "clinical_records"

urlpatterns = [
    path("", views.clinical_workspace, name="dashboard"),
    path(
        "admissions/",
        views.clinical_workspace,
        name="admission-search",
    ),
    path(
        "admissions/search/",
        views.admission_patient_search_results,
        name="admission-search-results",
    ),
    path(
        "patients/<int:patient_pk>/admissions/",
        views.patient_admissions,
        name="patient-admissions",
    ),
    path(
        "api/patients/<int:patient_pk>/admissions/",
        views.AdmissionCreateAPIView.as_view(),
        name="api-create-admission",
    ),
]
