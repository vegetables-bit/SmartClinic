# Milestone 06 Report — Healthcare Staff Management

## 1. Objective and scope

Implement staff directory, staff registration, profile viewing/editing,
department assignment, and account activation/deactivation using the existing
Django `User`, `StaffProfile`, and `Department` models. Preserve M01 as the
approved baseline, enforce the approved four-role permission matrix, retain
existing patient data and accounts, and do not start M07.

## 2. Existing functionality inspected

Before implementation, the repository already had:

- the built-in Django user model and a one-to-one `StaffProfile`;
- four approved roles: Administrator, Receptionist, Doctor/Clinician, and Nurse;
- an existing `Department` model with a many-to-many profile relationship;
- administrator-only account creation and editing forms/views;
- password validation, login checks, active-staff guards, and last-admin
  demotion protection;
- shared authenticated navigation and basic account list/form templates;
- automated authentication and account-management tests.

Missing or incomplete were a searchable/paginated staff directory, staff profile
page, generated staff identifiers for form-created accounts when omitted,
case-insensitive email uniqueness validation, restricted active-department
assignment, and a separate POST-only activation/deactivation workflow with
self-deactivation protection.

## 3. Features implemented

- Administrator-only directory with server-side search over staff identifier,
  username/name, email, phone, and department; role/status filters; and
  25-record pagination.
- Staff registration links a Django user to a `StaffProfile`, validates required
  account fields/password, prevents duplicate usernames, email addresses, and
  identifiers (case-insensitively), and assigns a unique `ST-` UUID identifier
  when none is provided.
- Staff profile view displays only needed identity/profile information and
  never exposes passwords or password hashes.
- Staff editing updates account identity, approved role, identifier, phone,
  and existing department membership.
- Department choices are limited to active existing `Department` rows.
- POST-only, CSRF-protected activation/deactivation updates both
  `StaffProfile.is_active` and linked `User.is_active` atomically. Self-
  deactivation is denied; the last active administrator cannot be deactivated
  or demoted. Staff records are retained.
- All directory, profile, edit, create, and status endpoints enforce the
  Administrator role server-side. The application role does not grant Django
  `is_staff` or `is_superuser`.
- Existing authenticated navigation now exposes a Staff directory link only
  to administrators.
- Invalid form values display visible field/non-field errors. Concurrent
  uniqueness conflicts are converted to a safe form error without returning
  database details.
- No appointments, consultations, reminder, reporting, or dashboard workflows
  were added.

## 4. Role and permission decisions

The approved matrix in `docs/role_permission_matrix.md` remains authoritative.
Staff directory/profile/create/edit/role/department/status operations remain
Administrator-only. Receptionists, clinicians, and nurses can sign in and
change their own passwords, but direct requests to staff administration return
403. Staff deactivation is reversible and does not delete the user or profile.
No Django superuser privileges are assigned to the Administrator application
role.

M01 remains approved. Narrow implementation details not prescribed at field or
workflow level are documented as technical choices without changing the
approved baseline.

## 5. Files created or modified

Created:

- `src/templates/clinic/auth/staff_account_profile.html`

Modified:

- `src/clinic/auth_forms.py`
- `src/clinic/auth_views.py`
- `src/clinic/auth_urls.py`
- `src/clinic/tests/test_authentication.py`
- `src/templates/clinic/auth/base.html`
- `src/templates/clinic/auth/staff_account_list.html`
- `src/templates/clinic/auth/staff_account_form.html`
- `src/templates/clinic/auth/staff_home.html`
- `src/static/clinic/css/app.css`
- `docs/authentication_and_authorization.md`
- `docs/role_permission_matrix.md`
- `docs/architecture.md`
- `docs/domain_model.md`
- `docs/database_design.md`
- `docs/requirements.md`
- `README.md`
- `reports/MILESTONE_00_REPORT.md`
- `reports/MILESTONE_01_REPORT.md`
- `reports/MILESTONE_02_REPORT.md`
- `reports/MILESTONE_05_REPORT.md`
- `reports/MILESTONE_06_REPORT.md`

The temporary browser-verification settings module and its disposable SQLite
database were removed after the browser checks.

## 6. Database and migrations

- No model or migration changes were needed for staff management.
- `makemigrations --check --dry-run` reported `No changes detected`.
- No migration was edited or deleted.
- The existing patient-gender migration `0003_patient_gender_reconcile.py`
  remains in place; it was applied as part of migrating the disposable browser
  verification database.
- The project's existing development database, receptionist account, and
  patient records were not modified for browser verification.

## 7. Automated testing and Django checks

Executed from the repository root using `.venv\Scripts\python.exe` and a
runtime-only `DJANGO_SECRET_KEY`:

```powershell
.\.venv\Scripts\python.exe .\src\manage.py test clinic.tests --verbosity 1
.\.venv\Scripts\python.exe .\src\manage.py check
.\.venv\Scripts\python.exe .\src\manage.py makemigrations --check --dry-run
```

Actual results:

- `clinic.tests`: **PASS**, 73 tests ran in 5.641 seconds; `OK`.
- `manage.py check`: **PASS**, `System check identified no issues (0 silenced)`.
- `makemigrations --check --dry-run`: **PASS**, `No changes detected`.

