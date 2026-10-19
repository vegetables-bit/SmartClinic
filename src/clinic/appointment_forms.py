import re
from datetime import datetime, timedelta

from django import forms
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from clinic.models import Appointment, Patient, StaffProfile


class AppointmentForm(forms.ModelForm):
    appointment_date = forms.DateField(
        label="Appointment date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    appointment_time = forms.TimeField(
        label="Start time",
        widget=forms.TimeInput(attrs={"type": "time"}),
    )

    class Meta:
        model = Appointment
        fields = ("patient", "clinician", "reason_for_visit")
        widgets = {"reason_for_visit": forms.Textarea(attrs={"rows": 3})}
        labels = {
            "patient": "Patient",
            "clinician": "Clinician",
            "reason_for_visit": "Reason for visit",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        patients = Patient.objects.filter(is_archived=False)
        clinicians = StaffProfile.objects.filter(
            role=StaffProfile.Role.CLINICIAN,
            is_active=True,
            account__is_active=True,
        ).select_related("account")
        if self.instance.pk:
            patients = Patient.objects.filter(pk=self.instance.patient_id) | patients
            clinicians = StaffProfile.objects.filter(
                pk=self.instance.clinician_id
            ) | clinicians
            local_start = timezone.localtime(self.instance.appointment_at)
            self.initial.setdefault("appointment_date", local_start.date())
            self.initial.setdefault("appointment_time", local_start.time())
        self.fields["patient"].queryset = patients.distinct()
        self.fields["clinician"].queryset = clinicians.distinct()

    def clean(self):
        cleaned_data = super().clean()
        appointment_date = cleaned_data.get("appointment_date")
        appointment_time = cleaned_data.get("appointment_time")
        patient = cleaned_data.get("patient")
        clinician = cleaned_data.get("clinician")
        reason = cleaned_data.get("reason_for_visit")

        if reason is not None and not reason.strip():
            self.add_error("reason_for_visit", "Enter a reason for the appointment.")

        if not (appointment_date and appointment_time and patient and clinician):
            return cleaned_data
        if not clinician.is_active or not clinician.account.is_active:
            self.add_error("clinician", "Select an active clinician.")
            return cleaned_data

        if self.instance.pk:
            duration = int(
                (self.instance.ends_at - self.instance.appointment_at).total_seconds()
                // 60
            )
        else:
            duration = getattr(settings, "APPOINTMENT_DEFAULT_DURATION_MINUTES", 30)
        if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
            raise ImproperlyConfigured(
                "APPOINTMENT_DEFAULT_DURATION_MINUTES must be a positive integer."
            )

        start = datetime.combine(appointment_date, appointment_time)
        if timezone.is_naive(start):
            start = timezone.make_aware(start, timezone.get_current_timezone())
        end = start + timedelta(minutes=duration)

        conflicts = Appointment.objects.select_for_update().filter(
            appointment_at__lt=end,
            ends_at__gt=start,
        ).exclude(status=Appointment.Status.CANCELLED)
        if self.instance.pk:
            conflicts = conflicts.exclude(pk=self.instance.pk)

        with transaction.atomic():
            patient_conflict = conflicts.filter(patient=patient).exists()
            clinician_conflict = conflicts.filter(clinician=clinician).exists()

        if patient_conflict:
            self.add_error(
                "patient",
                "This patient already has an appointment during that time.",
            )
        if clinician_conflict:
            self.add_error(
                "clinician",
                "This clinician already has an appointment during that time.",
            )

        cleaned_data["appointment_at"] = start
        cleaned_data["ends_at"] = end
        self.instance.appointment_at = start
        self.instance.ends_at = end
        return cleaned_data

    def save(self, commit=True):
        self.instance.appointment_at = self.cleaned_data["appointment_at"]
        self.instance.ends_at = self.cleaned_data["ends_at"]
        return super().save(commit=commit)


class AppointmentSearchForm(forms.Form):
    query = forms.CharField(
        label="Search",
        required=False,
        max_length=100,
        widget=forms.SearchInput(
            attrs={"placeholder": "Appointment ID, patient ID, or patient name"}
        ),
    )
    appointment_date = forms.DateField(
        label="Date",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    status = forms.ChoiceField(
        label="Status",
        required=False,
        choices=(("", "All statuses"), *Appointment.Status.choices),
    )
    category = forms.ChoiceField(
        label="Category",
        required=False,
        choices=(
            ("", "All categories"),
            ("upcoming", "Upcoming"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
            ("missed", "Missed"),
        ),
    )
    clinician = forms.ModelChoiceField(
        label="Clinician",
        required=False,
        queryset=StaffProfile.objects.none(),
        empty_label="All clinicians",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["clinician"].queryset = (
            StaffProfile.objects.filter(role=StaffProfile.Role.CLINICIAN)
            .select_related("account")
            .order_by("account__last_name", "account__first_name", "pk")
        )

    def clean_query(self):
        return self.cleaned_data["query"].strip()

    def appointment_pk_from_query(self):
        query = self.cleaned_data.get("query", "")
        match = re.fullmatch(r"AP-(\d+)", query, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
        if query.isdecimal():
            return int(query)
        return None
