from django import forms
from django.core.exceptions import ValidationError

from clinic.models import (
    Appointment,
    Consultation,
    MedicalHistoryEntry,
    NursingObservation,
)


class ClinicalPatientSearchForm(forms.Form):
    query = forms.CharField(
        label="Search clinical records",
        required=False,
        max_length=100,
        widget=forms.SearchInput(
            attrs={"placeholder": "Patient name or patient ID"},
        ),
    )

    def clean_query(self):
        query = self.cleaned_data.get("query", "").strip()
        if any(ord(character) < 32 or ord(character) == 127 for character in query):
            raise ValidationError("Search must not contain control characters.")
        return query


class ConsultationForm(forms.ModelForm):
    class Meta:
        model = Consultation
        fields = (
            "consultation_at",
            "appointment",
            "symptoms",
            "diagnosis",
            "treatment",
            "clinician_notes",
        )
        widgets = {
            "consultation_at": forms.DateTimeInput(
                attrs={"type": "datetime-local", "step": "1"},
                format="%Y-%m-%dT%H:%M:%S",
            ),
            "symptoms": forms.Textarea(attrs={"rows": 3}),
            "diagnosis": forms.Textarea(attrs={"rows": 3}),
            "treatment": forms.Textarea(attrs={"rows": 3}),
            "clinician_notes": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "consultation_at": "Consultation date and time",
            "appointment": "Related appointment (optional)",
            "symptoms": "Symptoms",
            "diagnosis": "Diagnosis",
            "treatment": "Treatment",
            "clinician_notes": "Clinician notes",
        }

    def __init__(self, *args, patient, clinician, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.patient = patient
        self.instance.clinician = clinician
        appointments = Appointment.objects.filter(
                patient=patient,
                clinician=clinician,
            ).exclude(status=Appointment.Status.CANCELLED)
        if self.instance.pk and self.instance.appointment_id:
            appointments = appointments | Appointment.objects.filter(
                pk=self.instance.appointment_id,
            )
        self.fields["appointment"].queryset = appointments.order_by("-appointment_at")
        self.fields["appointment"].empty_label = "No linked appointment"


class MedicalHistoryEntryForm(forms.ModelForm):
    class Meta:
        model = MedicalHistoryEntry
        fields = ("entry_text", "effective_date")
        widgets = {
            "entry_text": forms.Textarea(attrs={"rows": 5}),
            "effective_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "entry_text": "Medical history entry",
            "effective_date": "Effective date (optional)",
        }

    def __init__(self, *args, patient, author, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.patient = patient
        self.instance.author = author


class NursingObservationForm(forms.ModelForm):
    class Meta:
        model = NursingObservation
        fields = (
            "body_temperature_celsius",
            "pulse_rate_bpm",
            "systolic_blood_pressure_mm_hg",
            "diastolic_blood_pressure_mm_hg",
            "respiratory_rate_bpm",
            "weight_kg",
            "notes",
        )
        widgets = {
            "body_temperature_celsius": forms.NumberInput(
                attrs={"step": "0.1", "min": "0.1"}
            ),
            "pulse_rate_bpm": forms.NumberInput(attrs={"step": "1", "min": "1"}),
            "systolic_blood_pressure_mm_hg": forms.NumberInput(
                attrs={"step": "1", "min": "1"}
            ),
            "diastolic_blood_pressure_mm_hg": forms.NumberInput(
                attrs={"step": "1", "min": "1"}
            ),
            "respiratory_rate_bpm": forms.NumberInput(
                attrs={"step": "1", "min": "1"}
            ),
            "weight_kg": forms.NumberInput(
                attrs={"step": "0.01", "min": "0.01"}
            ),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "body_temperature_celsius": "Body temperature (°C)",
            "pulse_rate_bpm": "Pulse rate (beats/minute)",
            "systolic_blood_pressure_mm_hg": "Systolic blood pressure (mm Hg)",
            "diastolic_blood_pressure_mm_hg": "Diastolic blood pressure (mm Hg)",
            "respiratory_rate_bpm": "Respiratory rate (breaths/minute)",
            "weight_kg": "Weight (kg)",
            "notes": "Nursing notes (optional)",
        }

    def __init__(self, *args, appointment, recorded_by, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.appointment = appointment
        self.instance.recorded_by = recorded_by

    def clean(self):
        cleaned_data = super().clean()
        if any(self.errors):
            return cleaned_data

        systolic = cleaned_data.get("systolic_blood_pressure_mm_hg")
        diastolic = cleaned_data.get("diastolic_blood_pressure_mm_hg")
        if (systolic is None) != (diastolic is None):
            raise ValidationError(
                "Enter both systolic and diastolic blood pressure values."
            )
        measurements = (
            "body_temperature_celsius",
            "pulse_rate_bpm",
            "systolic_blood_pressure_mm_hg",
            "diastolic_blood_pressure_mm_hg",
            "respiratory_rate_bpm",
            "weight_kg",
        )
        if not any(cleaned_data.get(field) is not None for field in measurements):
            raise ValidationError("Enter at least one observation measurement.")
        return cleaned_data
