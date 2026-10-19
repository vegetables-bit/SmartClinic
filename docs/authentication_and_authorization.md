# Authentication and Authorization

## Scope

The project uses Django's built-in authentication system and the existing
`StaffProfile` design. Staff authentication, role enforcement, administrator-
only staff management, patient demographic management, M07 appointment
management, M08 appointment reminders, and M09 clinician-scoped consultation
and history workflows are implemented.

## Authentication flow

- The project continues to use Django's built-in `User` model and the
  one-to-one `StaffProfile` relationship.
- Staff sign-in uses `StaffLoginView` and `StaffAuthenticationForm`.
- Login accepts a staff username, email address, or a unique
  `StaffProfile.staff_identifier` value when present.
- Authentication rejects inactive Django users, missing staff profiles, and
  inactive staff profiles.
- Successful application sign-in uses the Smart Clinic staff-home destination,
  whose dashboard heading reflects the authenticated application role. A
  safe `next` destination is honored unless it targets Django Administration
  for an account without Django `is_staff` access; that case falls back to the
  Smart Clinic dashboard.
- Django Administration is a separate Django permission surface. The
  application Administrator role does not grant `is_staff` or `is_superuser`,
  and the public staff portal links to Smart Clinic sign-in rather than
  directing application staff to `/admin/`.
- Logout is POST-only.
- Password change uses Django's password validators.
- Password reset uses Django's built-in views and the configured development
  email backend; no real outgoing mail service is claimed.

## Role model

The approved roles are defined in `StaffProfile.Role` and remain the
application's single source of truth:

- Administrator
- Receptionist
- Doctor/Clinician
- Nurse

The database constraint validates role values. The
`roles_required`/`administrator_required` decorators enforce permissions on
the server. Assigning the Administrator application role does not set Django
`is_staff` or `is_superuser`.

## Protected endpoints

- `/accounts/home/` — authenticated active staff.
- `/accounts/settings/` — authenticated active staff; links to self-profile,
  password-change, and (for Administrators only) existing staff-account
  management.
- `/accounts/settings/profile/` — authenticated active staff; users may edit
  only their own first/last name, email, and phone number. Username, role,
  staff identifier, and departments are displayed but are not changed through
  this self-service form.
- `/accounts/password/change/` — authenticated active staff.
- `/accounts/staff/` — searchable, filtered, paginated directory; administrator.
- `/accounts/staff/create/` — staff registration; administrator.
- `/accounts/staff/<profile_id>/` — individual staff profile; administrator.
- `/accounts/staff/<profile_id>/edit/` — staff details and role editing;
  administrator.
- `/accounts/staff/<profile_id>/status/` — POST-only activate/deactivate;
  administrator.
- `/appointments/` — appointment directory, search, filters, pagination;
  administrator/receptionist, plus assigned appointments for clinicians.
- `/appointments/create/` — create appointment; administrator/receptionist.
- `/appointments/<appointment_id>/` — details; administrator/receptionist or
  the assigned clinician.
- `/appointments/<appointment_id>/edit/` — edit/reschedule Scheduled or
  Confirmed appointment; administrator/receptionist.
- `/appointments/<appointment_id>/cancel/` — POST-only cancellation of
  Scheduled or Confirmed appointment; administrator/receptionist.
- `/clinical/patients/<patient_identifier>/history/` — consultation and
  longitudinal history for a patient under the active clinician's assigned
  care scope; Doctor/Clinician.
- `/clinical/patients/<patient_identifier>/consultations/new/` — consultation
  creation; Doctor/Clinician with assigned-care scope.
- `/clinical/consultations/<consultation_id>/edit/` — amend consultation
  authored by the current clinician; POST/CSRF protected with previous content
  preserved.
- `/clinical/patients/<patient_identifier>/history/new/` — append-only history
  entry creation; Doctor/Clinician with assigned-care scope.
- `/clinical/consultations/<consultation_id>/` — consultation detail for
  clinical staff with an assigned-care basis for the patient; Doctor/Clinician.

Unauthenticated staff are redirected to login. Authenticated staff without the
required role receive HTTP 403. Unknown profile IDs return 404.

## Staff management

The administrator-only staff management workflow:

- searches by staff identifier, username/name, email, phone, and department;
- filters by the four approved roles and active/inactive status;
- paginates directory results;
- creates a linked Django user and `StaffProfile` with a generated unique
  identifier when one is not supplied;
