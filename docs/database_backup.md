# Local SQLite backup and isolated restore

The project uses SQLite for local development at `src/db.sqlite3`. Two
management commands provide explicit backup and isolated-copy recovery:

- `backup_sqlite_database` uses SQLite's online backup API to create a
  transactionally consistent copy of the configured default SQLite database.
- `restore_sqlite_backup` validates a backup and copies it to a new,
  explicitly named SQLite file. It does not replace the configured database
  or change Django's database configuration.

## Create a backup

Choose and create a destination directory outside the tracked source tree.
This example uses a user-selected folder under the current user's local
application data; it is an example path, not an approved protected-storage
policy:

```powershell
$backupDirectory = Join-Path $env:LOCALAPPDATA "SmartClinicBackups"
New-Item -ItemType Directory -Path $backupDirectory
$backupPath = Join-Path $backupDirectory "smartclinic-backup.sqlite3"
.\.venv\Scripts\python.exe .\src\manage.py backup_sqlite_database $backupPath
```

The destination parent must already exist. The command requires an explicit
destination, refuses to overwrite an existing file or the active database,
creates a new file, and runs SQLite `PRAGMA integrity_check` before reporting
success. If the copy or verification fails, the command reports the failure
and attempts to remove the incomplete file it created. Keep the backup in a
location whose access permissions are appropriate for the data it contains.

## Validate and restore to an isolated file

Restore always requires an explicit backup path, a new destination path, and
the `--confirm` option. The destination directory must exist and the
destination file must not exist:

```powershell
$recoveryPath = Join-Path $backupDirectory "smartclinic-recovery-check.sqlite3"
.\.venv\Scripts\python.exe .\src\manage.py restore_sqlite_backup `
    $backupPath $recoveryPath --confirm
```

The command opens the source backup read-only, checks its integrity, copies it
using SQLite's backup API, and checks the resulting database. It refuses to
overwrite the configured active database, the source backup, or any other
existing destination. It does not activate the restored copy.

For recovery verification, restore to a separate isolated file and inspect it
with an appropriate SQLite tool or an explicitly configured temporary Django
environment. Do not point a running application at the recovery copy or replace
`src/db.sqlite3` as part of this procedure. Any later operational recovery or
database switch requires a separately reviewed procedure and a verified
preservation copy of the current database.

## Limitations and decisions still required

These commands provide local file copies only. They do not provide scheduling,
retention, encryption, off-device storage, automatic database replacement, or
recovery objectives. No backup schedule, retention period, protected storage
location, recovery point objective, or recovery time objective is selected by
this project. Obtain approval for those policies before using real patient
data. SQLite is currently documented as a local-development database; this
implementation does not assess production hosting or concurrent deployment.

The online backup API is used instead of copying the live database file, so
SQLite can include committed data consistently even when the database is in
use. Operators remain responsible for protecting backup files and verifying
that the chosen destination has suitable access controls and capacity.
