# Patient Registration and Management

## Scope and approved patient-management boundary

M05 implements approved patient demographic management on the existing Django
`Patient` model. The approved M01 role model defines the four staff roles, and
this module enforces the current patient-management boundary:

- Administrators and receptionists can list/search, view, register, and edit
  patient demographics.
- Only administrators can archive and restore records.
- Clinicians and nurses are denied M05 patient routes unless a separate
  care-assignment scope is approved and implemented.
- No clinical notes, consultation details, appointment data, or medical-history
  entries are displayed by M05.

This is the project's implemented patient-management boundary and is enforced on
the server side.

## Patient fields

The form uses the fields already present in `clinic.Patient`, with the required
`gender` field now included as part of the approved demographic set:

| Field | Required | Validation / behavior |
|---|---:|---|
| Patient identifier | Generated | Existing `PT-` plus uppercase UUID4 hex strategy; unique in the database and not editable by staff. Generation collision is retried up to five times and failure returns a safe message without creating a record. |
| Full name | Yes | Required by the form and existing model/database constraint; whitespace is stripped by Django's form field. |
| Gender | Yes | Required choice field with values: Female, Male, Non-binary, Prefer not to say. |
| Date of birth | No | Optional; future dates are rejected. Age is not stored. |
| Phone number | No | Optional, limited by the existing model field's 30-character length. |
| Address | No | Optional. |
| Emergency contact name | No | Optional. |
| Emergency contact phone | No | Optional, limited by the existing model field's 30-character length. |
| Archived state | System-managed | Existing `is_archived` flag; controlled only through administrator POST actions. |
| Created/updated timestamps | System-managed | Existing timestamp fields. |

The approved patient demographic set includes `gender` as a required field. The
project has been updated to store the chosen value and render it consistently
in patient list and profile views.

## Search and listing

The patient list supports case-insensitive partial search across patient
identifier, full name, and phone number using Django ORM `Q` expressions. User
input is validated (maximum 100 characters, with control characters rejected)
and is never interpolated into SQL.

Active patients are shown by default. A validated status selection supports
archived-only and all records. Results are paginated at 25 rows per page. The
list exposes demographics appropriate to the interim receptionist/admin
boundary and does not include clinical notes or emergency contact details.

## Routes and behavior

Routes are namespaced as `clinic_patients` under `/patients/`:

- `/patients/` — active list, filters, search, and pagination.
- `/patients/register/` — register a patient.
- `/patients/<patient_identifier>/` — demographic profile.
- `/patients/<patient_identifier>/edit/` — edit demographics.
- `/patients/<patient_identifier>/archive/` — administrator-only POST archive.
- `/patients/<patient_identifier>/restore/` — administrator-only POST restore.

No permanent delete is offered. Archive/restore preserve Patient rows and
related appointment or clinical foreign-key records. Unknown identifiers
return a 404 response. All patient routes require active staff authentication
and permitted roles; state changes require POST and CSRF.

## Tests and local verification

Run from the repository root in PowerShell:

```powershell
$env:DJANGO_SECRET_KEY = 'local-test-only'
.\.venv\Scripts\python.exe .\src\manage.py test clinic.tests
.\.venv\Scripts\python.exe .\src\manage.py check
```

Automated tests use fictional records in Django's isolated test database.
