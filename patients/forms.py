from django import forms

from patients.models import Patient
from patients.validators import validate_patient_dni

PATIENT_REGISTRATION_FIELDS = (
    "dni",
    "first_name",
    "last_name",
    "date_of_birth",
    "sex",
    "phone",
    "email",
    "address",
    "health_insurer",
)

PATIENT_MUTABLE_FIELDS = (
    "first_name",
    "last_name",
    "date_of_birth",
    "sex",
    "phone",
    "email",
    "address",
    "health_insurer",
)


class PatientRegistrationForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = PATIENT_REGISTRATION_FIELDS
        widgets = {"date_of_birth": forms.DateInput(attrs={"type": "date"})}


class PatientUpdateForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = PATIENT_MUTABLE_FIELDS
        widgets = {"date_of_birth": forms.DateInput(attrs={"type": "date"})}


class PatientSearchForm(forms.Form):
    dni = forms.CharField(
        label="DNI",
        max_length=8,
        validators=[validate_patient_dni],
    )
