# Smart Clinic

A web-based Smart Clinic Appointment and Patient Records Tracking System. The
project currently provides staff authentication and management, a shared
responsive interface, demographic patient registration and management, and
appointment scheduling and management, with scheduled in-app appointment
reminder generation and reconciliation, and clinician-scoped consultation and
medical-history workflows. The shared staff dashboard includes role-scoped
appointment summaries; an administrator-only appointment status report is
available with inclusive local-date filters. Queue workflows, role-specific
aggregated operational reports, staff reminder email delivery, and an isolated
synthetic backup/recovery demonstration are also included.

## Prerequisites

- Python compatible with Django 6.1.2 (Python 3.14.3 was used to set up this
  milestone)
- Git
- Visual Studio Code (recommended editor)

The initial development database is SQLite, which Django includes. Django is
the only direct Python dependency. The interface uses Django templates and
project CSS without a separate UI framework.

## Project structure

```text
.
├── docs/                 # Requirements, domain model, roles, and database design
├── reports/              # Milestone verification reports
├── src/
│   ├── clinic/           # Database models grouped into focused modules
│   ├── config/           # Django settings, URLs, and WSGI/ASGI entry points
│   ├── templates/        # Shared shell, patient, staff, and appointment pages
│   └── manage.py         # Django management commands
├── .gitignore
├── requirements.txt
└── README.md
```

The `config` package contains project configuration. The `clinic` application
contains the existing data models and implemented staff, patient, and
appointment functionality.

The project requirements and role model are approved and reflected in the
current implementation. See `docs/requirements.md` for the approved baseline,
`docs/role_permission_matrix.md` for the enforced role matrix, and
`docs/database_design.md` for the current schema and implementation details.

## Setup (Windows PowerShell)

Run these commands from the repository root. To create a fresh environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation scripts, either use the environment's Python
directly (`.\.venv\Scripts\python.exe`) or, for this PowerShell process only,
run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and activate
again.

Set a random development secret for the current PowerShell session. It is
generated at runtime and is not stored in source control:

```powershell
$env:DJANGO_ENV = 'development'
$env:DJANGO_SECRET_KEY = (& python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
```

Set these variables again in each new terminal before running Django commands.
For production configuration requirements, see
[`docs/security_configuration.md`](docs/security_configuration.md).
Do not use a development secret in a production deployment.

## Run the project

```powershell
python .\src\manage.py migrate
python .\src\manage.py check
python .\src\manage.py runserver
```

Open <http://127.0.0.1:8000/> for the staff portal, or
<http://127.0.0.1:8000/admin/> for Django administration.

## Run tests

```powershell
python .\src\manage.py test clinic.tests
```

Database model tests are available under `src/clinic/tests/`. More tests should
be added with each future application and workflow.

The project implements M03 authentication and authorization, the M04 shared
interface shell, M05 demographic patient management, M06 healthcare staff
management, M07 appointment management, M08 scheduled in-app appointment
reminders, and M09 clinician-scoped consultation and medical history. Reminder
generation requires an external scheduler; see `docs/appointment_reminders.md`.
Nurses have a dedicated dashboard, read-only access to active demographic
records and appointment details, queue check-in/call actions, and an
appointment-linked observation workflow. They cannot edit patient
demographics, appointment schedules, or clinician consultations.
See `docs/authentication_and_authorization.md`, `docs/patient_management.md`,
`docs/database_backup.md`, and the milestone reports in `reports/` for behavior
and verification evidence. Explicit SQLite backup and isolated restore commands
are available; backup policy and production recovery objectives remain subject
to approval.

See `docs/clinic_queue_management.md`, `docs/role_specific_reports.md`,
`docs/appointment_reminder_email.md`, and
`docs/backup_recovery_demonstration.md` for the added workflows and their
operational boundaries. Apply the queue and reminder-delivery migration before
using queue pages or sending email reminders.

## Planned milestones

1. **Milestone 00 — Project foundation and development environment**
2. **Milestone 01 — Requirements confirmation and domain design** (approved)
3. **Milestone 02 — Database design and configuration**
4. **Milestone 03 — Authentication and role-based access** (implemented)
5. **Milestone 04 — Base interface and navigation** (implemented; see
   `reports/MILESTONE_04_REPORT.md`)
6. **Milestone 05 — Patient registration and management** (implemented; see
   `reports/MILESTONE_05_REPORT.md`)
7. **Milestone 06 — Healthcare staff management** (implemented; see
   `reports/MILESTONE_06_REPORT.md`)
8. **Milestone 07 — Appointment management** (implemented; see
   `reports/MILESTONE_07_REPORT.md`)
9. **Milestone 08 — Appointment reminders** (implemented with periodic
   external scheduler invocation; staff email delivery is a separate explicit
   operation)
10. **Milestone 09 — Consultation and medical history** (implemented with
    clinician-scoped access; nursing observations are implemented)
11. **Milestone 11 — Dashboard and appointment reporting** (initial operational
    scope implemented; patient-registration and clinical reporting remain
    deferred pending requirements approval)

M01 remains the approved requirements baseline. Reminder reconciliation is not
automatically run by Django; deployments configure its scheduler separately.
Email reminders require a separately configured email backend and an explicit
delivery command. The synthetic recovery demonstration does not access clinic
records.
