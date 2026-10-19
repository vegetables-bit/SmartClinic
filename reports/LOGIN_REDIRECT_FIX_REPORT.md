# Login Redirect Fix Report

## Root cause

The Smart Clinic `StaffLoginView` already uses Django's configured
`LOGIN_REDIRECT_URL`, which points to `clinic_auth:staff_home`. The application
has one shared staff-home route, not separate role-specific route names.

The misleading path was the public homepage's **Open admin** link, which went
directly to `/admin/`. Django's built-in admin correctly sends a user who
successfully authenticates there back to `/admin/`; it does not use the Smart
Clinic login view or the clinic dashboard. In addition, a safe same-site
`next=/admin/` value could override the normal application-login destination.

Read-only inspection of the main database found three active application
Administrator profiles linked to active user accounts. All three have
`is_staff=False` and `is_superuser=False`. A separate Django superuser account
has no `StaffProfile`. Therefore the application Administrator role does not
grant Django admin access.

## Fix implemented

- Removed the public homepage link that directed staff to Django Administration;
  Django Administration remains available at `/admin/` to accounts accepted by
  Django's existing admin permission checks.
- Kept the application login's normal Smart Clinic destination and role-aware
  access enforcement.
- If an application login receives a same-site `next` URL resolving to Django
  Administration, it returns a user without Django `is_staff` privileges to
  the Smart Clinic staff dashboard. Other safe `next` URLs continue to use
  Django's standard `LoginView` handling.
- Updated the existing staff dashboard to identify itself by application role
  (for example, “Administrator dashboard”) while preserving the existing
  route, shared interface, and role-specific navigation.
- Reworded the common login page, guest header, and homepage sign-in link to
  clearly serve all four authorized application roles.
- Added regression tests for all four role dashboards, safe and external
  redirects, the Django-admin `next` case, application-role privilege
  boundaries, common login wording, public navigation, and continued
  superuser access to Django Administration.

## Files changed

- `src/clinic/auth_views.py`
- `src/clinic/tests/test_authentication.py`
- `src/templates/clinic/auth/login.html`
- `src/templates/clinic/auth/base.html`
- `src/templates/clinic/auth/staff_home.html`
- `src/templates/home.html`
- `docs/authentication_and_authorization.md`
- `reports/LOGIN_REDIRECT_FIX_REPORT.md`

## Data, accounts, and migrations

- No production or project database records, existing passwords, patient
  records, staff records, appointments, or migrations were changed.
- No model or schema change was made.
- Django application staff-account creation continues to set
  `is_staff=False` and `is_superuser=False`.
- The main database account check was read-only and did not inspect passwords
  or password hashes. It found three active, linked application
  Administrators; a separate first-admin setup is not currently needed.
- If no active application Administrator exists in a local copy, first verify
  that condition against the linked `StaffProfile` and active user flags, then
  run `.\.venv\Scripts\python.exe .\src\manage.py create_staff_admin` with
  `DJANGO_SECRET_KEY` set. This existing interactive command prompts for the
  account details and hidden password input, validates the password, and
  creates a linked Administrator without Django `is_staff` or `is_superuser`
  privileges. Do not run it when an active application Administrator already
  exists.

## Automated verification

Commands were run from the repository root with an ephemeral runtime-only
`DJANGO_SECRET_KEY`:

```powershell
.\.venv\Scripts\python.exe .\src\manage.py test clinic.tests --verbosity 1
.\.venv\Scripts\python.exe .\src\manage.py check
.\.venv\Scripts\python.exe .\src\manage.py makemigrations --check --dry-run
```

Actual results:

- Clinic test suite: **PASS** — 102 tests ran in 10.337 seconds; `OK`.
- Django system check: **PASS** — no issues identified.
- Migration consistency check: **PASS** — `No changes detected`.

The new tests establish that every application role reaches the Smart Clinic
dashboard, which identifies the role; authorized safe `next` URLs still work;
external and non-Django-authorized admin redirects fall back safely; ordinary
application Administrators do not gain Django admin privileges; and a Django
superuser can still access Django Administration.

## Browser verification

The current browser check opened the application login on the main local
server:

- The browser title and heading displayed **Sign in to Smart Clinic**.
- The page header displayed **Secure access for the clinic team**.
- The page explained username, email, or employee-identifier login and retained
  the password-reset link.

A prior browser run against the separate disposable browser database verified
that its fictional Administrator account reached `/accounts/home/`, displayed
**Administrator dashboard**, and was denied access to Django Administration.
That run did not use any main-database account. The current main database has
active linked Administrator accounts, but browser login with one of those
accounts remains unverified because no credentials were provided; no password
was changed or inspected. Automated tests verified all four role dashboard
renderings, application-role privilege boundaries, and Django superuser access
to the admin index.

## Remaining limitations

- The project currently has one Smart Clinic dashboard route, shared by the
  four roles; the dashboard heading and existing actions reflect the signed-in
  role. Separate role-specific dashboard pages and operational summaries are
  outside this redirect fix.
- Browser login with an actual main-database Administrator remains pending
  until authorized credentials are available. The existing passwords were not
  changed.
