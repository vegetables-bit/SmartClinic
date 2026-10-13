# Milestone 05 Report

## 1. Objective

Implement patient registration and demographic management using the existing
`clinic.Patient` model, the approved M01 role model, M03 authentication and
authorization, and the M04 shared interface. M06 and later workflows remain
out of scope.

## 2. Existing files inspected

Inspected the actual workspace and Git state. The repository had no commits;
project files were already untracked, and no existing files were reverted.

Reviewed:

- `README.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/role_permission_matrix.md`
- `docs/database_design.md`
- `docs/authentication_and_authorization.md`
- `reports/MILESTONE_02_REPORT.md`
- `reports/MILESTONE_03_REPORT.md`
- `reports/MILESTONE_04_REPORT.md` (created before M05 implementation because
  it was missing)
- `src/clinic/models/patients.py`
- `src/clinic/models/appointments.py`
- `src/clinic/models/clinical.py`
- `src/clinic/migrations/0001_initial.py`
- `src/clinic/authentication.py`
- `src/clinic/auth_urls.py`
- `src/clinic/auth_views.py`
- `src/config/settings.py`
- `src/config/urls.py`
- Existing auth templates and `src/static/clinic/css/app.css`
- Existing tests under `src/clinic/tests/`

`docs/ui_design.md` was not present. The patient model already contains the
unique generated identifier, demographic fields, `is_archived`, and timestamp
fields. No schema change was needed.

## 3. Features implemented

- Patient list, profile, registration, and demographic editing.
- Search by case-insensitive partial patient identifier, name, or phone number.
- Active patients shown by default, with archived-only and all-record filters.
- Pagination of 25 records per page.
- Patient identifier generation using the existing `PT-` UUID4 scheme. A
  collision is retried up to five times; exhaustion returns a safe 503 form
  response and logs no patient data.
- Administrator-only POST archive and restore operations. Archive is a
  reversible flag change, not deletion; related appointments/history remain.
- Responsive pages reuse the M04 base, messages, CSS tokens, buttons, panels,
  and table components.
- Profile and list pages show demographics only; no clinical notes, history,
  or appointment information is exposed.
- No patient deletion action and no M06+ functionality.

## 4. Patient fields and validation rules

The form uses existing model fields:

- `patient_identifier`: generated, unique, non-editable.
- `full_name`: required; whitespace-only values are rejected by form
  validation.
- `date_of_birth`: optional; future dates are rejected. Age is not stored.
- `phone_number`: optional, bounded by the existing model field length.
- `address`: optional.
- `emergency_contact_name` and `emergency_contact_phone`: optional.
- `is_archived`, `created_at`, and `updated_at`: system-managed.

At the M05 implementation point, the existing model did not yet contain
`gender`, so the M05 form/report reflected that incomplete schema. The project
owner subsequently clarified that gender is required by approved M01; M06
implemented it in the model, migration, forms, templates, and tests. Phone-
number formatting, duplicate patient matching, and emergency-contact pairing
remain narrower implementation details not specified by the approved baseline.

## 5. Search behavior

Search input is stripped, limited to 100 characters, and rejects control
characters. Queries are composed with ORM `Q` filters and are not interpolated
into SQL. The status filter accepts only `active`, `archived`, and `all`.
Malformed search input returns the list with field feedback and HTTP 400.
Results use Django pagination, with 25 patients per page.

## 6. Authorization and privacy controls

The approved M01 requirements and role matrix define the four staff roles and
the patient-management boundary for the current project. The M05
implementation follows that approved scope without inventing additional
patient-care duties.
The current boundary is:

- Administrator and receptionist: patient demographic list/search, view,
  register, and edit.
- Administrator only: archive and restore.
- Clinician and nurse: denied all M05 patient routes until access scope and
  care-assignment rules are approved.
- No M05 page exposes clinical notes, consultation data, appointments, or
  longitudinal history.

All patient routes use the existing active-staff and role decorators.
Archive/restore are POST-only and CSRF-protected. Unknown identifiers return
404. The database's existing protected foreign keys preserve related records.
These permissions implement the approved role-permission matrix and are
enforced server-side.

## 7. Files created or modified

Created:

- `docs/patient_management.md`
- `reports/MILESTONE_04_REPORT.md`
- `reports/MILESTONE_05_REPORT.md`
- `src/clinic/patient_forms.py`
- `src/clinic/patient_urls.py`
- `src/clinic/patient_views.py`
- `src/clinic/tests/test_patient_management.py`
- `src/templates/clinic/patients/patient_list.html`
- `src/templates/clinic/patients/patient_form.html`
- `src/templates/clinic/patients/patient_profile.html`

Modified:

- `README.md`
- `docs/architecture.md`
- `docs/role_permission_matrix.md`
- `src/config/urls.py`
- `src/static/clinic/css/app.css`
- `src/templates/clinic/auth/base.html` (patient navigation; also repaired the
  duplicate M04 content-block defect found during verification)

