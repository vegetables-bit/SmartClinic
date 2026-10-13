# Milestone 02 Report

> **Current status correction:** M01 is approved and remains the authoritative
> project baseline. Earlier wording in this historical M02 report about M01's
> approval status is superseded. Any remaining gaps below refer
> only to detailed technical/workflow values not specified in the approved
> requirements.

## 1. Milestone name and objective.

**Milestone 02: Database Design and Configuration**

Translate the M01 domain design into an additive Django/SQLite
database foundation with models, relationships, constraints, migrations, tests,
and documentation, without implementing authentication workflows, user
interfaces, or clinic business workflows.

**Result: PASS for M02 database-foundation scope.** The approved M01 baseline is
authoritative. Schema choices below document implementation details and
workflow behaviors that are not fully specified at the technical level.

## 2. Existing project files and migration state inspected.

Before edits, inspected the current README, requirements, architecture,
role-permission matrix, domain model, M00 report, M01 report, Django settings,
source tree, database, migration state, and Git status.

Observed baseline:

- Python **3.14.3**, Django **6.1.2**.
- Project configuration in `src/config`; no existing domain app, model source,
  or migration directory.
- `src/db.sqlite3` already held Django's built-in auth, admin, contenttypes,
  and sessions schema.
- `showmigrations --plan` showed all **18 existing built-in migration entries**
  applied. No clinic migration existed at inspection.
- Direct read-only SQLite inspection found **0 auth users** and **18 rows** in
  `django_migrations`.
- Git existed but had no commits; the project files appeared as untracked
  baseline files. No existing tracked changes were overwritten or discarded.

The database and built-in migration history were preserved. No custom
`AUTH_USER_MODEL` was introduced.

## 3. Database architecture and Django applications.

Added one non-empty Django application, `clinic`, registered as
`clinic.apps.ClinicConfig`. Its models are split into modules under
`src/clinic/models/` by organization, patients, appointments, clinical
records, notifications, and audit events, with a shared abstract timestamp
model. This keeps related foreign-key entities together without creating
several empty or tightly coupled apps.

The application uses Django's existing built-in user model and a
`OneToOneField` StaffProfile. Existing auth migrations had already been
applied; this avoids a risky late switch of `AUTH_USER_MODEL`. Migrations only
add clinic tables and constraints.

## 4. Models and tables implemented.

- **Department** — `clinic_department`.
- **StaffProfile** — `clinic_staffprofile`, related one-to-one to Django User.
- **Patient** — `clinic_patient`.
- **Appointment** — `clinic_appointment`.
- **Consultation** — `clinic_consultation`.
- **MedicalHistoryEntry** — `clinic_medicalhistoryentry`.
- **AppointmentNotification** — `clinic_appointmentnotification`.
- **AuditEvent** — `clinic_auditevent`.
- Django's implicit staff/department many-to-many table.

No model, migration, or test contains real patient data. Post-migration checks
confirmed zero rows in the patient, appointment, consultation, history,
notification, and audit tables.

## 5. Important fields and data types.

- Shared `created_at`/`updated_at` DateTimeFields on clinic records; audit event
  uses `occurred_at`.
- Department name, optional description, and active flag.
- Staff account reference, optional unique staff identifier, role choice,
  optional phone, active flag, and many-to-many department memberships.
- Patient generated identifier, required full name, optional date of birth,
  phone, address, emergency contact name/phone, and archive flag.
- Appointment patient and clinician references, start/end DateTimeFields,
  optional reason/cancellation text, and status.
- Consultation patient and clinician references, optional appointment,
  encounter DateTimeField, and optional symptoms, diagnosis, treatment, and
  clinician notes.
- Medical-history patient and author references, required text, optional
  effective date, and recorded timestamp.
- Appointment notification reference, optional recipient account, type,
  optional scheduled time and read time.
- Audit actor, action, timestamp, optional generic target, and JSON metadata.

