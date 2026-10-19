from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("clinic", "0003_patient_gender_reconcile"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="appointmentnotification",
            constraint=models.UniqueConstraint(
                fields=("appointment", "recipient", "notification_type"),
                condition=Q(
                    notification_type="appointment_reminder",
                    recipient__isnull=False,
                ),
                name="clinic_unique_appt_reminder_recipient",
            ),
        ),
    ]
