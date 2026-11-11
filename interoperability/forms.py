"""No-JavaScript external FHIR import form."""

from django import forms

from interoperability.importing import MAX_IMPORT_BYTES


class ExternalImportForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    source_system = forms.URLField(
        max_length=500, assume_scheme="https", label="Source organization system"
    )
    file = forms.FileField(label="FHIR XML file")

    def clean_file(self):
        value = self.cleaned_data["file"]
        content_type = (value.content_type or "").split(";", 1)[0]
        if content_type != "application/fhir+xml":
            raise forms.ValidationError("Upload an application/fhir+xml file.")
        if value.size > MAX_IMPORT_BYTES:
            raise forms.ValidationError("FHIR XML files may not exceed 2 MiB.")
        return value


class JsonImportForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    source_system = forms.URLField(
        max_length=500, assume_scheme="https", label="Source organization system"
    )
    file = forms.FileField(label="FHIR JSON file")

    def clean_file(self):
        value = self.cleaned_data["file"]
        if not value.name.lower().endswith(".json"):
            raise forms.ValidationError("Choose a .json file.")
        content_type = (value.content_type or "").split(";", 1)[0]
        if content_type not in {
            "application/fhir+json",
            "application/json",
            "application/octet-stream",
        }:
            raise forms.ValidationError("Upload a JSON file.")
        if not 0 < value.size <= MAX_IMPORT_BYTES:
            raise forms.ValidationError(
                "FHIR JSON files must be between 1 byte and 2 MiB."
            )
        return value
