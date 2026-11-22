from django.urls import path

from appointments import request_views, views

app_name = "appointments"
urlpatterns = [
    path("", views.agenda, name="agenda"),
    path("requests/", request_views.inbox, name="requests"),
    path("requests/new/", request_views.new_request, name="new-request"),
    path("requests/<int:pk>/", request_views.request_detail, name="request-detail"),
    path(
        "requests/<int:pk>/openings/", request_views.request_slots, name="request-slots"
    ),
    path(
        "requests/<int:pk>/reserve/",
        request_views.request_choice,
        name="request-choice",
    ),
    path("availability/", views.availability, name="availability"),
    path("openings/", views.slots, name="slots"),
    path("openings/choose/", views.choice, name="choice"),
    path("<int:booking_id>/move/", views.slots, name="move"),
    path("<int:booking_id>/cancel/", views.cancel, name="cancel"),
    path("<int:booking_id>/arrival/", views.arrival, name="arrival"),
    path("<int:booking_id>/absence/", views.absence, name="absence"),
]
