"""Read-only views of clinical requests received from other systems."""

from django.core.paginator import Paginator
from django.http import HttpRequest

from interoperability.models import ImportedMedicationRequest, ImportedServiceRequest
from patients.models import Patient


def imported_request_history(
    request: HttpRequest, patient: Patient
) -> dict[str, object]:
    return {
        "imported_services": Paginator(
            ImportedServiceRequest.objects.filter(patient=patient).select_related(
                "requester"
            ),
            20,
        ).get_page(request.GET.get("services_page")),
        "imported_medications": Paginator(
            ImportedMedicationRequest.objects.filter(patient=patient).select_related(
                "requester"
            ),
            20,
        ).get_page(request.GET.get("medications_page")),
    }