- validates username, email, and staff identifier uniqueness
  case-insensitively before saving;
- validates account passwords using Django's configured password validators;
- assigns only active `Department` records;
- edits identity, role, staff identifier, phone, and department assignments;
- activates/deactivates the `StaffProfile` and linked Django account together
  in a POST/CSRF-protected transaction;
- prevents self-deactivation and prevents demoting the last active
  administrator.

Staff profiles are retained when accounts are deactivated. Passwords and
password hashes are never displayed in staff pages.

The Settings page reuses the existing password-change endpoint and
administrator-only staff-management endpoints. The self-profile endpoint has
no target-user ID parameter and always updates the authenticated user's linked
account and profile; role and authorization data can only be changed through
the existing administrator-protected staff-edit workflow.

## Appointment management (M07)

- Administrators and Receptionists manage all appointments. Clinicians can
  list and view only appointments assigned to their own active profile.
  Nurses have no appointment-route access.
- Appointment creation selects an existing non-archived patient and an active
  clinician account/profile. A generated `AP-` identifier is a display value
  derived from the immutable appointment primary key; the database schema is
  unchanged.
- Appointments store timezone-aware start/end timestamps. The configurable
  `APPOINTMENT_DEFAULT_DURATION_MINUTES` setting defaults to 30 minutes as an
  implementation choice; existing appointment duration is retained on edits.
- Scheduling rejects overlapping half-open time intervals for either the same
  patient or clinician. Cancelled appointments do not block a slot. Validation
  and writes are wrapped in transactions; SQLite cannot enforce interval
  exclusion under every concurrent-writer race.
- Appointment creation, schedule changes, general edits, and cancellations
  write `AuditEvent` records with the actor. Rescheduling metadata preserves
  the prior and new start/end values.
- Only Scheduled and Confirmed appointments can be edited/rescheduled or
  cancelled in M07. Cancellation is POST-only and retains the record and
  cancellation event. Attendance, completion, and missed-state transitions
  are deliberately outside M07 pending their later workflow rules.
- Appointments created from ordinary forms require a reason; the existing
  model retains `blank=True` so pre-existing records remain valid.

## Consultation and medical history (M09)

- Existing `Consultation` and `MedicalHistoryEntry` models are reused. The
  additive `ConsultationRevision` table stores prior content for amendments;
  no duplicate consultation or history tables are introduced.
- Only active Doctor/Clinician profiles can use the clinical routes. Patient
  scope requires an appointment assigned to that clinician that is not
  cancelled, or an existing consultation/history entry authored by them.
- Consultation appointments are optional, but the form only offers
  non-cancelled appointments for the same patient and clinician. Model
  validation also checks the patient/appointment/clinician relationship.
- Consultation and history-entry creation write actor, target, patient
  identifier, and record ID to `AuditEvent` metadata; clinical text is not
  copied into audit metadata.
- Consultations and independent longitudinal history entries are shown
  separately, newest first. New history entries are appended; separate
  history-entry editing/deletion is not provided.
- Administrator and Receptionist clinical access is denied. Nurse clinical
  access is not yet implemented because there is no nurse assignment
  relationship or approved nursing-note workflow in the current schema.
- Consultation amendments are limited to the original clinician. Before
  changing saved content, the system stores a `ConsultationRevision` snapshot
  of the prior time, appointment, and text fields plus the revising clinician.
  Amendment history is visible to clinicians with assigned-care scope.

## Security controls

- CSRF middleware and template tokens protect all state-changing forms.
- Login, role, and active-profile checks are server-side.
- Django password hashing and configured password validation are used.
- Staff creation does not grant Django admin-site or superuser privileges.
- Account edits and status changes use database transactions.
- Appointment authorization, assigned-clinician filtering, status checks,
  schedule conflict validation, audit events, and cancellation are enforced
  server-side.
- Clinical route authorization, patient assignment scope, consultation
  relationship validation, and CSRF-protected clinical writes are enforced
  server-side.
- Patient-management access rules are documented in
  `docs/role_permission_matrix.md` and `docs/patient_management.md`.

## Operational requirements

Before running Django commands, set `DJANGO_SECRET_KEY` through the project's
environment configuration. Development and test data must be fictional.

## Files involved

- `src/clinic/auth_forms.py`
- `src/clinic/auth_urls.py`
- `src/clinic/auth_views.py`
- `src/clinic/authentication.py`
- `src/templates/clinic/auth/*.html`
- `src/clinic/tests/test_authentication.py`
