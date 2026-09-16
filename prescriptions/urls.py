from django.urls import path

from prescriptions import views

app_name = "prescriptions"

urlpatterns = [
    path(
        "patients/<int:patient_pk>/prescriptions/", views.prescription_list, name="list"
    ),
    path(
        "patients/<int:patient_pk>/prescriptions/new/",
        views.prescription_issue,
        name="issue",
    ),
    path(
        "patients/<int:patient_pk>/prescriptions/<uuid:identifier>/",
        views.prescription_detail,
        name="detail",
    ),
    path(
        "patients/<int:patient_pk>/prescriptions/<uuid:identifier>/report/",
        views.prescription_report,
        name="report",
    ),
    path(
        "patients/<int:patient_pk>/prescriptions/<uuid:identifier>/xml/",
        views.prescription_xml,
        name="xml",
    ),
    path(
        "api/patients/<int:patient_pk>/prescriptions/",
        views.PrescriptionCollectionAPIView.as_view(),
        name="api-list",
    ),
    path(
        "api/patients/<int:patient_pk>/prescriptions/<uuid:identifier>/",
        views.PrescriptionDetailAPIView.as_view(),
        name="api-detail",
    ),
    path(
        "api/patients/<int:patient_pk>/prescriptions/<uuid:identifier>/report/",
        views.prescription_report,
        name="api-report",
    ),
    path(
        "api/patients/<int:patient_pk>/prescriptions/<uuid:identifier>/xml/",
        views.prescription_xml,
        name="api-xml",
    ),
]
