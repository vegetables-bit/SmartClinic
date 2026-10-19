# Milestone 07 Report — Appointment Management

## 1. Objective and scope

Implement the M07 appointment-management workflow within the approved Smart Clinic architecture:

- appointment model and scheduling data;
- create/list/detail/edit/reschedule/cancel flows;
- conflict prevention for overlapping staff or patient bookings;
- role-aware access enforcement;
- regression coverage for patient, staff, and authentication workflows; and
- evidence from automated tests and browser verification.

This milestone was intentionally scoped to appointment management only and did not start M08 or later milestones.

## 2. Existing functionality inspected

Before implementation, the repository already had:

- the approved four-role staff model: Administrator, Receptionist, Clinician, and Nurse;
- patient management and authentication flows already in place;
- shared authenticated navigation and existing `StaffProfile` / `Department` models;
- a `clinic` app structure with models, views, forms, templates, and tests already established;
- the approved appointment rule notes in the project documentation, which define scheduling logic and a 30-minute default slot duration.

The main gap was that the project had not yet completed the M07 appointment workflow as a validated end-to-end feature set.

## 3. Implementation gaps found

The target gaps were:

- no complete appointment scheduling workflow for patient/staff booking;
- no list/detail/create/edit/cancel routes aligned with the approved role model;
- no server-side conflict validation for same-patient or same-clinician overlaps;
- no appointment permission enforcement in the views and routing;
- no appointment regression tests covering booking, editing, cancellation, and authorization.

## 4. Features implemented

- Appointment model and related status choices, indexes, and validation constraints.
- Appointment form with patient and clinician selection, date/time capture, required reason field, and visible validation errors.
- Appointment creation via POST with server-side validation and redirect to the detail page.
- Appointment list/search page with filters by date, status, clinician, and text query.
- Appointment detail page showing patient, clinician, time, status, and action controls.
- Edit/reschedule flow that validates conflicts and preserves a safe audit trail.
- Cancel flow using POST + CSRF, retaining the record and recording the status change.
- Role enforcement: Administrator and Receptionist can manage appointments; Clinicians can view assigned appointments only; nurses are denied appointment routes.
- Existing navigation and page layout were updated to include appointment access as approved.

## 5. Files created or modified

Created:

- `src/clinic/appointment_forms.py`
- `src/clinic/appointment_urls.py`
- `src/clinic/appointment_views.py`
- `src/clinic/tests/test_appointment_management.py`
- `src/templates/clinic/appointments/appointment_detail.html`
- `src/templates/clinic/appointments/appointment_form.html`
- `src/templates/clinic/appointments/appointment_list.html`

Modified:

- `src/clinic/models/appointments.py`
- `src/clinic/models/__init__.py`
- `src/config/settings.py`
- `src/config/urls.py`
- `src/static/clinic/css/app.css`
- `src/templates/clinic/auth/base.html`
- `src/templates/clinic/patients/patient_profile.html`
- `README.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/domain_model.md`
- `docs/database_design.md`
- `docs/authentication_and_authorization.md`
- `docs/role_permission_matrix.md`

## 6. Data model and migration changes

The project uses an appointment model that stores:

- patient reference;
- clinician reference;
- appointment start and end timestamps;
- reason for visit;
- status;
- cancellation reason and timestamps.

The scheduling model uses a half-open interval check (`appointment_at < end` and `ends_at > start`) to detect overlaps without treating adjacent bookings as conflicts.

The default duration is configured at `APPOINTMENT_DEFAULT_DURATION_MINUTES = 30`, matching the project documentation. This is a project-level development default and remains easy to adjust.

Migration checks were run and no schema drift was detected:

```powershell
$env:DJANGO_SECRET_KEY = 'dev-secret-key'
.\.venv\Scripts\python.exe .\src\manage.py makemigrations --check --dry-run
```

Result:

- `No changes detected`

## 7. Scheduling conflict rules and assumptions

Conflict prevention was implemented with application-level validation to match the approved design and local SQLite constraints:

- same clinician at the same time is rejected;
- same patient at the same time is rejected;
- editing/rescheduling re-runs exactly the same check on the updated appointment;
- cancelled appointments are excluded from conflict checks so they do not block future bookings;
- adjacent bookings are permitted when the intervals do not overlap.

SQLite remains a local-development limitation for some race-condition edge cases, so conflict prevention is enforced in the Django application layer rather than relying on a database-only constraint.

## 8. Role-permission decisions

The approved role matrix remains authoritative:

- Administrator: full appointment-management access.
- Receptionist: create, edit, cancel, and list appointments.
- Clinician: assigned-appointment read access only.
- Nurse: no appointment access in M07.

All write actions are server-side enforced and protected by CSRF. Direct guessed URLs for another clinician's appointment return access denial rather than exposing records.

## 9. Automated test commands and actual results

Executed from the project root with the required runtime secret:

```powershell
$env:DJANGO_SECRET_KEY = 'dev-secret-key'
.\.venv\Scripts\python.exe .\src\manage.py test clinic.tests --verbosity 1
.\.venv\Scripts\python.exe .\src\manage.py check
.\.venv\Scripts\python.exe .\src\manage.py makemigrations --check --dry-run
```

Actual results:

- `clinic.tests`: PASS, `Ran 96 tests in 10.972s`, `OK`
- `manage.py check`: PASS, `System check identified no issues (0 silenced)`
- `makemigrations --check --dry-run`: PASS, `No changes detected`

The suite covers successful appointment creation, persistence, invalid input, same-staff conflict rules, same-patient conflict rules, editing/rescheduling validation, cancellation handling, list/search/filter behavior, role authorization, and regression coverage for patient/staff auth flows.

## 10. Browser verification evidence

Browser verification was performed using the disposable browser database and test accounts configured for the local verification environment.

Verified flows:

- Administrator login succeeded.
- Appointments navigation opened successfully.
- Appointment list rendered and showed records.
- Schedule appointment form loaded and accepted valid patient/clinician selections.
- Appointment creation redirected to the appointment detail page and persisted the new record.
- Overlap prevention was checked against staff and patient conflicts.
- Existing patient and staff-management workflows remained accessible without breaking the core app navigation.

The original project database was not reset or altered for browser verification. The disposable verification database was kept separate from the project’s main development database.

## 11. Known limitations

- This verification used a dedicated disposable browser database rather than the project’s production-style local database.
- The project does not implement later milestone features such as reminder delivery, outcome tracking, or consultation records.
- SQLite remains a local-development limitation for fully race-safe interval enforcement at the DB layer; the application-level checks are the active safeguard.

## 12. Final status

Status: Complete

Justification: the appointment-management features required for M07 were implemented, validated by the project test suite, checked clean by Django, confirmed migration-safe with `makemigrations --check --dry-run`, and validated via browser workflow checks. The work remained scoped to the approved M07 requirements and did not start M08 or later milestone features.
