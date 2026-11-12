from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from clinic.audit import record_audit_event
from clinic.models import Appointment, AppointmentNotification, StaffProfile

REMINDER_NOTIFICATION_TYPE = "appointment_reminder"
REMINDER_ELIGIBLE_STATUSES = (
    Appointment.Status.SCHEDULED,
    Appointment.Status.CONFIRMED,
)
REMINDER_RECONCILIATION_TASK = "reconcile_appointment_reminders"


def _record_reminder_event(*, action, target, extra_metadata=None):
    metadata = {
        "actor_kind": "system",
        "task": REMINDER_RECONCILIATION_TASK,
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    record_audit_event(
        actor=None,
        action=action,
        target=target,
        metadata=metadata,
    )


def reminder_due_at(appointment):
    return appointment.appointment_at - timedelta(
        hours=settings.APPOINTMENT_REMINDER_LEAD_TIME_HOURS,
    )


def sync_appointment_reminder(appointment, *, now=None, audit_events=False):
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
            removed_reminders = list(reminders) if audit_events else ()
            result["removed"] = (
                len(removed_reminders) if audit_events else reminders.count()
            )
            for reminder in removed_reminders:
                _record_reminder_event(
                    action="reminder.removed",
                    target=locked_appointment,
                    extra_metadata={
                        "notification_id": reminder.pk,
                        "reason": "appointment_ineligible",
                    },
                )
            reminders.delete()
            result["skipped"] = 1
            return result

        due_at = reminder_due_at(locked_appointment)
        if due_at > now:
            removed_reminders = list(reminders) if audit_events else ()
            result["removed"] = (
                len(removed_reminders) if audit_events else reminders.count()
            )
            for reminder in removed_reminders:
                _record_reminder_event(
                    action="reminder.removed",
                    target=locked_appointment,
                    extra_metadata={
                        "notification_id": reminder.pk,
                        "reason": "reminder_not_due",
                    },
                )
            reminders.delete()
            result["skipped"] = 1
            return result

        recipient = clinician.account
        existing_reminder = reminders.filter(recipient=recipient).first()
        stale_reminders = reminders.exclude(recipient=recipient)
        if existing_reminder is not None:
            stale_reminders = stale_reminders.exclude(pk=existing_reminder.pk)
        stale_rows = list(stale_reminders) if audit_events else ()
        result["removed"] += (
            len(stale_rows) if audit_events else stale_reminders.count()
        )
        for reminder in stale_rows:
            _record_reminder_event(
                action="reminder.removed",
                target=locked_appointment,
                extra_metadata={
                    "notification_id": reminder.pk,
                    "reason": "recipient_changed",
                },
            )
        stale_reminders.delete()

        if existing_reminder is None:
            notification, created = AppointmentNotification.objects.get_or_create(
                appointment=locked_appointment,
                recipient=recipient,
                notification_type=REMINDER_NOTIFICATION_TYPE,
                defaults={"scheduled_for": due_at},
            )
            result["created"] = int(created)
            result["skipped"] = int(not created)
            if audit_events and created:
                _record_reminder_event(
                    action="reminder.created",
                    target=notification,
                )
            return result

        if existing_reminder.scheduled_for != due_at:
            existing_reminder.scheduled_for = due_at
            existing_reminder.read_at = None
            existing_reminder.save(
                update_fields=("scheduled_for", "read_at", "updated_at")
            )
            result["updated"] = 1
            if audit_events:
                _record_reminder_event(
                    action="reminder.updated",
                    target=existing_reminder,
                )
        else:
            result["skipped"] = 1
    return result


def reconcile_appointment_reminders(*, now=None, audit_events=False):
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
        outcome = sync_appointment_reminder(
            appointment,
            now=now,
            audit_events=audit_events,
        )
        for key, count in outcome.items():
            totals[key] += count
    if audit_events and any(
        totals[key] for key in ("created", "updated", "removed")
    ):
        _record_reminder_event(
            action="reminder.reconciliation.completed",
            target=None,
            extra_metadata={
                "created": totals["created"],
                "updated": totals["updated"],
                "removed": totals["removed"],
            },
        )
    return totals
