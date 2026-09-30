from django.urls import path

from catalogs import views

app_name = "catalogs"

urlpatterns = [
    path("", views.catalog_home, name="home"),
    path("specialties/", views.specialty_index, name="specialty-index"),
    path("specialties/new/", views.specialty_create, name="specialty-create"),
    path("specialties/<int:pk>/edit/", views.specialty_edit, name="specialty-edit"),
    path(
        "specialties/<int:pk>/delete/", views.specialty_delete, name="specialty-delete"
    ),
    path("terminology/", views.terminology_index, name="terminology-index"),
    path("terminology/new/", views.terminology_create, name="terminology-create"),
    path("terminology/import/", views.terminology_import, name="terminology-import"),
    path("medications/", views.medication_index, name="medication-index"),
    path("medications/new/", views.medication_create, name="medication-create"),
    path("medications/import/", views.medication_import, name="medication-import"),
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
        name="api-medication-import",
    ),
]
