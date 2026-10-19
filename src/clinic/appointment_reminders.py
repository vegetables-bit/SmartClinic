from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from clinic.models import Appointment, AppointmentNotification, StaffProfile

REMINDER_NOTIFICATION_TYPE = "appointment_reminder"
REMINDER_ELIGIBLE_STATUSES = (
    Appointment.Status.SCHEDULED,
    Appointment.Status.CONFIRMED,
)


def reminder_due_at(appointment):
    return appointment.appointment_at - timedelta(
        hours=settings.APPOINTMENT_REMINDER_LEAD_TIME_HOURS,
    )


def sync_appointment_reminder(appointment, *, now=None):
    now = now or timezone.now()
    result = {"created": 0, "updated": 0, "removed": 0, "skipped": 0}

    with transaction.atomic():
        locked_appointment = (
            Appointment.objects.select_for_update()
            .select_related("clinician__account")
            .get(pk=appointment.pk)
        )
        reminders = AppointmentNotification.objects.filter(
            appointment=locked_appointment,
            notification_type=REMINDER_NOTIFICATION_TYPE,
        )
        clinician = locked_appointment.clinician
        eligible = (
            locked_appointment.status in REMINDER_ELIGIBLE_STATUSES
            and locked_appointment.appointment_at > now
            and clinician.role == StaffProfile.Role.CLINICIAN
            and clinician.is_active
            and clinician.account.is_active
        )
        if not eligible:
            result["removed"] = reminders.count()
            reminders.delete()
            result["skipped"] = 1
            return result

        due_at = reminder_due_at(locked_appointment)
        if due_at > now:
            result["removed"] = reminders.count()
            reminders.delete()
            result["skipped"] = 1
            return result

        recipient = clinician.account
        existing_reminder = reminders.filter(recipient=recipient).first()
        stale_reminders = reminders.exclude(recipient=recipient)
        if existing_reminder is not None:
            stale_reminders = stale_reminders.exclude(pk=existing_reminder.pk)
        result["removed"] += stale_reminders.count()
        stale_reminders.delete()

        if existing_reminder is None:
            _, created = AppointmentNotification.objects.get_or_create(
                appointment=locked_appointment,
                recipient=recipient,
                notification_type=REMINDER_NOTIFICATION_TYPE,
                defaults={"scheduled_for": due_at},
            )
            result["created"] = int(created)
            result["skipped"] = int(not created)
            return result

        if existing_reminder.scheduled_for != due_at:
            existing_reminder.scheduled_for = due_at
            existing_reminder.read_at = None
            existing_reminder.save(
                update_fields=("scheduled_for", "read_at", "updated_at")
            )
            result["updated"] = 1
        else:
            result["skipped"] = 1
    return result


def reconcile_appointment_reminders(*, now=None):
    now = now or timezone.now()
    upcoming_ids = Appointment.objects.filter(
        status__in=REMINDER_ELIGIBLE_STATUSES,
        appointment_at__gt=now,
    ).values_list("pk", flat=True)
    existing_ids = AppointmentNotification.objects.filter(
        notification_type=REMINDER_NOTIFICATION_TYPE,
    ).values_list("appointment_id", flat=True)
    appointment_ids = set(upcoming_ids).union(existing_ids)

    totals = {"created": 0, "updated": 0, "removed": 0, "skipped": 0}
    for appointment_id in sorted(appointment_ids):
        try:
            appointment = Appointment.objects.get(pk=appointment_id)
        except Appointment.DoesNotExist:
            continue
        outcome = sync_appointment_reminder(appointment, now=now)
        for key, count in outcome.items():
            totals[key] += count
    return totals
