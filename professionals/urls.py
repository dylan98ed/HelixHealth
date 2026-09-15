from django.urls import path

from professionals import views

app_name = "professionals"

urlpatterns = [
    path("", views.professional_index, name="index"),
    path("search/", views.professional_search, name="search"),
    path("search/results/", views.professional_search, name="search-results"),
    path("register/", views.professional_registration, name="register"),
    path("api/", views.ProfessionalCreateAPIView.as_view(), name="api-create"),
    path(
        "api/search/",
        views.ProfessionalSearchAPIView.as_view(),
        name="api-search",
    ),
    path(
        "api/<int:pk>/",
        views.ProfessionalDetailUpdateAPIView.as_view(),
        name="api-detail",
    ),
    path(
        "api/<int:pk>/deactivate/",
        views.ProfessionalStatusAPIView.as_view(operation="deactivate"),
        name="api-deactivate",
    ),
    path(
        "api/<int:pk>/reactivate/",
        views.ProfessionalStatusAPIView.as_view(operation="reactivate"),
        name="api-reactivate",
    ),
    path("<int:pk>/", views.professional_detail, name="detail"),
    path("<int:pk>/complete/", views.professional_registration, name="complete"),
    path("<int:pk>/edit/", views.professional_update, name="update"),
    path("<int:pk>/deactivate/", views.professional_status, name="deactivate"),
    path("<int:pk>/reactivate/", views.professional_status, name="reactivate"),
]
