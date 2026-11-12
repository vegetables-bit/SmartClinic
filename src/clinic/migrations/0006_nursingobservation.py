# Generated for the approved nursing-observation workflow.

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("clinic", "0005_consultationrevision"),
    ]

    operations = [
        migrations.CreateModel(
            name="NursingObservation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("observed_at", models.DateTimeField(default=timezone.now)),
                (
                    "body_temperature_celsius",
                    models.DecimalField(
                        blank=True,
                        decimal_places=1,
                        max_digits=4,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(0.1)
                        ],
                    ),
                ),
                (
                    "pulse_rate_bpm",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "systolic_blood_pressure_mm_hg",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "diastolic_blood_pressure_mm_hg",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "respiratory_rate_bpm",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "weight_kg",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=6,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(0.01)
                        ],
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                (
                    "appointment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="nursing_observations",
                        to="clinic.appointment",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="nursing_observations",
                        to="clinic.staffprofile",
                    ),
                ),
            ],
            options={
                "ordering": ["-observed_at", "-pk"],
            },
        ),
    ]
