import calendar

from django import forms

from appointments.models import BookingRequest
from patients.models import Patient
from professionals.models import Professional, Specialty


class DayInput(forms.DateInput):
    input_type = "date"


class ClockInput(forms.TimeInput):
    input_type = "time"


class SchedulingForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label_suffix = ""


class WeeklyForm(SchedulingForm):
    opens = forms.TimeField(label="Opening time", widget=ClockInput)
    closes = forms.TimeField(label="Closing time", widget=ClockInput)
    minutes = forms.IntegerField(
        label="Slot duration (minutes)", min_value=1, max_value=1440
    )
    effective_from = forms.DateField(label="Effective from", widget=DayInput)
    effective_until = forms.DateField(
        label="Effective through", widget=DayInput, required=False
    )

    def clean(self):
        data = self.cleaned_data
        if data.get("opens") and data.get("closes") and data["opens"] >= data["closes"]:
            self.add_error("closes", "Closing time must be after opening time.")
        if (
            data.get("effective_from")
            and data.get("effective_until")
            and data["effective_from"] > data["effective_until"]
        ):
            self.add_error(
                "effective_until", "The end date must be on or after the start date."
            )
        return data


class AddWeeklyForm(WeeklyForm):
    weekday = forms.TypedMultipleChoiceField(
        label="Weekdays",
        choices=list(enumerate(calendar.day_name)),
        coerce=int,
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Select at least one weekday."},
    )
    field_order = ["weekday"]


class EditWeeklyForm(WeeklyForm):
    weekday = forms.TypedChoiceField(
        choices=list(enumerate(calendar.day_name)), coerce=int
    )
    field_order = ["weekday"]


class ExceptionForm(SchedulingForm):
    day = forms.DateField(label="Exception date", widget=DayInput)
    mode = forms.ChoiceField(
        choices=[("closed", "Closed all day"), ("replace", "Replacement hours")]
    )
    opens = forms.TimeField(
        label="Replacement opening time", required=False, widget=ClockInput
    )
    closes = forms.TimeField(
        label="Replacement closing time", required=False, widget=ClockInput
    )
    minutes = forms.IntegerField(
        label="Replacement duration (minutes)",
        required=False,
        min_value=1,
        max_value=1440,
    )

    def clean(self):
        data = self.cleaned_data
        if data.get("mode") == "replace":
            for field in ("opens", "closes", "minutes"):
                if data.get(field) is None:
                    self.add_error(field, "Required for replacement hours.")
            if (
                data.get("opens")
                and data.get("closes")
                and data["opens"] >= data["closes"]
            ):
                self.add_error("closes", "Closing time must be after opening time.")
        else:
            data.update(opens=None, closes=None, minutes=None)
        return data


class AgendaFilter(SchedulingForm):
    day = forms.DateField(label="Date", widget=DayInput)
    professional = forms.ModelChoiceField(
        queryset=Professional.objects.filter(
            registration_completed_at__isnull=False
        ).order_by("last_name", "first_name", "pk"),
        required=False,
        empty_label="All professionals",
    )


class SlotFilter(SchedulingForm):
    specialty = forms.ModelChoiceField(
        queryset=Specialty.objects.filter(is_active=True)
    )


class IdentityForm(SchedulingForm):
    dni = forms.CharField(label="Patient DNI", max_length=18)


class ReservationForm(SchedulingForm):
    birth_date = forms.DateField(
        label="Patient-supplied date of birth", widget=DayInput
    )
    status = forms.ChoiceField(
        choices=[("confirmed", "Confirmed"), ("pending", "Pending")]
    )
    identity = forms.CharField(widget=forms.HiddenInput)
    token = forms.UUIDField(widget=forms.HiddenInput)


class RequestForm(SchedulingForm):
    patient = forms.ModelChoiceField(
        queryset=Patient.objects.order_by("last_name", "first_name", "pk"),
        empty_label="Select a patient",
    )
    channel = forms.ChoiceField(
        label="Original channel", choices=BookingRequest.Channel.choices
    )
    contact = forms.CharField(label="Contact number", max_length=254)
    preference = forms.CharField(
        label="Appointment preference",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    token = forms.UUIDField(widget=forms.HiddenInput)


class ContactForm(SchedulingForm):
    token = forms.UUIDField(widget=forms.HiddenInput)


class BookingActionForm(ContactForm):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class ConfirmForm(BookingActionForm):
    dni = forms.CharField(label="Patient-supplied DNI", max_length=18)
    birth_date = forms.DateField(
        label="Patient-supplied date of birth", widget=DayInput
    )


class RequestReservationForm(ContactForm):
    patient = forms.ChoiceField(label="Patient")
    status = forms.ChoiceField(
        choices=[
            ("pending", "Pending confirmation"),
            ("confirmed", "Patient confirmed on original channel"),
        ]
    )

    def __init__(self, *args, patient, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["patient"].choices = [(patient.pk, str(patient))]
        self.initial["patient"] = patient.pk
