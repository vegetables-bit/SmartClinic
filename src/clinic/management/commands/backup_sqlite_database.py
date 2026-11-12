from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connections

from clinic.database_backup import create_sqlite_backup


class Command(BaseCommand):
    help = "Create and validate a SQLite backup at a new explicit destination."

    def add_arguments(self, parser):
        parser.add_argument("destination", help="New backup file path; it must not exist.")

    def handle(self, *args, **options):
        connection = connections["default"]
        if connection.vendor != "sqlite":
            raise CommandError("The configured default database is not SQLite.")

        active_database_path = connection.settings_dict["NAME"]
        try:
            connection.ensure_connection()
            destination = create_sqlite_backup(
                connection.connection,
                options["destination"],
                active_database_path,
            )
        except (DatabaseError, OSError) as error:
            raise CommandError(f"Could not access the configured database: {error}") from error

        self.stdout.write(
            self.style.SUCCESS(f"SQLite backup created and verified: {destination}")
        )
