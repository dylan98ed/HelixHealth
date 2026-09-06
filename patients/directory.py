"""Shared patient-list presentation, called after each workspace authorizes access."""

from django import forms
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest

from patients.models import Patient


class PatientNameSearchForm(forms.Form):
    q = forms.CharField(
        label="Name or surname",
        required=False,
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "type": "search",
                "placeholder": "Start typing a first name or surname…",
                "autocomplete": "off",
                "class": "form-control",
                "aria-describedby": "name-search-help",
            }
        ),
    )


def patient_directory_context(request: HttpRequest) -> dict[str, object]:
    form = PatientNameSearchForm(request.GET)
    patients = Patient.objects.all()
    query = ""
    if form.is_valid():
        query = " ".join(form.cleaned_data["q"].split())
        for term in query.split():
            patients = patients.filter(
                Q(first_name__icontains=term) | Q(last_name__icontains=term)
            )
    else:
        patients = patients.none()
    page = Paginator(patients, 20).get_page(request.GET.get("page"))
    return {
        "name_form": form,
        "name_query": query,
        "active_patients": page,
        "active_patients_page": page,
        "directory_url": request.path,
    }