## 8. Dependencies

No dependencies were added or changed. No migration was added or altered.

## 9. Commands executed

Commands ran on 2026-10-13 from `src` with the project virtual environment and
a temporary test-only `DJANGO_SECRET_KEY`:

```powershell
$env:DJANGO_SECRET_KEY = 'm05-test-only'
..\.venv\Scripts\python.exe .\manage.py test clinic.tests.test_patient_management --verbosity 2
..\.venv\Scripts\python.exe .\manage.py test clinic.tests.test_patient_management --verbosity 1
..\.venv\Scripts\python.exe .\manage.py test clinic.tests --verbosity 1
..\.venv\Scripts\python.exe .\manage.py check
..\.venv\Scripts\python.exe .\manage.py makemigrations --check --dry-run
```

## 10. Automated test results

- Focused patient-management suite: **19 tests passed**.
- Complete `clinic.tests` suite: **67 tests passed**, covering existing M02
  model tests, M03 authentication/authorization tests, and M05 patient tests.
- Tests use Django's isolated test database and fictional data only.

An initial M04 regression run exposed a duplicate `{% block content %}` in the
shared base template; it was corrected, then the pre-M05 suite passed all 48
tests. An initial M05 focused run exposed that an empty GET query was treated as an
unbound invalid search form and that an assertion helper assumed HTTP 200 for
the expected safe 503 identifier-generation response. The list now validates
the actual GET data, and the assertion checks the error response directly. The
subsequent focused run passed 18 tests; after adding a direct POST authorization
test, the final focused run with verbosity 1 passed all 19 tests.

## 11. Django system-check results

- `manage.py check`: **System check identified no issues (0 silenced)**.
- `manage.py makemigrations --check --dry-run`: **No changes detected**.

## 12. Problems encountered and resolutions

- **Missing M04 report:** created `reports/MILESTONE_04_REPORT.md` using the
  current implementation and fresh test/system-check evidence; no historical
  M04 results were fabricated.
- **M04 duplicate content block:** fixed the shared base template after the
  first fresh regression run found it prevented template compilation.
- **Empty GET binding:** changed the patient search form to bind the request's
  actual GET data, making the initial unfiltered list valid.
- **Identifier collisions:** collision checks, transactional insertion, and
  bounded retries prevent duplicate identifiers; exhausted retries return a
  user-safe error instead of a database exception.

## 13. Limitations and deferred features

- The approved M01 role model is enforced consistently.
  Clinician/nurse patient access remains intentionally restricted until a
  separate care-assignment scope is approved and implemented.
- The existing Patient model includes the approved `gender` field and the
  database schema was reconciled to match it during M06 verification.
- Patient duplicate detection, identifier-format policy, phone normalization,
  and emergency-contact completeness rules remain unresolved.
- There is no patient deletion, patient portal, appointment, consultation,
  clinical-history workflow, reminder, dashboard, or reporting feature.
- No browser-based visual regression or accessibility audit was run.
- M06 and later milestones have not been started.

## 14. Acceptance checklist

| Criterion | Result |
|---|---|
| Patient registration works with generated unique identifier | PASS |
| Required full-name and future-date validation | PASS |
| Existing database uniqueness constraint retained and tested by M02 suite | PASS |
| Patient records can be listed and viewed | PASS |
| Patient demographics can be edited | PASS |
| Search supports identifier, name, and phone | PASS |
| Patient list pagination works | PASS |
| Archive and restore preserve related records | PASS |
| Archive/restore use POST and require CSRF | PASS |
| Server-side role permissions tested | PASS |
| Unauthenticated requests are denied; invalid identifiers return 404 | PASS |
| M04 shared layout is reused | PASS |
| Existing M02 and M03 tests continue to pass | PASS |
| New M05 tests pass | PASS |
| Django system checks pass | PASS |
| Documentation matches model and implementation | PASS |
| Approved gender policy/schema | NOT TESTED — no model field or approved policy exists |
| Browser visual regression/accessibility audit | NOT TESTED |
| M06 and later features remain unimplemented | PASS |

## 15. Instructions for testing the module

Use fictional test data. From the repository root, run:

```powershell
$env:DJANGO_SECRET_KEY = 'local-test-only'
.\.venv\Scripts\python.exe .\src\manage.py test clinic.tests
.\.venv\Scripts\python.exe .\src\manage.py check
```

After signing in as an active administrator or receptionist, open
`/patients/` to search/list records or `/patients/register/` to register one.
Administrator-only archive and restore controls appear on the patient profile.
Use the existing staff-account mechanism to provision local staff accounts;
do not use real patient information.

## 16. Recommended next milestone

M06 should not begin until M05 is reviewed and the project owner/supervisor
confirms patient-role permissions, gender requirements, and any outstanding
patient data policies. M06 has not been started in this work.
