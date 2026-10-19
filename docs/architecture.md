# Architecture Overview

## Project layout

The project is organized as a Django application with the main project package under `src/config` and the domain application under `src/clinic`.

## Core authentication components

- `src/config/settings.py` configures Django authentication, security middleware, password validators, and login redirects.
- `src/config/urls.py` exposes the authentication routes and the project-level 403 handler.
- `src/clinic/auth_urls.py` contains the path definitions for login, logout, password management, and staff administration.
- `src/clinic/auth_views.py` implements the authentication and admin-protected view logic.
- `src/clinic/auth_forms.py` contains the staff login form, password reset behavior, and staff-management validation/search forms.
- `src/clinic/authentication.py` houses reusable server-side decorators for active staff membership and role enforcement.
- `src/clinic/appointment_urls.py`, `appointment_views.py`, and
  `appointment_forms.py` implement the M07 scheduling interface using the
  existing appointment, patient, staff, and audit models.
- `src/clinic/models/organization.py` defines the existing `Department` and
  `StaffProfile` models; M06 reuses the many-to-many department relationship
  without adding a duplicate model.

## Data model integration

The authentication layer continues to use the existing Django user model and the `StaffProfile` relationship:

- `User` remains the built-in Django user type.
- `StaffProfile` is a one-to-one relationship to the user.
- `StaffProfile.role` stores the approved staff role.
- `StaffProfile.is_active` prevents inactive staff from signing in even when their Django user account is active.

## Security boundaries

- The login layer validates users before granting a session.
- Protected pages are guarded by login-required or role-required decorators.
- Account-management actions are only accessible to administrators.
- The administrator-only staff directory supports role/status filters,
  server-side search, profile viewing/editing, department assignment, and
  POST-only activation/deactivation. Active state is synchronized between the
  staff profile and its linked Django user.
- The application Administrator role does not grant Django `is_staff` or
  `is_superuser`.
- Patient demographic pages use server-side role decorators and retain related
  records through the existing `Patient` model and its protected foreign keys.
- Non-admin requests are rejected with HTTP 403.
- Password validation follows Django's configured security validators.

## Patient management

`src/clinic/patient_urls.py`, `patient_views.py`, and `patient_forms.py`
implement M05 patient demographics using the existing `Patient` model. The
views support listing, searching, registration, profile display, editing, and
administrator-only archive/restore. The patient identifier remains the
existing generated, unique UUID-based value. Patient pages do not expose
clinical notes or create appointment and consultation workflows.

The approved M01 requirements define the four staff roles and the current
patient-management permission boundaries for the project. Administrators and
receptionists can manage approved demographic records; clinicians and nurses
remain restricted from M05 patient routes unless the care-assignment scope is
approved and implemented separately. This boundary is enforced server-side as
documented in `docs/patient_management.md`.

## Appointment management and reminders

M07 adds appointment create/list/detail/edit/reschedule/cancel workflows
without duplicating the existing `Appointment` model or changing the database
schema. Administrators and Receptionists manage scheduling; Clinicians can
view only appointments assigned to themselves; Nurses have no appointment
route access. Forms select existing active patients and clinicians, derive
the end time from a configurable slot duration, and reject overlapping
intervals for the same patient or clinician. Reschedules and cancellations
are recorded using the existing `AuditEvent` model. M08 adds in-app reminder
generation and reconciliation through the existing `AppointmentNotification`
model and `reconcile_appointment_reminders` command. A deployment scheduler
must invoke the command periodically; Django does not run it automatically.
Attendance, completion, and missed-state transitions remain deferred because
the approved workflow does not yet specify their rules or responsible roles.

M09 reuses the existing `Consultation` and `MedicalHistoryEntry` models to
provide consultation creation/detail and a separate patient history view.
Clinical access is restricted to active clinicians with an assigned,
non-cancelled appointment or an existing authored clinical record. Appointment
selection is limited to the same patient and clinician and the model's
cross-record validation is run by the form. Creation is audited without
including clinical text in event metadata. Consultation amendments are limited
to the original clinician; an additive `ConsultationRevision` record captures
the prior fields and actor before the current consultation is updated. Separate
longitudinal history entries remain append-only. Nurse documentation remains
outside this implementation because a nurse assignment basis and nursing-note
workflow are not implemented.

## Milestone scope boundaries

M03 established the authenticated staff model, protected routes, and role
enforcement rules. M04 added the shared interface shell and responsive
navigation. M05 added patient demographics. M06 expands staff management using
the existing user, profile, department models, and approved role matrix.
Reporting and richer dashboards remain outside the implemented milestone
scope. M09 provides the scoped consultation and medical-history workflows
described above.
