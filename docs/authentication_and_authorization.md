# Authentication and Authorization

## Scope

The project uses Django's built-in authentication system and the existing
`StaffProfile` design. Staff authentication, role enforcement, administrator-
only staff management, and patient demographic management are implemented.
Appointment and consultation workflows remain outside the implemented
milestone scope.

## Authentication flow

- The project continues to use Django's built-in `User` model and the
  one-to-one `StaffProfile` relationship.
- Staff sign-in uses `StaffLoginView` and `StaffAuthenticationForm`.
- Login accepts a staff username, email address, or a unique
  `StaffProfile.staff_identifier` value when present.
- Authentication rejects inactive Django users, missing staff profiles, and
  inactive staff profiles.
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
- `/accounts/password/change/` — authenticated active staff.
- `/accounts/staff/` — searchable, filtered, paginated directory; administrator.
- `/accounts/staff/create/` — staff registration; administrator.
- `/accounts/staff/<profile_id>/` — individual staff profile; administrator.
- `/accounts/staff/<profile_id>/edit/` — staff details and role editing;
  administrator.
- `/accounts/staff/<profile_id>/status/` — POST-only activate/deactivate;
  administrator.

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

## Security controls

- CSRF middleware and template tokens protect all state-changing forms.
- Login, role, and active-profile checks are server-side.
- Django password hashing and configured password validation are used.
- Staff creation does not grant Django admin-site or superuser privileges.
- Account edits and status changes use database transactions.
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
