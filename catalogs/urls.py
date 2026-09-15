from django.urls import path

from catalogs import views

app_name = "catalogs"

urlpatterns = [
    path(
        "api/specialties/", views.SpecialtyListAPIView.as_view(), name="api-specialties"
    ),
    path(
        "api/specialties/<int:pk>/",
        views.SpecialtyDetailAPIView.as_view(),
        name="api-specialty-detail",
    ),
    path(
        "api/terminology/",
        views.TerminologyListAPIView.as_view(),
        name="api-terminology",
    ),
    path(
        "api/terminology/<int:pk>/",
        views.TerminologyDetailAPIView.as_view(),
        name="api-terminology-detail",
    ),
    path(
        "api/terminology/import/",
        views.TerminologyImportAPIView.as_view(),
        name="api-terminology-import",
    ),
    path(
        "api/medications/",
        views.MedicationListAPIView.as_view(),
        name="api-medications",
    ),
    path(
        "api/medications/<int:pk>/",
        views.MedicationDetailAPIView.as_view(),
        name="api-medication-detail",
    ),
    path(
        "api/medications/import/",
        views.MedicationImportAPIView.as_view(),
        name="api-medications-import",
    ),
]
