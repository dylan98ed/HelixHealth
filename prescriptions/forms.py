"""No-JavaScript HTML forms for prescription issuance."""

from django import forms

from catalogs.models import MedicationEntry, TerminologyEntry


class PrescriptionHeaderForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    reason_entry_id = forms.ModelChoiceField(
        queryset=TerminologyEntry.objects.none(), required=False, label="Reason"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        reason_field = self.fields["reason_entry_id"]
        assert isinstance(reason_field, forms.ModelChoiceField)
        reason_field.queryset = TerminologyEntry.objects.order_by("display", "id")


class PrescriptionItemForm(forms.Form):
    medication_id = forms.ModelChoiceField(
        queryset=MedicationEntry.objects.none(), required=False, label="Medication"
    )
    dose_value = forms.DecimalField(
        max_digits=12, decimal_places=4, required=False, min_value=0
    )
    dose_unit = forms.CharField(max_length=100, required=False)
    route = forms.CharField(max_length=100, required=False)
    frequency = forms.CharField(max_length=500, required=False)
    duration_days = forms.IntegerField(required=False, min_value=1, max_value=365)
    instructions = forms.CharField(
        max_length=2000, required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        medication_field = self.fields["medication_id"]
        assert isinstance(medication_field, forms.ModelChoiceField)
        medication_field.queryset = MedicationEntry.objects.order_by("name", "id")

    def clean(self):
        cleaned = super().clean() or {}
        values = [cleaned.get(name) for name in self.fields]
        if not any(value not in (None, "") for value in values):
            return cleaned
        required = (
            "medication_id",
            "dose_value",
            "dose_unit",
            "route",
            "frequency",
            "duration_days",
        )
        for name in required:
            if cleaned.get(name) in (None, ""):
                self.add_error(name, "This field is required for a medication item.")
        return cleaned
