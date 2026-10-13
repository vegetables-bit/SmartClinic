# Patient Registration Save Bugfix Report

## Root cause

The patient registration form itself was not failing in its own validation or URL flow. The actual root cause was a database schema drift issue:

- The `Patient` model includes the required `gender` field.
- The active SQLite database table `clinic_patient` did not include the `gender` column.
- When a valid form POST was submitted, Django reached the save step and raised a database `OperationalError` instead of creating the patient record.
- This is consistent with the observed runtime exception: `table clinic_patient has no column named gender`.

The fix was therefore to reconcile the live SQLite schema with the model without resetting existing data or breaking the registration flow.

## Files changed

- `src/clinic/models/patients.py`
- `src/clinic/migrations/0003_patient_gender_reconcile.py`
- `src/clinic/patient_forms.py`
- `src/clinic/patient_views.py`
- `src/config/settings.py`
- `reports/PATIENT_REGISTRATION_SAVE_BUGFIX_REPORT.md`

## Fix implemented

1. Reconciled the database schema by applying a safe migration (`0003_patient_gender_reconcile.py`) that adds the missing `gender` column only when it is absent.
2. Kept existing patient records intact and avoided database resets.
3. Confirmed the registration request reaches the correct URL, uses POST, and passes through Django form validation.
4. Kept the required `full_name` and `gender` handling aligned with the model and approved requirements.
5. Preserved identifier-generation safety: patient IDs are generated with a retry loop and guarded against duplicate generation failures.
6. Confirmed invalid submissions display useful, visible errors instead of silently failing.
7. Confirmed successful registration redirects to the patient profile and displays a success message.

## Database and migration changes

- Added `gender` to the live SQLite schema via a reversible `RunPython` migration when the column is absent.
- The migration is intentionally safe for existing data and does not drop or reset patient records.
- The live schema now matches the model contract used by the form and view layer.

## Test commands and actual results

Executed in the project root with the required Django secret configured:

```powershell
$env:DJANGO_SECRET_KEY = 'dev-secret-key'
python .\src\manage.py test clinic.tests --verbosity 1
python .\src\manage.py check
python .\src\manage.py makemigrations --check --dry-run
```

Actual results:

- `python .\src\manage.py test clinic.tests --verbosity 1` -> Passed
- `python .\src\manage.py check` -> Passed (`System check identified no issues (0 silenced)`) 
- `python .\src\manage.py makemigrations --check --dry-run` -> Passed (`No changes detected`)

Test suite summary:

- Ran 67 tests in 5.945s
- Result: `OK`

## Browser verification evidence

Browser-based checks were performed against the running app and confirmed:

- The patient registration page loads and accepts valid patient input.
- A valid fictional patient successfully creates a record.
- The app redirects to the patient profile page.
- The success notification is visible.
- The patient appears in the patient directory and is viewable.
- Invalid data displays inline validation errors for required fields and date-of-birth constraints.
- The saved patient has the expected `Gender` value and it is displayed correctly on the profile page.

Example observed browser flow:

- URL after successful submit: `http://127.0.0.1:8000/patients/PT-11FECCC9321348C9AEA62BEDBC0C2E7F/`
- Page title: `Browser Test Patient | Smart Clinic`
- Profile displays `Gender: Female`

## Remaining limitations

- This task was intentionally limited to the patient registration save failure and verification.
- No later milestone features or unrelated modules were started.
- Browser verification was performed in the local development environment; no additional browser automation framework was introduced.

## Final assessment

The registration bug was fixed by resolving the schema mismatch rather than by weakening validation or bypassing the save layer. The registration flow now works, the database remains intact, and the relevant Django checks and tests pass.
