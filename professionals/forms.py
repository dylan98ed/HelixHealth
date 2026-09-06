from typing import Any

from django import forms
from django.db.models import Q

from professionals.models import HospitalService, Professional, Specialty
from professionals.validators import (
    canonicalize_professional_dni,
    validate_professional_date_of_birth,
    validate_professional_name,
)


class ProfessionalRegistrationForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        help_text="Use the existing login username supplied by your account administrator.",
    )
    dni = forms.CharField(label="DNI")
    first_name = forms.CharField(
        max_length=150, validators=[validate_professional_name]
    )
    last_name = forms.CharField(max_length=150, validators=[validate_professional_name])
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        validators=[validate_professional_date_of_birth],
    )
    specialty_code = forms.ModelChoiceField(
        label="Specialty", queryset=Specialty.objects.none(), to_field_name="code"
    )
    hospital_service_code = forms.ModelChoiceField(
        label="Hospital service",
        queryset=HospitalService.objects.none(),
        to_field_name="code",
    )

    def __init__(
        self,
        *args: Any,
        professional: Professional | None = None,
        editing: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        if professional is not None:
            self.initial.update(
                username=professional.user.get_username(),
                dni=professional.dni,
                first_name=professional.first_name,
                last_name=professional.last_name,
                date_of_birth=professional.date_of_birth,
                specialty_code=professional.specialty_id,
                hospital_service_code=professional.hospital_service_id,
            )
            self.fields["username"].disabled = True
        specialty = self.fields["specialty_code"]
        service = self.fields["hospital_service_code"]
        assert isinstance(specialty, forms.ModelChoiceField)
        assert isinstance(service, forms.ModelChoiceField)
        specialty_filter = Q(is_active=True)
        service_filter = Q(is_active=True)
        if editing and professional is not None:
            specialty_filter |= Q(pk=professional.specialty_id)
            service_filter |= Q(pk=professional.hospital_service_id)
            del self.fields["username"]
            del self.fields["dni"]
        specialty.queryset = Specialty.objects.filter(specialty_filter)
        service.queryset = HospitalService.objects.filter(service_filter)
        if professional is not None:
            self.initial["specialty_code"] = (
                professional.specialty.code if professional.specialty else None
            )
            self.initial["hospital_service_code"] = (
                professional.hospital_service.code
                if professional.hospital_service
                else None
            )

    def clean_dni(self) -> str:
        return canonicalize_professional_dni(self.cleaned_data["dni"])

    def clean_specialty_code(self) -> str:
        return str(self.cleaned_data["specialty_code"].code)

    def clean_hospital_service_code(self) -> str:
        return str(self.cleaned_data["hospital_service_code"].code)


class ProfessionalSearchForm(forms.Form):
    dni = forms.CharField(label="DNI")

    def clean_dni(self) -> str:
        return canonicalize_professional_dni(self.cleaned_data["dni"])


class ProfessionalConfirmationForm(forms.Form):
    confirm = forms.BooleanField(
        label="I confirm this change to the professional's status."
    )
