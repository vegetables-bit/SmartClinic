import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("clinic", "0006_nursingobservation"),
    ]

    operations = [
        migrations.CreateModel(
            name="QueueEntry",
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
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("waiting", "Waiting"),
                            ("called", "Called"),
                            ("in_consultation", "In consultation"),
                            ("completed", "Completed"),
                        ],
                        default="waiting",
                        max_length=20,
                    ),
                ),
                ("checked_in_at", models.DateTimeField()),
                ("called_at", models.DateTimeField(blank=True, null=True)),
                (
                    "consultation_started_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "appointment",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="queue_entry",
                        to="clinic.appointment",
                    ),
                ),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="queue_changes",
                        to="clinic.staffprofile",
                    ),
                ),
            ],
            options={"ordering": ["checked_in_at", "pk"]},
        ),
        migrations.AddConstraint(
            model_name="queueentry",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=("waiting", "called", "in_consultation", "completed")
                ),
                name="clinic_queue_status_valid",
            ),
        ),
        migrations.AddIndex(
            model_name="queueentry",
            index=models.Index(
                fields=["status", "checked_in_at"],
                name="clinic_queue_status_ts_idx",
            ),
        ),
        migrations.AddField(
            model_name="appointmentnotification",
            name="email_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="appointmentnotification",
            name="email_last_attempt_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="appointmentnotification",
            name="email_attempt_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="appointmentnotification",
            name="email_last_error_code",
            field=models.CharField(blank=True, max_length=32),
        ),
    ]
