import sqlite3
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from clinic.database_backup import create_sqlite_backup, restore_sqlite_backup


class Command(BaseCommand):
    help = "Measure a backup and isolated restore using synthetic data only."

    def add_arguments(self, parser):
        parser.add_argument("--rows", type=int, default=1000)

    def handle(self, *args, **options):
        rows = options["rows"]
        if rows < 1 or rows > 100000:
            raise CommandError("--rows must be between 1 and 100000.")

        active_database_path = connections["default"].settings_dict["NAME"]
        with tempfile.TemporaryDirectory(prefix="smartclinic-recovery-demo-") as folder:
            root = Path(folder)
            source_path = root / "synthetic-source.sqlite3"
            backup_path = root / "synthetic-backup.sqlite3"
            restore_path = root / "synthetic-restore.sqlite3"

            source = sqlite3.connect(source_path)
            try:
                source.execute(
                    "CREATE TABLE demo_records "
                    "(record_id INTEGER PRIMARY KEY, label TEXT NOT NULL)"
                )
                source.executemany(
                    "INSERT INTO demo_records (record_id, label) VALUES (?, ?)",
                    ((index, f"synthetic-{index:06d}") for index in range(1, rows + 1)),
                )
                source.commit()
                start = time.perf_counter()
                backup = create_sqlite_backup(
                    source,
                    backup_path,
                    active_database_path,
                )
                backup_seconds = time.perf_counter() - start
            finally:
                source.close()

            start = time.perf_counter()
            restored = restore_sqlite_backup(
                backup,
                restore_path,
                active_database_path,
            )
            restore_seconds = time.perf_counter() - start

            encoded_path = quote(str(restored).replace("\\", "/"), safe="/:")
            recovered = sqlite3.connect(f"file:{encoded_path}?mode=ro", uri=True)
            try:
                recovered_rows = recovered.execute(
                    "SELECT COUNT(*) FROM demo_records"
                ).fetchone()[0]
                integrity = recovered.execute("PRAGMA integrity_check").fetchone()[0]
                if recovered_rows != rows or integrity != "ok":
                    raise CommandError("The synthetic recovery verification failed.")
            finally:
                recovered.close()

            self.stdout.write(self.style.SUCCESS("Synthetic SQLite recovery demonstration passed."))
            self.stdout.write(f"Synthetic records restored: {recovered_rows}")
            self.stdout.write(f"Backup size: {backup.stat().st_size} bytes")
            self.stdout.write(f"Backup elapsed: {backup_seconds:.6f} seconds")
            self.stdout.write(f"Restore elapsed: {restore_seconds:.6f} seconds")
            self.stdout.write(f"Integrity check: {integrity}")
