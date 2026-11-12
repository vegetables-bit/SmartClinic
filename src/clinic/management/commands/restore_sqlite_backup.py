from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connections

from clinic.database_backup import restore_sqlite_backup


class Command(BaseCommand):
    help = "Restore a SQLite backup to a new isolated destination; never replaces a database."

    def add_arguments(self, parser):
        parser.add_argument("backup", help="Path to an existing SQLite backup.")
        parser.add_argument(
            "destination",
            help="New isolated SQLite file path; it must not exist.",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm that the isolated destination is intentional.",
        )

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError(
                "Restore requires explicit confirmation with --confirm."
            )

        connection = connections["default"]
        if connection.vendor != "sqlite":
            raise CommandError("The configured default database is not SQLite.")

        try:
            destination = restore_sqlite_backup(
                options["backup"],
                options["destination"],
                connection.settings_dict["NAME"],
            )
        except (DatabaseError, OSError) as error:
            raise CommandError(f"Could not access the SQLite backup: {error}") from error

        self.stdout.write(
            self.style.SUCCESS(
                f"SQLite backup restored and verified to isolated destination: "
                f"{destination}"
            )
        )
