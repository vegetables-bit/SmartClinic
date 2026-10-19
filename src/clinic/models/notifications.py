from django.conf import settings
from django.db import models

from .base import TimeStampedModel


class AppointmentNotification(TimeStampedModel):
    appointment = models.ForeignKey(
        "clinic.Appointment",
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="appointment_notifications",
        blank=True,
        null=True,
    )
    notification_type = models.CharField(
        max_length=50,
        default="appointment_reminder",
    )
    scheduled_for = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=("appointment", "recipient", "notification_type"),
                condition=models.Q(
                    notification_type="appointment_reminder",
                    recipient__isnull=False,
                ),
                name="clinic_unique_appt_reminder_recipient",
            ),
        ]
        indexes = [
            models.Index(
                fields=["recipient", "read_at"],
                name="clinic_notice_rec_read_idx",
            ),
        ]

    def __str__(self):
        return f"{self.notification_type} for appointment {self.appointment_id}"
