from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from .base import TimeStampedModel


class Department(TimeStampedModel):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="clinic_department_name_ci_uniq",
            ),
        ]

    def __str__(self):
        return self.name


class StaffProfile(TimeStampedModel):
    class Role(models.TextChoices):
        ADMINISTRATOR = "administrator", "Administrator"
        RECEPTIONIST = "receptionist", "Receptionist"
        CLINICIAN = "clinician", "Doctor/Clinician"
        NURSE = "nurse", "Nurse"

    account = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="staff_profile",
    )
    staff_identifier = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    phone_number = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name="staff_members",
    )

    class Meta:
        ordering = ["account_id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    role__in=(
                        "administrator",
                        "receptionist",
                        "clinician",
                        "nurse",
                    )
                ),
                name="clinic_staff_role_valid",
            ),
        ]

    def __str__(self):
        return f"{self.account} ({self.get_role_display()})"
