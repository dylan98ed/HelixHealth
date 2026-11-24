from django.urls import path

from clinical_records import chart_views, documentation_views, views

app_name = "clinical_records"

urlpatterns = [
    path(
        "charts/<int:patient_pk>/sources/<str:kind>/<int:pk>/",
        chart_views.source_detail,
        name="timeline-source",
    ),
    path("charts/", chart_views.assigned_charts, name="assigned-charts"),
    path("charts/<int:patient_pk>/", chart_views.chart, name="chart"),
    path(
        "charts/<int:patient_pk>/admissions/<int:admission_pk>/",
        chart_views.chart_admission,
        name="chart-admission",
    ),
    path(
        "charts/<int:patient_pk>/consultations/new/",
        documentation_views.new_consultation,
        name="new-consultation",
    ),
    path(
        "charts/<int:patient_pk>/consultations/<int:consultation_pk>/",
        documentation_views.consultation_detail,
        name="consultation",
    ),
    path(
        "charts/<int:patient_pk>/history/<str:category>/new/",
        documentation_views.history_form,
        name="new-history",
    ),
    path(
        "charts/<int:patient_pk>/history/<str:category>/<int:entry_pk>/",
        documentation_views.history_form,
        name="edit-history",
    ),
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
