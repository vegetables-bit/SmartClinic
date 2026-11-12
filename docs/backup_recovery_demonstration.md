# Synthetic backup and recovery demonstration

Run this command to measure the existing SQLite backup and isolated restore
helpers with synthetic records. It creates temporary SQLite files under the
operating-system temporary directory and removes them when the command exits.
It reads the configured active database path only to protect that path from
being selected as a destination; it does not connect to or copy the active
database.

```powershell
python .\src\manage.py demo_sqlite_backup_recovery
```

The default run creates 1,000 synthetic rows and reports restored row count,
backup size, backup duration, restore duration, and SQLite integrity result.
To change the synthetic workload, pass `--rows N` (1 through 100,000). Record
the command, machine/runtime context, output and date in the academic report;
performance figures are local measurements and must not be presented as
production recovery guarantees.

The demonstration complements the explicit backup and restore commands in
`database_backup.md`; it does not test recovery of real clinic data, establish
backup scheduling/retention, or authorize replacing the active database.
