# Appointment reminder scheduling

Smart Clinic stores in-app appointment reminders in the existing
`AppointmentNotification` table. A reminder is eligible when its appointment
is still in the future, has status `scheduled` or `confirmed`, and the assigned
clinician and clinician account are active.

The configured reminder lead time is
`APPOINTMENT_REMINDER_LEAD_TIME_HOURS` (24 hours by default). A reminder is
created once the current time reaches or passes
`appointment_at - lead_time`. Its `scheduled_for` value records that exact due
time. If a scheduler polls every five minutes, creation can be delayed by up to
approximately five minutes after the due time. Running the command manually is
also supported.

From the repository root, invoke:

```powershell
.\.venv\Scripts\python.exe .\src\manage.py reconcile_appointment_reminders
```

The command is not started automatically by Django. Configure an external
scheduler to run it periodically in the deployed environment. For a five-minute
polling interval, Windows Task Scheduler or a server cron/task runner can invoke
the command every five minutes using the deployment's Python executable and
environment configuration. Configure only one regular scheduler instance per
database where possible; the conditional database uniqueness constraint also
prevents duplicate reminders if runs overlap.

Repeated runs preserve a reminder's read state while its scheduled due time is
unchanged. A changed schedule recalculates `scheduled_for` and resets read state
so the clinician sees the changed appointment reminder again. Cancelled,
completed/non-eligible, past, or inactive-recipient reminders are removed.
No email, SMS, patient-facing notification, or appointment status transition is
implemented by this command.
