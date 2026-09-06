from django import forms

from clinical_records.models import Admission
from clinical_records.vital_signs import vital_sign_definitions
from patients.validators import validate_patient_dni

ADMISSION_INPUT_FIELDS = (
    "consultation_reason",
    "systolic_blood_pressure",
    "diastolic_blood_pressure",
    "heart_rate",
    "temperature",
)


class PatientAdmissionSearchForm(forms.Form):
    dni = forms.CharField(
        label="DNI",
        max_length=8,
        validators=[validate_patient_dni],
    )


class AdmissionForm(forms.ModelForm):
    class Meta:
        model = Admission
        fields = ADMISSION_INPUT_FIELDS
        widgets = {
            "consultation_reason": forms.Textarea(attrs={"rows": 3}),
            "temperature": forms.NumberInput(attrs={"step": "0.1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        definitions = vital_sign_definitions()
        for field_name, definition in definitions.items():
            field = self.fields[field_name]
            field.help_text = (
                f"Accepted range: {definition.minimum}–{definition.maximum} "
                f"{definition.unit}."
            )
            field.widget.attrs.update(
                {
                    "min": str(definition.minimum),
                    "max": str(definition.maximum),
                }
            )