At the M02 implementation point, only full name and the generated identifier
were required in the Patient schema. Gender was missing from that schema; M06
later implemented the required gender field and migration in accordance with
the approved M01 clarification. Date of birth and contact fields remain
optional in the current model.

## 6. Entity relationships and cardinalities.

- One Django User to zero or one StaffProfile; a profile's account deletion is
  protected.
- Departments and StaffProfiles are many-to-many to allow the unresolved
  possibility that a staff member belongs to multiple departments.
- One Patient to many Appointments, Consultations, and MedicalHistoryEntries.
- One StaffProfile may be assigned many Appointments and author many clinical
  records.
- Each Consultation may be linked to zero or one Appointment; one Appointment
  may be linked to multiple Consultations.
- An Appointment may have many AppointmentNotifications, with an optional
  Django User recipient.
- AuditEvent may have an optional User actor and generic object target.

M01's available documentation did not specify a precise appointment/
consultation cardinality. M02 implements a nullable ForeignKey, permitting
multiple consultations per appointment and consultations without an
appointment. This is a documented technical implementation choice.

## 7. Primary keys, foreign keys, indexes and constraints.

- Django BigAutoField primary keys; patient-facing identifier is separate.
- Foreign keys to patient, clinician, author, appointment, and staff account
  use `PROTECT` where deletion could erase history or attribution.
- Notification recipient and audit actor use `SET_NULL` to retain records if
  an account is deleted.
- Department name has a case-insensitive unique constraint.
- Staff identifier and patient identifier are unique; multiple null staff IDs
  remain permitted.
- Staff role and appointment status values have database check constraints.
- Patient full name rejects the empty string at the database level.
- Appointment end must be later than its start at the database level.
- Purposeful indexes cover patient name, appointment patient/clinician/status
  schedules, consultation/history timelines, notification recipient/read state,
  and audit actor/action/target lookups.

The generic audit target is not a relational foreign key. Consultation
patient/clinician consistency with its optional appointment is checked only by
`Consultation.full_clean()`; normal `save()` does not call `full_clean()`.

## 8. Patient identifier implementation.

`Patient.patient_identifier` defaults to `PT-` plus an uppercase random UUID4
hex string. It is not the database primary key and is unique-constrained by
SQLite. The patient creation workflow retries safely after a collision. The
format is a technical implementation choice; M01 remains approved.

## 9. Appointment statuses and scheduling limitations.

Stored values are `scheduled`, `confirmed`, `attended`, `completed`,
`cancelled`, and `missed`. A database check rejects any other value, and
`ends_at > appointment_at` is also database-enforced.

Valid transitions, detailed status meanings, missed thresholds, attendance
rules, availability, time zones, appointment lengths/buffers, cancellation
policy, and interval-overlap prevention are not implemented. The approved M01
baseline includes appointment workflows; these are narrower workflow details.
No constraint prevents overlapping intervals; different durations make
simple start-time uniqueness insufficient. No claim that conflicting
appointments are prevented is made.

## 10. Consultation and medical-history design.

Consultation stores encounter-specific symptoms, diagnosis, treatment, and
clinician notes and may be linked to an appointment. MedicalHistoryEntry is a
separate, attributable longitudinal text entry, avoiding a second editable
copy of a consultation's diagnosis/treatment. No clinical categories or
decision-making rules were invented.

Patient and clinician/author records are protected from deletion while history
references them. No version table or amendment history was implemented;
timestamps alone do not preserve prior clinical-note content after edits.

## 11. Notification and audit-event design.

AppointmentNotification stores appointment reference, optional recipient,
notification type, optional scheduled time, read time, and timestamps. It is
only an in-app record structure: no reminder generation, recipient policy,
consent handling, background task, email/SMS, or delivery provider exists.

AuditEvent stores optional actor, action, occurrence time, generic object
reference, and JSON metadata. Creating the model does not log events
automatically and does not guarantee immutable/tamper-proof audit history.
Do not put passwords, secrets, or unnecessary clinical content in audit
metadata.

## 12. Migrations generated and applied.

