from django.core.management.base import BaseCommand, CommandError

from clinic.reminder_email import send_due_reminder_emails


class Command(BaseCommand):
    help = "Send due staff appointment reminders through the configured email backend."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit < 1 or limit > 1000:
            raise CommandError("--limit must be between 1 and 1000.")
        summary = send_due_reminder_emails(limit=limit)
        self.stdout.write(
            self.style.SUCCESS(
                "Reminder email run: "
                f"{summary['sent']} sent, {summary['failed']} failed, "
                f"{summary['skipped']} skipped."
            )
        )
