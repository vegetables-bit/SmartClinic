from django.db import models

from .base import TimeStampedModel


class QueueEntry(TimeStampedModel):
    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        CALLED = "called", "Called"
        IN_CONSULTATION = "in_consultation", "In consultation"
        COMPLETED = "completed", "Completed"

    appointment = models.OneToOneField(
        "clinic.Appointment",
        on_delete=models.PROTECT,
        related_name="queue_entry",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
    )
    checked_in_at = models.DateTimeField()
    called_at = models.DateTimeField(blank=True, null=True)
    consultation_started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    changed_by = models.ForeignKey(
        "clinic.StaffProfile",
        on_delete=models.SET_NULL,
        related_name="queue_changes",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["checked_in_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=("waiting", "called", "in_consultation", "completed")
                ),
                name="clinic_queue_status_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "checked_in_at"],
                name="clinic_queue_status_ts_idx",
            ),
        ]

    def __str__(self):
        return f"Queue entry for appointment {self.appointment_id} ({self.status})"
