from django.urls import path

from interoperability import views

app_name = "interoperability"

urlpatterns = [
    path(
        "patients/<int:patient_pk>/interoperability/", views.exchange_home, name="home"
    ),
    path(
        "patients/<int:patient_pk>/interoperability/import/",
        views.import_upload,
        name="import-upload",
    ),
    path(
        "patients/<int:patient_pk>/interoperability/export/",
        views.export_selected,
        name="export",
    ),
    path(
        "patients/<int:patient_pk>/interoperability/imports/<uuid:identifier>/",
        views.import_detail,
        name="import-detail",
    ),
    path(
        "patients/<int:patient_pk>/interoperability/imports/<uuid:identifier>/xml/",
        views.import_xml,
        name="import-xml",
    ),
    path(
        "api/patients/<int:patient_pk>/exchange/imports/",
        views.ImportCollectionAPIView.as_view(),
        name="api-imports",
    ),
    path(
        "api/patients/<int:patient_pk>/exchange/imports/<uuid:identifier>/",
        views.ImportDetailAPIView.as_view(),
        name="api-import-detail",
    ),
    path(
        "api/patients/<int:patient_pk>/exchange/imports/<uuid:identifier>/xml/",
        views.ImportXmlAPIView.as_view(),
        name="api-import-xml",
    ),
    path(
        "api/patients/<int:patient_pk>/exchange/export/",
        views.ExportAPIView.as_view(),
        name="api-export",
    ),
]
