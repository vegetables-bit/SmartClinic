import uuid

from django.db import models
from django.db.models import Q

from .base import TimeStampedModel


def generate_patient_identifier():
    return f"PT-{uuid.uuid4().hex.upper()}"


class Patient(TimeStampedModel):
    class Gender(models.TextChoices):
        FEMALE = "female", "Female"
        MALE = "male", "Male"
        NON_BINARY = "non_binary", "Non-binary"
        PREFER_NOT_TO_SAY = "prefer_not_to_say", "Prefer not to say"

    patient_identifier = models.CharField(
        max_length=35,
        unique=True,
        default=generate_patient_identifier,
        editable=False,
    )
    full_name = models.CharField(max_length=200)
    gender = models.CharField(
        max_length=20,
        choices=Gender.choices,
        default=Gender.PREFER_NOT_TO_SAY,
    )
    date_of_birth = models.DateField(blank=True, null=True)
    phone_number = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["full_name", "patient_identifier"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(full_name=""),
                name="clinic_patient_name_nonempty",
            ),
        ]
        indexes = [
            models.Index(fields=["full_name"], name="clinic_patient_name_idx"),
        ]

    def __str__(self):
        return f"{self.patient_identifier} - {self.full_name}"
