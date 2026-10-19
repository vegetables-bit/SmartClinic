from django import forms

from clinic.models import Appointment, Consultation, MedicalHistoryEntry


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
