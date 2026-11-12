import os
import sqlite3
from pathlib import Path
from urllib.parse import quote

from django.core.management.base import CommandError


def _canonical_path(path):
    try:
        return Path(path).expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise CommandError(f"Could not resolve database path {path!s}: {error}") from error


def _validated_destination(destination, protected_paths):
    target = _canonical_path(destination)
    for protected_path in protected_paths:
        if target == _canonical_path(protected_path):
            raise CommandError(
                "The destination must not be the active database or another "
                "protected database."
            )
    if os.path.lexists(target):
        raise CommandError(f"Destination already exists: {target}")
    if not target.parent.is_dir():
        raise CommandError(
            f"Destination directory does not exist or is not a directory: "
            f"{target.parent}"
        )
    return target


def _create_destination_file(target):
    try:
        descriptor = os.open(
            target,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
    except FileExistsError as error:
        raise CommandError(f"Destination already exists: {target}") from error
    except OSError as error:
        raise CommandError(f"Could not create destination {target}: {error}") from error
    os.close(descriptor)


def _validate_database(database):
    result = database.execute("PRAGMA integrity_check").fetchall()
    if result != [("ok",)]:
        raise sqlite3.DatabaseError(
            "SQLite integrity check failed: "
            + "; ".join(str(row[0]) for row in result)
        )


def _copy_database(source, destination, protected_paths):
    target = _validated_destination(destination, protected_paths)
    created = False
    try:
        _create_destination_file(target)
        created = True
        target_database = sqlite3.connect(target)
        try:
            source.backup(target_database)
            _validate_database(target_database)
        finally:
            target_database.close()
    except (OSError, sqlite3.Error, CommandError) as error:
        if created:
            try:
                target.unlink()
            except OSError as cleanup_error:
                raise CommandError(
                    f"{error} The incomplete destination could not be removed: "
                    f"{cleanup_error}"
                ) from error
        if isinstance(error, CommandError):
            raise
        raise CommandError(f"SQLite database copy failed: {error}") from error
    return target


def create_sqlite_backup(source, destination, active_database_path):
    return _copy_database(source, destination, (active_database_path,))


def restore_sqlite_backup(backup_path, destination, active_database_path):
    backup = _canonical_path(backup_path)
    if not backup.is_file():
        raise CommandError(f"Backup file does not exist: {backup}")

    encoded_path = quote(str(backup).replace("\\", "/"), safe="/:")
    try:
        source = sqlite3.connect(f"file:{encoded_path}?mode=ro", uri=True)
    except sqlite3.Error as error:
        raise CommandError(f"Could not open SQLite backup {backup}: {error}") from error
    try:
        try:
            _validate_database(source)
        except sqlite3.Error as error:
            raise CommandError(f"Backup is not a valid SQLite database: {error}") from error
        return _copy_database(source, destination, (active_database_path, backup))
    finally:
        source.close()
