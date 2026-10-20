from django.urls import path

from imaging import views

app_name = "imaging"

urlpatterns = [
    path("patients/<int:patient_pk>/images/", views.image_list, name="list"),
    path(
        "patients/<int:patient_pk>/images/<int:image_pk>/download/",
        views.download_image,
        name="download",
    ),
]
