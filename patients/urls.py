from django.urls import path

from patients import views

app_name = "patients"

urlpatterns = [
    path("register/", views.patient_registration, name="register"),
    path("<int:pk>/", views.patient_detail, name="detail"),
    path("<int:pk>/edit/", views.patient_update, name="update"),
    path("<int:pk>/deactivate/", views.patient_deactivate, name="deactivate"),
    path("api/", views.PatientCreateAPIView.as_view(), name="api-create"),
    path(
        "api/<int:pk>/",
        views.PatientDetailUpdateAPIView.as_view(),
        name="api-detail",
    ),
    path(
        "api/<int:pk>/deactivate/",
        views.PatientDeactivateAPIView.as_view(),
        name="api-deactivate",
    ),
]
