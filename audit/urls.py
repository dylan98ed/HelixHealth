from django.urls import path

from audit import views

app_name = "audit"
urlpatterns = [
    path("", views.review, name="review"),
    path(
        "patients/<int:patient_pk>/events/<int:event_pk>/", views.detail, name="detail"
    ),
    path("charts/<int:patient_pk>/", views.review, {"clinical": True}, name="chart"),
    path(
        "charts/<int:patient_pk>/events/<int:event_pk>/",
        views.detail,
        {"clinical": True},
        name="chart-detail",
    ),
]
