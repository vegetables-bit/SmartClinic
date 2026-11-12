import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase


class SQLiteBackupCommandTests(SimpleTestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.directory = Path(self.temp_directory.name)
        self.active_database = self.directory / "active.sqlite3"
        with closing(sqlite3.connect(self.active_database)) as database:
            database.execute(
                "CREATE TABLE sample_records (id INTEGER PRIMARY KEY, value TEXT)"
            )
            database.execute(
                "INSERT INTO sample_records (value) VALUES (?)",
                ("preserved test value",),
            )
            database.commit()

    def run_with_database(self, database_path, command, *args, **options):
        database = sqlite3.connect(database_path)
        connection = SimpleNamespace(
            vendor="sqlite",
            settings_dict={"NAME": str(database_path)},
            connection=database,
            ensure_connection=lambda: None,
        )
        command_modules = (
            "clinic.management.commands.backup_sqlite_database.connections",
            "clinic.management.commands.restore_sqlite_backup.connections",
        )
        try:
            with patch(command_modules[0], {"default": connection}), patch(
                command_modules[1],
                {"default": connection},
            ):
                return call_command(
                    command,
                    *args,
                    skip_checks=True,
                    **options,
                )
        finally:
            database.close()

    def read_sample_values(self, database_path):
        with closing(sqlite3.connect(database_path)) as database:
            return database.execute(
                "SELECT value FROM sample_records ORDER BY id"
            ).fetchall()

    def test_backup_creates_valid_database_and_preserves_data(self):
        destination = self.directory / "backup.sqlite3"

        self.run_with_database(
            self.active_database,
            "backup_sqlite_database",
            str(destination),
        )

        self.assertEqual(
            self.read_sample_values(destination),
            [("preserved test value",)],
        )
        with closing(sqlite3.connect(destination)) as database:
            self.assertEqual(database.execute("PRAGMA integrity_check").fetchone(), ("ok",))

    def test_backup_rejects_destination_with_missing_parent(self):
        destination = self.directory / "missing" / "backup.sqlite3"

        with self.assertRaisesMessage(CommandError, "Destination directory"):
            self.run_with_database(
                self.active_database,
                "backup_sqlite_database",
                str(destination),
            )

        self.assertFalse(destination.parent.exists())

    def test_backup_does_not_overwrite_existing_file(self):
        destination = self.directory / "existing.sqlite3"
        destination.write_bytes(b"existing backup contents")

        with self.assertRaisesMessage(CommandError, "Destination already exists"):
            self.run_with_database(
                self.active_database,
                "backup_sqlite_database",
                str(destination),
            )

        self.assertEqual(destination.read_bytes(), b"existing backup contents")

    def test_backup_refuses_active_database_path(self):
        active_contents = self.active_database.read_bytes()

        with self.assertRaisesMessage(CommandError, "active database"):
            self.run_with_database(
                self.active_database,
                "backup_sqlite_database",
                str(self.active_database),
            )

        self.assertEqual(self.active_database.read_bytes(), active_contents)
        self.assertEqual(
            self.read_sample_values(self.active_database),
            [("preserved test value",)],
        )

    def test_restore_requires_confirmation(self):
        backup = self.directory / "backup.sqlite3"
        self.run_with_database(
            self.active_database,
            "backup_sqlite_database",
            str(backup),
        )
        destination = self.directory / "restored.sqlite3"

        with self.assertRaisesMessage(CommandError, "requires explicit confirmation"):
            self.run_with_database(
                self.active_database,
                "restore_sqlite_backup",
                str(backup),
                str(destination),
            )

        self.assertFalse(destination.exists())

    def test_restore_copies_backup_only_to_new_isolated_destination(self):
        backup = self.directory / "backup.sqlite3"
        destination = self.directory / "restored.sqlite3"
        self.run_with_database(
            self.active_database,
            "backup_sqlite_database",
            str(backup),
        )

        self.run_with_database(
            self.active_database,
            "restore_sqlite_backup",
            str(backup),
            str(destination),
            confirm=True,
        )

        self.assertEqual(
            self.read_sample_values(destination),
            [("preserved test value",)],
        )
        with closing(sqlite3.connect(destination)) as database:
            self.assertEqual(database.execute("PRAGMA integrity_check").fetchone(), ("ok",))

    def test_restore_does_not_overwrite_existing_destination(self):
        backup = self.directory / "backup.sqlite3"
        destination = self.directory / "existing.sqlite3"
        self.run_with_database(
            self.active_database,
            "backup_sqlite_database",
            str(backup),
        )
        destination.write_bytes(b"existing database contents")

        with self.assertRaisesMessage(CommandError, "Destination already exists"):
            self.run_with_database(
                self.active_database,
                "restore_sqlite_backup",
                str(backup),
                str(destination),
                confirm=True,
            )

        self.assertEqual(
            destination.read_bytes(),
            b"existing database contents",
        )

    def test_restore_refuses_active_database_path(self):
        backup = self.directory / "backup.sqlite3"
        self.run_with_database(
            self.active_database,
            "backup_sqlite_database",
            str(backup),
        )
        active_contents = self.active_database.read_bytes()

        with self.assertRaisesMessage(CommandError, "active database"):
            self.run_with_database(
                self.active_database,
                "restore_sqlite_backup",
                str(backup),
                str(self.active_database),
                confirm=True,
            )

        self.assertEqual(self.active_database.read_bytes(), active_contents)
        self.assertEqual(
            self.read_sample_values(self.active_database),
            [("preserved test value",)],
        )

    def test_restore_rejects_invalid_backup_without_creating_destination(self):
        backup = self.directory / "not-a-database.sqlite3"
        backup.write_bytes(b"not a sqlite database")
        destination = self.directory / "restored.sqlite3"

        with self.assertRaisesMessage(CommandError, "not a valid SQLite database"):
            self.run_with_database(
                self.active_database,
                "restore_sqlite_backup",
                str(backup),
                str(destination),
                confirm=True,
            )

        self.assertFalse(destination.exists())
