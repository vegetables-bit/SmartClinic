from django.db import models
from django.db.models import Q

from .base import TimeStampedModel


class Appointment(TimeStampedModel):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CONFIRMED = "confirmed", "Confirmed"
        ATTENDED = "attended", "Attended"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        MISSED = "missed", "Missed"

    patient = models.ForeignKey(
        "clinic.Patient",
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    clinician = models.ForeignKey(
        "clinic.StaffProfile",
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    appointment_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason_for_visit = models.TextField(blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["appointment_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=models.F("appointment_at")),
                name="clinic_appointment_end_after_start",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=(
                        "scheduled",
                        "confirmed",
                        "attended",
                        "completed",
                        "cancelled",
                        "missed",
                    )
                ),
                name="clinic_appointment_status_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["patient", "appointment_at"],
                name="clinic_appt_patient_time_idx",
            ),
            models.Index(
                fields=["clinician", "appointment_at"],
                name="clinic_appt_staff_time_idx",
            ),
            models.Index(
                fields=["status", "appointment_at"],
                name="clinic_appt_status_time_idx",
            ),
        ]

    def __str__(self):
        return f"{self.patient} at {self.appointment_at:%Y-%m-%d %H:%M}"

    @property
    def appointment_identifier(self):
        if self.pk is None:
            return ""
        return f"AP-{self.pk:06d}"