- Existing applied Django migration history was preserved.
- Generated and reviewed `clinic.0001_initial`, creating the domain tables,
  relationships, indexes, and appointment constraints.
- Generated and reviewed `clinic.0002_patient_clinic_patient_name_nonempty_and_more`,
  adding patient-name and staff-role database checks.
- Both migrations applied successfully to the existing `src/db.sqlite3`.
- `showmigrations --plan` showed both clinic migrations checked/applied.
- `migrate --check` reported no pending migrations.
- `makemigrations --check --dry-run` reported `No changes detected`.

## 13. Files created or modified.

**Created**

- `src/clinic/__init__.py`, `src/clinic/apps.py`.
- `src/clinic/models/__init__.py`, `base.py`, `organization.py`,
  `patients.py`, `appointments.py`, `clinical.py`, `notifications.py`, and
  `audit.py`.
- `src/clinic/migrations/__init__.py`,
  `0001_initial.py`, and
  `0002_patient_clinic_patient_name_nonempty_and_more.py`.
- `src/clinic/tests/__init__.py` and `test_models.py`.
- `docs/database_design.md`.
- `reports/MILESTONE_02_REPORT.md`.

**Modified**

- `src/config/settings.py` to register the clinic app.
- `docs/requirements.md` to distinguish implemented schema choices from
  detailed operational values not prescribed by the approved M01 baseline.
- `docs/domain_model.md` and `docs/architecture.md` to reflect actual models,
  cardinalities, and limitations.
- `README.md` to update the structure, test command, and milestone sequence.

## 14. Dependencies added or changed.

**None.** Django 6.1.2 remains the only direct Python dependency. No external
package or database driver was added.

## 15. Commands actually executed.

