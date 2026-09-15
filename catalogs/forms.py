"""Server-rendered forms for reference catalog administration."""

from django import forms

from catalogs.models import TerminologyEntry


class SpecialtyCreateForm(forms.Form):
    code = forms.CharField(max_length=50)
    name = forms.CharField(max_length=100)


class SpecialtyEditForm(forms.Form):
    name = forms.CharField(max_length=100)
    is_active = forms.BooleanField(
        required=False, label="Available for new assignments"
    )


class SpecialtyDeleteForm(forms.Form):
    confirm = forms.BooleanField(
        label="I confirm I want to remove this unreferenced specialty."
    )


class TerminologyEntryForm(forms.Form):
    system = forms.URLField(label="System URI", max_length=500, assume_scheme="https")
    version = forms.CharField(max_length=100)
    code = forms.CharField(max_length=255)
    display = forms.CharField(max_length=500)
    source_label = forms.CharField(label="Source label", max_length=200)


class MedicationEntryForm(forms.Form):
    system = forms.URLField(label="System URI", max_length=500, assume_scheme="https")
    version = forms.CharField(max_length=100)
    code = forms.CharField(max_length=255)
    name = forms.CharField(max_length=500)
    presentation = forms.CharField(max_length=500)
    terminology_entry = forms.ModelChoiceField(
        label="Related terminology entry",
        queryset=TerminologyEntry.objects.order_by("display", "id"),
        required=False,
    )
    source_label = forms.CharField(label="Source label", max_length=200)


class CatalogImportForm(forms.Form):
    file = forms.FileField(
        label="Normalized JSON file",
        help_text="JSON with source_label and up to 500 entries (maximum 2 MiB).",
        widget=forms.ClearableFileInput(attrs={"accept": "application/json,.json"}),
    )
