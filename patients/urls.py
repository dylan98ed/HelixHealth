from django.urls import path

from clinical_records import care_views
from patients import views

app_name = "patients"

urlpatterns = [
    path("search/", views.patient_search, name="search"),
    path("search/results/", views.patient_search_results, name="search-results"),
    path("register/", views.patient_registration, name="register"),
    path("<int:pk>/", views.patient_detail, name="detail"),
    path("<int:pk>/edit/", views.patient_update, name="update"),
    path("<int:pk>/deactivate/", views.patient_deactivate, name="deactivate"),
    path("<int:pk>/care-team/", care_views.care_team, name="care-team"),
    path(
        "<int:pk>/care-team/<int:relationship_pk>/revoke/",
        care_views.revoke_care,
        name="revoke-care",
    ),
    path("api/", views.PatientCreateAPIView.as_view(), name="api-create"),
    path("api/search/", views.PatientSearchAPIView.as_view(), name="api-search"),
    path(
        "api/<int:pk>/care-team/",
        care_views.CareTeamAPIView.as_view(),
        name="api-care-team",
    ),
    path(
        "api/<int:pk>/care-team/<int:relationship_pk>/revoke/",
        care_views.CareRevokeAPIView.as_view(),
        name="api-revoke-care",
    ),
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
