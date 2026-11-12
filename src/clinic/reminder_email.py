from django.conf import settings
from django.core.mail import send_mail
from django.db.models import F
from django.utils import timezone

from clinic.appointment_reminders import REMINDER_NOTIFICATION_TYPE
from clinic.models import Appointment, AppointmentNotification, StaffProfile

MAX_EMAIL_ATTEMPTS = 3


def send_due_reminder_emails(*, now=None, limit=100):
    """Send generic staff reminders through Django's configured email backend."""
    now = now or timezone.now()
    notifications = (
        AppointmentNotification.objects.filter(
            notification_type=REMINDER_NOTIFICATION_TYPE,
            scheduled_for__lte=now,
            email_sent_at__isnull=True,
            email_attempt_count__lt=MAX_EMAIL_ATTEMPTS,
            appointment__appointment_at__gt=now,
            appointment__status__in=(
                Appointment.Status.SCHEDULED,
                Appointment.Status.CONFIRMED,
            ),
            appointment__clinician__role=StaffProfile.Role.CLINICIAN,
            appointment__clinician__is_active=True,
            appointment__clinician__account__is_active=True,
            recipient__is_active=True,
            recipient_id=F("appointment__clinician__account_id"),
        )
        .select_related("appointment", "recipient")
        .order_by("scheduled_for", "pk")[:limit]
    )
    summary = {"sent": 0, "failed": 0, "skipped": 0}
    for notification in notifications:
        recipient_email = notification.recipient.email.strip()
        if not recipient_email:
            summary["skipped"] += 1
            continue

        notification.email_attempt_count += 1
        notification.email_last_attempt_at = now
        notification.email_last_error_code = ""
        notification.save(
            update_fields=(
                "email_attempt_count",
                "email_last_attempt_at",
                "email_last_error_code",
                "updated_at",
            )
        )
        appointment = notification.appointment
        subject = f"Smart Clinic appointment reminder: {appointment.appointment_identifier}"
        body = (
            f"An appointment ({appointment.appointment_identifier}) is scheduled "
            f"for {timezone.localtime(appointment.appointment_at):%Y-%m-%d %H:%M %Z}.\n\n"
            "Sign in to Smart Clinic to view the appointment details."
        )
        try:
            sent = send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [recipient_email],
                fail_silently=False,
            )
        except Exception:  # Provider exceptions vary by configured backend.
            sent = 0

        if sent:
            notification.email_sent_at = now
            notification.email_last_error_code = ""
            notification.save(
                update_fields=("email_sent_at", "email_last_error_code", "updated_at")
            )
            summary["sent"] += 1
        else:
            notification.email_last_error_code = "provider_error"
            notification.save(update_fields=("email_last_error_code", "updated_at"))
            summary["failed"] += 1
    return summary
