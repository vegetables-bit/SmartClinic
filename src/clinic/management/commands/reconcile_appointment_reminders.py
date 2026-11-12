from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import DatabaseError

from clinic.appointment_reminders import reconcile_appointment_reminders


class Command(BaseCommand):
    help = "Generate due appointment reminders and reconcile obsolete reminders."

    def handle(self, *args, **options):
        try:
            summary = reconcile_appointment_reminders(audit_events=True)
        except DatabaseError:
            raise CommandError(
                "Reminder reconciliation stopped because persistence failed."
            ) from None
        self.stdout.write(
            self.style.SUCCESS(
                "Appointment reminders reconciled: "
                f"{summary['created']} created, "
                f"{summary['updated']} updated, "
                f"{summary['removed']} removed, "
                f"{summary['skipped']} skipped."
            )
        )