The following command families were executed from the Windows PowerShell
project root with the project virtual environment. A temporary
`DJANGO_SECRET_KEY` was set for local management commands; its value is not
included in this report.

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m django --version
.\.venv\Scripts\python.exe .\src\manage.py showmigrations --plan
.\.venv\Scripts\python.exe .\src\manage.py makemigrations clinic
.\.venv\Scripts\python.exe .\src\manage.py migrate
.\.venv\Scripts\python.exe .\src\manage.py check
.\.venv\Scripts\python.exe .\src\manage.py check --database default
.\.venv\Scripts\python.exe .\src\manage.py migrate --check
.\.venv\Scripts\python.exe .\src\manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe .\src\manage.py test
.\.venv\Scripts\python.exe .\src\manage.py test clinic.tests -v 2
.\.venv\Scripts\python.exe .\src\manage.py runserver 127.0.0.1:8000 --noreload
```

A read-only Python/SQLite inspection queried table names and row counts without
inserting data.

## 16. Automated tests and observed results.

`manage.py test clinic.tests -v 2` discovered and ran **22 tests**; result:
`Ran 22 tests ... OK`. Test coverage includes model creation/relationships,
case-insensitive department uniqueness, staff account protection, identifier
generation and uniqueness, patient required-name checks, archival retention,
database appointment status/end-time constraints, patient deletion
protection, multiple consultations, consultation consistency validation,
medical-history relationships, notification relationships/recipient
deletion, and audit target/actor behavior.

The unlabelled `manage.py test` command was also executed; it found **0 tests**
and reported `NO TESTS RAN` because Django did not discover the nested `src`
test package through root discovery. The application-labeled command above
successfully ran the full model suite. The README documents that verified
command.

## 17. Django system-check results.

- `manage.py check`: `System check identified no issues (0 silenced).`
- `manage.py check --database default`: `System check identified no issues
  (0 silenced).`
- `makemigrations --check --dry-run`: `No changes detected`.
- `migrate --check`: no pending migrations.
- Development server smoke test: root page returned **HTTP 200** and the
  existing foundation-page marker was present.

## 18. Security, privacy and data-integrity considerations.

- Existing Django auth schema and the local database were not reset.
- No secrets or credentials were committed and no dependency was added.
- Protective deletion and archival/inactive flags help retain relationships;
  they are not authorization or privacy controls.
- Role values are stored but no role-based access checks, account workflow, or
  login UI is implemented.
- No real patient data was created or used; inspected domain tables remain
  empty.
- Avoid real patient data until privacy, permissions, audit policy, retention,
  backup, and deployment controls are designed and reviewed.
- No healthcare-law/standard compliance claim is made.

## 19. Problems encountered and solutions.

- The first `makemigrations` attempt failed because nested Django `Meta` class
  scope could not resolve the model's nested status enum. The database check
  was changed to an explicit tuple of allowed stored status values, then the
  migration was generated and reviewed.
- A read-only inline SQLite inspection command initially had a PowerShell
  quoting error before it queried the database. It was rerun via a
  PowerShell here-string; the successful inspection found no users and no
  clinic data.
- Plain test discovery found zero tests due to the source-tree layout. Running
  `test clinic.tests` discovered and passed all 22 tests, and the README now
  gives that exact command.

## 20. Outstanding issues and deferred functionality.

- M01 requirements are approved and remain authoritative. Detailed field
  constraints, identifier formatting, cardinalities, scheduling behavior, and
  clinical semantics not fully specified by M01 are implementation/workflow
  details and are recorded as such.
- No authentication, authorization, staff-account UI, patient UI, appointment
  workflow, consultation workflow, or interface was implemented.
- Appointment transitions, availability, interval conflicts, missed rules,
  and cancellation rules are not implemented.
- Consultation amendment/version preservation is not implemented.
- Notification scheduling/delivery and automatic audit event logging are not
  implemented.
- Retention periods, physical deletion rules, backup/recovery, deployment,
  production database, and compliance obligations remain unresolved.
- Generic audit target IDs are not protected by a relational FK; history is not
  immutable/tamper-proof.

## 21. Acceptance checklist using PASS, FAIL, NOT TESTED or BLOCKED.

1. **PASS** — Existing project, SQLite tables, and migration state inspected.
2. **PASS** — `clinic` app and split model organization documented.
3. **PASS** — Staff profiles and departments implemented.
4. **PASS** — Patient model, generated unique identifier, and archive flag
   implemented.
5. **PASS** — Appointment model, six statuses, and date-order constraint
   implemented.
6. **PASS** — Consultation model implemented.
7. **PASS** — Separate longitudinal medical-history model justified and
   implemented without copying consultation fields.
8. **PASS** — In-app appointment notification record implemented.
9. **PASS** — Audit-event storage model implemented.
10. **PASS** — Relationships, deletion behavior, indexes, and database checks
    implemented and tested. Workflow-level rules remain deferred as noted.
11. **PASS** — Two additive clinic migrations generated, reviewed, and applied.
12. **PASS** — Django system checks passed.
13. **PASS** — 22 labeled automated model tests executed and passed.
14. **PASS** — Database design document and text entity-relationship diagram
    completed.
15. **PASS** — Requirements, domain model, and architecture updated to match
    the schema and distinguish implementation details from the approved
    requirements.
16. **PASS** — This report records commands and observed evidence for each
    criterion.
17. **PASS** — No M03 or later workflow/UI/authentication functionality was
    implemented.

## 22. Instructions for starting the project and checking the database.

From the project root in Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
$env:DJANGO_SECRET_KEY = (& python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
python .\src\manage.py migrate
python .\src\manage.py check --database default
python .\src\manage.py test clinic.tests
python .\src\manage.py runserver
```

Inspect the applied migration state with:

```powershell
python .\src\manage.py showmigrations --plan
python .\src\manage.py migrate --check
```

Open <http://127.0.0.1:8000/> for the existing foundation page. The secret is
generated per PowerShell session and is not stored in source control.

## 23. Recommended next milestone.

**Milestone 03 — Authentication and Role-Based Access** was the follow-on
milestone and is implemented. It used the approved M01 role matrix and the M02
choice to store one role per StaffProfile. Do not infer that later milestones
were started as part of M02.
