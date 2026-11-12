from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .base import TimeStampedModel


class Consultation(TimeStampedModel):
    patient = models.ForeignKey(
        "clinic.Patient",
        on_delete=models.PROTECT,
        related_name="consultations",
    )
    appointment = models.ForeignKey(
        "clinic.Appointment",
        on_delete=models.PROTECT,
        related_name="consultations",
        blank=True,
        null=True,
    )
    clinician = models.ForeignKey(
        "clinic.StaffProfile",
        on_delete=models.PROTECT,
        related_name="consultations",
    )
    consultation_at = models.DateTimeField(default=timezone.now)
    symptoms = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)
    treatment = models.TextField(blank=True)
    clinician_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-consultation_at"]
        indexes = [
            models.Index(
                fields=["patient", "consultation_at"],
                name="clinic_cons_patient_time_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.appointment_id and self.patient_id:
            if self.appointment.patient_id != self.patient_id:
                raise ValidationError(
                    {"appointment": "The appointment must belong to this patient."}
                )
        if self.appointment_id and self.clinician_id:
            if self.appointment.clinician_id != self.clinician_id:
                raise ValidationError(
                    {"clinician": "The clinician must match the appointment."}
                )

    def __str__(self):
        return f"Consultation for {self.patient} at {self.consultation_at:%Y-%m-%d}"


class ConsultationRevision(TimeStampedModel):
    consultation = models.ForeignKey(
        Consultation,
        on_delete=models.PROTECT,
        related_name="revisions",
    )
    revised_by = models.ForeignKey(
        "clinic.StaffProfile",
        on_delete=models.PROTECT,
        related_name="consultation_revisions",
    )
    previous_appointment = models.ForeignKey(
        "clinic.Appointment",
        on_delete=models.PROTECT,
        related_name="consultation_revisions",
        blank=True,
        null=True,
    )
    previous_consultation_at = models.DateTimeField()
    previous_symptoms = models.TextField(blank=True)
    previous_diagnosis = models.TextField(blank=True)
    previous_treatment = models.TextField(blank=True)
    previous_clinician_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"Revision {self.pk} of consultation {self.consultation_id}"


class MedicalHistoryEntry(TimeStampedModel):
    patient = models.ForeignKey(
        "clinic.Patient",
        on_delete=models.PROTECT,
        related_name="medical_history_entries",
    )
    author = models.ForeignKey(
        "clinic.StaffProfile",
        on_delete=models.PROTECT,
        related_name="medical_history_entries",
    )
    entry_text = models.TextField()
    effective_date = models.DateField(blank=True, null=True)
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(
                fields=["patient", "recorded_at"],
                name="clinic_history_patient_ts_idx",
            ),
        ]

    def __str__(self):
        return f"Medical history entry for {self.patient}"


class NursingObservation(TimeStampedModel):
    appointment = models.ForeignKey(
        "clinic.Appointment",
        on_delete=models.PROTECT,
        related_name="nursing_observations",
    )
    recorded_by = models.ForeignKey(
        "clinic.StaffProfile",
        on_delete=models.PROTECT,
        related_name="nursing_observations",
    )
    observed_at = models.DateTimeField(default=timezone.now)
    body_temperature_celsius = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        blank=True,
        null=True,
        validators=[MinValueValidator(0.1)],
    )
    pulse_rate_bpm = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
    )
    systolic_blood_pressure_mm_hg = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
    )
    diastolic_blood_pressure_mm_hg = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
    )
    respiratory_rate_bpm = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
    )
    weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0.01)],
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-observed_at", "-pk"]

    def clean(self):
        super().clean()
        if self.recorded_by_id and self.recorded_by.role != "nurse":
            raise ValidationError(
                {"recorded_by": "Only a Nurse may record a nursing observation."}
            )
        systolic = self.systolic_blood_pressure_mm_hg
        diastolic = self.diastolic_blood_pressure_mm_hg
        if (systolic is None) != (diastolic is None):
            raise ValidationError(
                "Enter both systolic and diastolic blood pressure values."
            )
        if all(
            value is None
            for value in (
                self.body_temperature_celsius,
                self.pulse_rate_bpm,
                systolic,
                diastolic,
                self.respiratory_rate_bpm,
                self.weight_kg,
            )
        ):
            raise ValidationError("Enter at least one observation measurement.")

    def __str__(self):
        return (
            f"Nursing observation for appointment {self.appointment_id} "
            f"at {self.observed_at:%Y-%m-%d %H:%M}"
        )
