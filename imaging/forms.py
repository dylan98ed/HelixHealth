from datetime import date
from pathlib import Path

from django import forms

from imaging.services import MAX_UPLOAD_BYTES


class ImageUploadForm(forms.Form):
    file = forms.FileField(label="JPG, PNG or DICOM file")
    birth_year = forms.IntegerField(
        label="Birth year", required=False, min_value=1850, max_value=date.today().year
    )
    study_year = forms.IntegerField(
        label="Study year", required=False, min_value=1850, max_value=date.today().year
    )
    sex = forms.ChoiceField(
        label="Sex",
        required=False,
        choices=(("", "Select sex"), ("M", "Male"), ("F", "Female"), ("O", "Other")),
    )

    def clean_file(self):
        upload = self.cleaned_data["file"]
        extension = Path(upload.name).suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".dcm", ".dicom"}:
            raise forms.ValidationError("Choose a JPG, PNG or DICOM file.")
        if upload.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("The file must be 32 MB or smaller.")
        return upload

    def clean(self):
        cleaned = super().clean() or {}
        upload = cleaned.get("file")
        if not upload:
            return cleaned
        extension = Path(upload.name).suffix.lower()
        if extension in {".jpg", ".jpeg", ".png"}:
            for field in ("birth_year", "study_year", "sex"):
                if not cleaned.get(field):
                    self.add_error(
                        field, "This field is required for JPG and PNG images."
                    )
            if cleaned.get("birth_year") and cleaned.get("study_year"):
                if cleaned["birth_year"] > cleaned["study_year"]:
                    self.add_error(
                        "study_year", "Study year cannot precede birth year."
                    )
        return cleaned
