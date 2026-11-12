# Staff appointment reminder email

The project can send due in-app appointment reminders to the assigned active
Clinician's staff email using Django's configured email backend. Email is an
explicit, separate operation: creating an appointment or running
`reconcile_appointment_reminders` does not send mail.

Invoke the delivery command after reminder reconciliation, using the approved
deployment environment and provider configuration:

```powershell
python .\src\manage.py send_appointment_reminder_emails
```

The command sends a generic message containing the appointment identifier and
time, but no patient name, contact details, reason for visit, or clinical
content. It records delivery time and attempt count on the reminder. Provider
errors are stored as the bounded code `provider_error`; retries stop after
three attempts. A Clinician without an email address is skipped and can be
retried after their address is corrected. Use `--limit` to bound each run.

Development uses Django's console email backend. Production must configure an
approved Django email backend and sender; SMTP settings are read from the
environment as listed in `security_configuration.md`. No specific provider,
real delivery, SMS channel, patient consent workflow, or scheduler is supplied
by this code. Configure a scheduler only after testing against a non-delivering
provider or an approved test mailbox.