The suite covers successful staff registration and persistence, generated and
duplicate identifiers, duplicate accounts/emails, profile edit and department
assignment, active-department validation, directory search/filter/pagination,
profile privacy, all-role authorization denial, activation/deactivation, login
rejection after deactivation, CSRF, and existing patient/authentication
regressions.

## 8. Browser verification evidence

Browser verification used a disposable SQLite database, fictional users and
departments, and the actual local Django application on a separate port. This
avoided changing the project database or existing account credentials.

Verified workflows:

- Signed in as a fictional active Administrator and opened the staff directory.
- Submitted an invalid staff registration and observed visible server-side
  required-field errors.
- Registered a fictional Nurse with no supplied identifier; the profile
  displayed its generated `ST-` identifier and assigned department.
- Opened the new profile, edited its name, reassigned its department, and
  confirmed both updates on the profile page.
- Deactivated the Nurse using the profile POST action; status changed to
  Inactive and a subsequent login attempt was rejected with the generic
  authentication error. Reactivated the record.
- Signed in as a fictional Receptionist, confirmed no Staff directory link was
  present, and confirmed a direct request to `/accounts/staff/` returned 403.
- Registered a fictional patient as that Receptionist; the app redirected to
  the patient profile, showed a success notification, and displayed the saved
  Gender value.

Responsive/accessibility checks:

- Desktop viewport: 1440 × 900.
- Tablet viewport: 768 × 1024.
- Mobile viewport: 390 × 844.
- Staff directory was visually checked at all three sizes. The compact
  navigation and filter controls reflowed; the wide data table stayed inside
  its horizontal-scroll container on narrow viewports.
- Registration/profile workflows were exercised at desktop size. The staff
  form returned visible inline errors on invalid submission.
- Keyboard Tab navigation showed a visible 3 px gold focus outline with 3 px
  offset.
- Browser-computed body text/background contrast was 14.70:1; white text on the
  primary button color was 7.02:1.
- Viewport screenshots were captured through the browser tool for desktop,
  tablet, and mobile visual inspection; they are not committed project files.

Limitation: active administrator and receptionist accounts exist in the
project's development database, but their credentials were not available in
the shared browser session. No existing password was changed. Equivalent
administrator and receptionist role workflows were tested using fictional
accounts in the disposable database. The specifically requested sign-in using
the existing receptionist account therefore remains pending.

## 9. Known limitations and unfinished work

- The existing development receptionist credential could not be used in this
  browser session. To complete that final check locally, use the existing
  receptionist's known credentials without changing them and verify that
  `/accounts/staff/` returns 403. If no administrator credential is available,
  have the project owner provision an authorized verification account locally;
  do not reset the receptionist password or expose credentials in reports.
- No UI to create or deactivate departments was added; staff assignment uses
  the existing department data and model.
- Audit-event generation remains outside this milestone's implemented behavior.
- M07 and later workflows remain unimplemented.

## 10. Acceptance checklist

| Criterion | Result | Evidence |
|---|---|---|
| Directory, search/filter, empty state, and pagination | PASS | Automated tests and browser directory view |
| Staff registration, persisted user/profile, and unique identifier | PASS | Automated tests and browser-created fictional Nurse |
| Profile viewing/editing | PASS | Tests and browser profile/edit workflow |
| Department assignment and validation | PASS | Tests and browser reassignment |
| Approved role enforcement on sensitive routes | PASS | Direct-request role tests and Receptionist browser 403 |
| Activation/deactivation and inactive login denial | PASS | Tests and browser status/login workflow |
| CSRF on state-changing staff operations | PASS | Enforced-CSRF automated test |
| No superuser grant to application Administrator | PASS | Account-creation test |
| Patient/gender regression | PASS | Full clinic tests and browser patient creation/profile |
| Django checks and migration consistency | PASS | Commands and actual outputs above |
| Responsive, keyboard, and contrast checks | PASS | Browser sizes, focus, and contrast measurements above |
| Existing receptionist login in browser | NOT TESTED | Credentials unavailable; no password changed |
| M07 started | PASS — NOT STARTED | No M07 implementation changes |

## 11. Instructions for testing locally

Set the project secret key in PowerShell without storing it in source:

```powershell
$env:DJANGO_SECRET_KEY = (& .\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
.\.venv\Scripts\python.exe .\src\manage.py test clinic.tests --verbosity 1
.\.venv\Scripts\python.exe .\src\manage.py check
.\.venv\Scripts\python.exe .\src\manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe .\src\manage.py runserver 127.0.0.1:8000
```

Sign in with an authorized Administrator to exercise the staff directory.
Use a separately authorized Receptionist account to confirm direct staff
management requests are denied and patient registration remains permitted.

## 12. Final status

**Partially Complete.** The staff-management implementation, automated
regression suite, Django checks, migration check, and browser workflows passed.
The existing receptionist-account browser sign-in requested by the milestone
could not be performed because its credential was unavailable. No existing
account or patient data was changed. Complete that one manual check locally
before marking M06 fully complete. M07 has not been started.
