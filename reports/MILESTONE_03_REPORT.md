# Milestone 03 Report

## 1. Milestone name and objective

**Milestone 03 — Authentication and Role-Based Access Control**

The objective of this milestone was to implement the foundational authentication and authorization layer for the Smart Clinic project while preserving the existing database design. The work focused on Django's built-in authentication system, staff account administration, role enforcement, and proof that permitted and prohibited access behaves correctly.

## 2. Existing files and architecture inspected

Before changes, the project was inspected for the current Django settings, URL configuration, clinic models, existing migrations, tests, and documentation. The relevant files reviewed were:

- `README.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/role_permission_matrix.md`
- `docs/database_design.md`
- `docs/domain_model.md`
- `reports/MILESTONE_02_REPORT.md`
- `src/config/settings.py`
- `src/config/urls.py`
- `src/clinic/models/organization.py`
- `src/clinic/auth_forms.py`
- `src/clinic/auth_views.py`
- `src/clinic/authentication.py`
- `src/clinic/tests/test_authentication.py`

The baseline confirmed that the project already uses Django's built-in `User` model and an associated `StaffProfile` with a `role` field, reused database constraints, and no custom `AUTH_USER_MODEL` changes.

## 3. Authentication implementation

Django's built-in authentication stack is used for:

- login via Django's `LoginView`
- logout via Django's `LogoutView`
- password change via Django's `PasswordChangeView`
- password reset via Django's built-in reset flow
- CSRF protection on POST forms
- session handling through Django's configured session middleware

The custom `StaffAuthenticationForm` validates the submitted login identifier against the canonical Django username and also accepts the current project staff identifier. It blocks access when either the Django user is inactive or the related `StaffProfile` is inactive or missing.

The login view also ensures that an authenticated user with an inactive account or inactive profile is logged out before access to protected routes continues.

## 4. Role and permission implementation

The role design and permissions remain anchored to the existing `StaffProfile.Role` values:

- `administrator`
- `receptionist`
- `clinician`
- `nurse`

The reusable authorization decorators enforce these restrictions server-side:

- `active_staff_required` ensures a valid, active staff member is authenticated before protected views are rendered.
- `roles_required(*roles)` enforces a staff role check before a view runs.
- `administrator_required` is the admin-only gate used for staff account management endpoints.

These checks are not dependent on template conditions or client-side control hiding.

## 5. Staff account administration

Administrator-only pages were implemented for:

- staff account listing
- staff account creation
- staff account editing
- role assignment
- staff identifier and department assignments
- activation/deactivation

The staff account forms validate duplicate usernames, duplicate staff identifiers, password strength, mismatched confirmation values, and the special case where the last active administrator would be demoted or deactivated. The form logic therefore blocks accidental privilege loss while preserving the database architecture.

## 6. Pages and routes created

The auth routes live in `src/clinic/auth_urls.py` and support:

- login
- logout
- staff home
- password change and completion
- password reset, completion, and confirmation
- staff account list
- staff account create
- staff account edit
- HTTP 403 access denied view

Templates for these screens were placed under `src/templates/clinic/auth/` and remain minimal and focused on the milestone requirement.

## 7. Security controls

The implementation applies the following controls:

- CSRF on state-changing forms
- Django password hashing
- Django password validators
- login-required access on private routes
- role-based checks on admin-only actions
- safe redirect behavior after authentication
- no public staff registration workflow
- no plaintext password exposure in logs or templates
- inactive account rejection during login
- database transaction protection around account updates

Password-reset functionality is documented as development-safe because it uses Django's console email backend, which is suitable for local testing but does not provide production email delivery.

## 8. Files created or modified

- `src/clinic/auth_forms.py`
- `src/clinic/auth_views.py`
- `src/clinic/authentication.py`
- `src/clinic/tests/test_authentication.py`
- `src/clinic/auth_urls.py`
- `src/templates/clinic/auth/*.html`
- `docs/authentication_and_authorization.md`
- `docs/role_permission_matrix.md`
- `docs/architecture.md`
- `README.md`
- `reports/MILESTONE_03_REPORT.md`

## 9. Dependencies added or changed

No additional third-party dependencies were introduced. The milestone uses the existing Django 6.1.2 stack and the SQLite database already configured for the project.

## 10. Commands executed

The following commands were used during validation:

```powershell
$env:DJANGO_SECRET_KEY = 'dev-secret-key'
cd 'c:\Users\MASAMBA\OneDrive\Documents\PROGRAMMING\SmartClinicApp_PatientTracking\src'
python .\manage.py test clinic.tests -v 2
python .\manage.py check
```

## 11. Automated tests and observed results

Actual executed tests:

- `python .\manage.py test clinic.tests -v 2`
- Result: `Found 47 test(s)` and exit code `0`.
- `python .\manage.py check`
- Result: `System check identified no issues (0 silenced).`

The test database was created by Django's test runner, and no real patient data was used.

## 12. Django system-check results

`manage.py check` completed successfully with no issues. This validation confirms that the authentication URLs, forms, middleware, and settings are configured consistently for the current project layout.

## 13. Problems encountered and solutions

A project requirement gap was identified in the authentication form: login was originally designed around the Django username and did not clearly support the unique `StaffProfile.staff_identifier` used by the project. The fix was to normalize the submitted login value against the canonical username and allow the project staff identifier to resolve to the correct user before authentication.

This preserves the existing database pattern without introducing a custom user model or conflicting role definitions.

## 14. Security considerations and limitations

- The system uses Django's default secure auth stack and password hashing.
- Production email delivery is not configured or claimed; password reset execution remains development-safe through the console email backend.
- Authentication is limited to the staff management area and does not create a public self-registration workflow.
- The project does not implement patient, appointment, or consultation management in this milestone.

## 15. Acceptance checklist

| Criterion | Result |
|---|---|
| Existing auth and `StaffProfile` design verified | PASS |
| Login and logout work | PASS |
| Password management works to documented extent | PASS |
| Staff account administration restricted to administrators | PASS |
| Four approved roles supported | PASS |
| Server-side permission checks implemented | PASS |
| Inactive accounts cannot access the app | PASS |
| Unauthorized requests correctly rejected | PASS |
| Authentication forms use security protections | PASS |
| Automated auth and permission tests executed | PASS |
| Existing M02 tests continue to pass | PASS |
| Django system checks pass | PASS |
| Documentation matches actual implementation | PASS |
| M04 not started | PASS |

## 16. Instructions for running and testing authentication

```powershell
$env:DJANGO_SECRET_KEY = 'dev-secret-key'
cd 'c:\Users\MASAMBA\OneDrive\Documents\PROGRAMMING\SmartClinicApp_PatientTracking\src'
python .\manage.py migrate
python .\manage.py test clinic.tests -v 2
python .\manage.py runserver
```

Then open the local app and verify:

- login with a valid username
- login with a valid staff identifier
- invalid credentials show a generic error
- inactive account is rejected
- protected routes redirect unauthenticated users to login
- admin-only account endpoints reject non-admins with HTTP 403

## 17. Recommended next milestone

The next milestone should focus on the base interface and navigation layer for authenticated staff users, while keeping the authentication and authorization rules intact. This should happen only after the current milestone's acceptance criteria are confirmed and retained.
