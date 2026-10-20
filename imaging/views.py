from pathlib import Path

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from access_control.actors import actor_context_from_user
from clinical_records.services import active_professional_for_actor
from clinical_records.views import medical_professional_required
from imaging.forms import ImageUploadForm
from imaging.models import AnonymizedImage
from imaging.services import ImageProcessingError, anonymize_dicom, convert_raster
from patients.models import Patient


@medical_professional_required
@require_http_methods(["GET", "POST"])
def image_list(request: HttpRequest, patient_pk: int) -> HttpResponse:
    patient = get_object_or_404(Patient.objects, pk=patient_pk)
    form = ImageUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        upload = form.cleaned_data["file"]
        extension = Path(upload.name).suffix.lower()
        source_format = {
            ".jpg": "JPEG",
            ".jpeg": "JPEG",
            ".png": "PNG",
            ".dcm": "DICOM",
            ".dicom": "DICOM",
        }[extension]
        try:
            data = upload.read()
            if source_format == "DICOM":
                output, birth_year, study_year, sex = anonymize_dicom(data)
            else:
                birth_year = form.cleaned_data["birth_year"]
                study_year = form.cleaned_data["study_year"]
                sex = form.cleaned_data["sex"]
                output = convert_raster(
                    data,
                    source_format=source_format,
                    birth_year=birth_year,
                    study_year=study_year,
                    sex=sex,
                )
        except ImageProcessingError as error:
            form.add_error("file", str(error))
        else:
            record = AnonymizedImage.objects.create(
                patient=patient,
                created_by=active_professional_for_actor(
                    actor_context_from_user(request.user)
                ),
                source_format=source_format,
                birth_year=birth_year,
                study_year=study_year,
                sex=sex,
                dicom_bytes=output,
            )
            messages.success(request, "DICOM saved to this patient record.")
            return redirect(
                f"{reverse('imaging:list', args=[patient.pk])}?created={record.pk}"
            )
    images = AnonymizedImage.objects.filter(patient=patient).select_related(
        "created_by"
    )
    created_pk = request.GET.get("created", "")
    created = images.filter(pk=created_pk).first() if created_pk.isdecimal() else None
    response = render(
        request,
        "imaging/list.html",
        {"patient": patient, "form": form, "images": images, "created": created},
        status=422 if request.method == "POST" else 200,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@require_http_methods(["GET"])
@medical_professional_required
def download_image(
    request: HttpRequest, patient_pk: int, image_pk: int
) -> HttpResponse:
    image = get_object_or_404(AnonymizedImage, pk=image_pk, patient_id=patient_pk)
    response = HttpResponse(image.dicom_bytes, content_type="application/dicom")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="anonymized-image-{image.pk}.dcm"'
    )
    response.headers["Cache-Control"] = "no-store"
    return response
