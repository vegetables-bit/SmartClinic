# Audit logging requirements and approval register

## 1. Purpose and scope

This document records audit logging requirements, their approval status, and
implementation facts. The authentication/session decisions in Section 3.1 are
approved for the current implementation baseline. Other proposed event
coverage, viewer permission, retention, tamper-protection, and operational
decisions remain unapproved unless explicitly stated otherwise below.

The project supervisor may add, modify, or remove requirements. Each future
revision must update this approval record and identify its implementation and
test impact. A later approved revision supersedes the affected earlier
decision; approval of one area does not approve unrelated proposals.

The scope is accountability for selected sensitive changes and security-
relevant outcomes. It does not require logging every page view or routine
record read. Any read-access logging should be selected according to purpose,
privacy impact, and expected event volume.

The existing role names in
[role_permission_matrix.md](./role_permission_matrix.md) are Administrator,
Receptionist, Doctor/Clinician (internal value `clinician`), and Nurse.
Current application permissions remain as documented there; this proposal
does not grant new application or clinical access.

## 2. Existing implementation facts

The `AuditEvent` model stores an optional user actor, a free-form action
string, an automatically populated timestamp, an optional generic target, and
JSON metadata. Its generic target is not a database-enforced foreign key.
Deleting an actor sets the actor reference to null while retaining the event.
The model itself does not automatically write events.

Explicit writers currently cover appointment creation, appointment updates
and rescheduling, cancellation, consultation creation and amendment, and
medical-history entry creation. Covered business writes and their event
creation occur inside database transactions. Existing clinical event metadata
does not copy consultation text; tests verify this for consultation creation
and amendments. No audit viewer, audit URL, audit template, or `AuditEvent`
Django admin registration was found in the Stage 3A inspection.

Stage 3A found no event writers for patient registration/demographic
updates/archive/restore; staff account administration; authentication
success/failure, logout, or password change/reset; reminder reconciliation;
or denied operations. Appointment status transitions other than cancellation
are not currently supported. No established audit retention, viewer-access,
or tamper-protection policy was found.

Evidence and implementation details are documented in
[database_design.md](./database_design.md),
[domain_model.md](./domain_model.md),
[authentication_and_authorization.md](./authentication_and_authorization.md),
and [database_backup.md](./database_backup.md). The findings above describe
the inspected implementation and do not imply that proposed events below
already exist.

### Relationship to existing requirements

This proposal does not replace or narrow the existing FR-17 requirement to
record actions designated sensitive by an approved audit policy. FR-04 and
FR-19 also refer to recording actions “as required” or designated sensitive.
The policy and event scope needed to make those acceptance statements
testable remain unresolved. The matrix below is a candidate decision aid; it
does not designate events as approved or claim the current implementation
satisfies those requirements.

## 3. Event coverage matrix

Except for the approved authentication/session decisions in Section 3.1, the
entries below remain proposals requiring approval. “Actor” means the
authenticated initiating user where one exists. For other proposed
unauthenticated events, do not attribute activity to a fabricated user.
Automated work should use a stable system/task identity and an actor-kind
marker, not impersonate a staff user. Their exact representation requires
approval. Approved anonymous authentication/session events use a null actor.

Common exclusions apply to every row: never store passwords, password-reset
tokens, session identifiers/cookies, secret values, credentials, raw
authentication form submissions, or unnecessary patient/clinical content.
Do not place request bodies, free-form notes, or exception tracebacks in
metadata. Keep metadata small, structured, validated, and limited to fields
approved for that event.

| Category and current status | Proposed events and actor | Minimum target | Permitted metadata and prohibited content | Outcome to record | Priority and approval |
|---|---|---|---|---|---|
| **1. Authentication and session — Approved for the current implementation baseline; implementation tracked below.** Django login, logout, password change, and password-reset workflows are supported. | `auth.login.succeeded`, `auth.login.failed`, `auth.logout`, `auth.password.changed`, `auth.password_reset.requested`, `auth.password_reset.completed`, only for supported workflows. Successful authenticated actions identify the initiating user. Anonymous events may have a null actor. Never attribute an anonymous attempt to an unrelated authenticated user or invent a human actor. | Target an account only when reliably identified and permitted; never target a reset token. | Minimal registered, validated metadata. Never record passwords, password hashes, reset tokens, session IDs, cookies, authentication headers, secret keys, or raw request bodies. Do not include information in audit metadata that reveals whether an account exists. Avoid IP addresses and user-agent strings unless separately authorized. | Record the listed supported success/failure outcomes. Preserve generic failed-login and password-reset responses and do not disclose account existence. | **P1**: account compromise and accountability. These decisions are approved as recorded in Section 3.1; later supervisor revisions must be recorded and their implementation/test impact identified. |
| **2. Patient creation, demographics, archive, restore — Not found.** These workflows have business tests but no event assertions. | `patient.created`, `patient.demographics_updated`, `patient.archived`, `patient.restored`; authenticated staff actor. | Stable patient identifier and internal record ID where needed for unambiguous correlation. | Changed field names and archive-state transition only; do not store old/new demographic values, addresses, phone numbers, date of birth, emergency-contact data, or clinical content in event metadata. | Successful changes; record selected denied attempts only under category 8. | **P1**: patient-record accountability. Approve the demographic field set and whether values belong in a separate, access-controlled history (not audit metadata). |
| **3. Appointments and status — Partially implemented.** Creation, edits/rescheduling, and cancellation are logged and tested. Other status transitions are unsupported and no status-change event path was found. | Preserve existing `appointment.created`, `appointment.updated`, `appointment.rescheduled`, `appointment.cancelled`; proposed future transitions use `appointment.status_changed`. Authenticated staff actor. | Appointment identifier and internal ID; patient identifier only if policy approves the additional linkage. | Changed field names, prior/new schedule for rescheduling, and prior/new status for an approved status transition. Exclude reason-for-visit and cancellation free text, clinical detail, and unnecessary patient values. | Successful supported changes. Failed or denied attempts only if selected under category 8. | **P1**: scheduling changes affect care coordination. Approve metadata detail and any future transition/event mapping before adding status transitions. |
| **4. Consultation creation and amendment — Implemented and verified for current create/amend paths.** Tests check actor, changed fields, prior revision, and exclusion of clinical text from event metadata. | Preserve `consultation.created` and `consultation.amended`; authenticated clinician actor. | Consultation internal ID and patient identifier as currently used; appointment ID where required and approved. | Changed field names and record identifiers only. Do not duplicate symptoms, diagnosis, treatment, clinician notes, or prior clinical text in audit metadata. | Successful creation/amendment. No-op submissions need not create an event. Selected denial events are covered by category 8. | **P1**: sensitive clinical record accountability. Approve patient-linked metadata visibility and whether the current identifiers are minimum necessary. |
| **5. Medical-history entry creation and corrections — Creation implemented and verified; correction workflow not found.** Current entries are append-only. | Preserve `medical_history.created`; if correction is approved, use a separate `medical_history.corrected` event tied to the correction/version record. Authenticated clinician actor for current workflow. | Entry internal ID and patient identifier; correction target/version ID if a future correction model supports it. | Event type, effective date only if approved, changed field names, and correction reference. Do not put entry text or clinical detail in metadata. | Successful creation and approved correction. Do not silently overwrite history; failure behavior for a future correction workflow requires approval. | **P1**: longitudinal clinical history. Approve correction model, authorship, visibility, and whether correction events reference a replacement record. |
| **6. Staff accounts — Not found.** Creation, account/profile edits, role/department changes, activation, and deactivation have no audit writers. | `staff.account.created`, `staff.account.updated`, `staff.role.changed`, `staff.departments.changed`, `staff.account.activated`, `staff.account.deactivated`; authenticated Administrator actor. | Staff profile ID and account ID; avoid targeting account identifiers that expose credentials. | Changed field names and prior/new role or active state where approved. Department IDs/names require approval. Never store temporary/current passwords, reset tokens, or unnecessary contact details. | Successful actions. Selected denied attempts under category 8. | **P1**: authorization changes affect access. Approve department detail, target identifiers, and audit visibility. |
| **7. Reminder generation/reconciliation/failure — Approved for the current implementation baseline; see Section 3.2.** Reminder service and reconciliation command create, update, skip, and remove in-app reminder records; they do not deliver reminders externally. | `reminder.created`, `reminder.updated`, `reminder.removed` for persisted state changes; `reminder.reconciliation.completed` once per reconciliation run that changes state. Automated actor attribution is null actor plus fixed registered metadata. Do not emit per-item skipped/no-op events or a completed event for a no-change run. | Created/updated event target: reminder notification. Removed event target: appointment, with removed reminder ID in metadata. Summary event has no target. | Metadata has `actor_kind: "system"` and `task: "reconcile_appointment_reminders"` plus only required identifiers, a bounded reason code, or bounded changed-item counts. No recipient identity, patient data, message body, contact details, credentials, or raw exception text. | Emit only after the corresponding operation succeeds. A database/audit failure rolls back the current appointment's reminder changes and aborts the command; prior appointments already committed remain committed. No failure event is emitted for a failed transaction. | **P2**: operational reliability. Project owner approved the automated attribution, event granularity, and failure behavior in Section 3.2; supervisor revisions must update the approval record and implementation/test impact. |
| **8. Denied access and security-sensitive failures — Not found.** Authorization tests verify denial behavior but not audit records. | `security.access.denied` and narrowly selected `security.operation.failed`; actor is authenticated user or unauthenticated actor kind. Avoid an event for every ordinary form error. | Target ID only when the request identifies an existing protected object without exposing it; otherwise no target. | Route/action category, outcome, bounded correlation ID, and a coarse reason code. Do not store submitted secrets, complete query strings, request bodies, tokens, or sensitive object details. | Selected authorization denials and security-sensitive failures. Ordinary invalid input should not be logged by default. | **P1**: detect misuse without turning logs into a copy of sensitive requests. Approve which denial/failure classes are recorded and how to limit noise. |
| **9. Sensitive reports and exports — Report exists; audit logging not found. No export endpoint was located in Stage 3A.** | If approved, `report.viewed` for selected sensitive reports and `data.exported` for each approved export operation. Actor is authenticated requester. | Report type and bounded scope identifier; export job/file ID if a future export feature exists. Do not copy exported rows into the event. | Report/export type, approved date range or aggregate filter summary, row-count bucket if useful, and correlation ID. Avoid patient names, identifiers, or clinical data unless explicitly approved as necessary. | Successful access/export; selected denied access under category 8. Failed report parsing need not be logged unless security-relevant. | **P2**: accountability for bulk disclosure. Approve which reports are sensitive, whether reads are logged, and any export scope; do not imply exports exist. |
| **10. Destructive actions and correction workflows — Partially implemented.** Appointment cancellation and consultation amendments are logged; patient archive/restore are not. No patient hard-delete path or medical-history correction path was found. Reminder reconciliation deletes obsolete reminder rows without audit events. | Preserve relevant existing events; add `patient.archived`/`patient.restored` if approved; future purge/correction events should identify operation and authorization. Automated cleanup uses a system/task actor. | Affected record identifier(s), operation batch/run ID for bulk actions, and correction/replacement ID where applicable. | Operation, outcome, record type/count, and approved reason code; never copy record contents or secrets. | Success and failures for approved destructive/purge operations. Failed authorization under category 8. | **P1** for patient/staff/clinical corrections or purges; **P2** for reminder cleanup. Approve delete/purge scope, reversibility, authorization, and event preservation before implementation. |

### Proposed action naming

Use lowercase, dot-separated names in the form
`<domain>.<resource-or-operation>.<past-tense-outcome>` where that form is
unambiguous, for example `auth.login.succeeded`,
`patient.demographics_updated`, and `appointment.cancelled`. Existing names
such as `appointment.created`, `consultation.amended`, and
`medical_history.created` remain unchanged in this requirements stage.
Before implementation, maintain a reviewed action registry that defines each
name, triggering outcome, target type, and metadata schema. Do not infer
approval from this naming proposal.

### 3.1 Approved authentication/session decisions — current baseline

The project owner approved the following authentication/session decisions for
the current implementation baseline:

- Register and emit `auth.login.succeeded`, `auth.login.failed`,
  `auth.logout`, `auth.password.changed`,
  `auth.password_reset.requested`, and
  `auth.password_reset.completed` only for workflows supported by the
  application.
- Attribute successful login, logout, and password change to the initiating
  account. Anonymous login failures and password-reset requests may have a
  null actor. Password-reset completion also uses a null actor because a
  valid reset token identifies the target account, not the human holding the
  token. Never attribute anonymous activity to an unrelated signed-in user.
- Use the account as target only when reliably identified: successful login,
  logout, password change, and completed reset target the account; failed
  login and reset request have no target. Reset tokens are never targets.
- Use empty metadata for these events unless a future approved revision
  specifically authorizes additional fields. Never record passwords,
  password hashes, reset tokens, session IDs, cookies, authentication
  headers, secret keys, raw request bodies, IP addresses, or user-agent
  strings.
- Failed-login and password-reset event data and user-facing responses must
  not reveal whether an account exists.
- If a successful-login event cannot be persisted, do not establish or retain
  the authenticated session; present a safe generic failure. Failed login
  remains unsuccessful if its event cannot be persisted; retain the generic
  external response and report the storage failure operationally without
  credentials.
- Logout terminates the session even if its event cannot be persisted; report
  the storage failure operationally. Password change and reset completion
  must commit together with their event, rolling back the password change if
  event persistence fails, using a database transaction where feasible.
- Password-reset requests retain their generic response and do not disclose
  account existence. Report event-storage failure operationally without
  sensitive account details. Email delivery and audit persistence are not
  claimed to be atomic.
- Do not silently swallow audit failures or expose secrets in operational
  logs. The `create_staff_admin` bootstrap command remains outside this
  decision because it is not an authentication/session request workflow.

The supervisor may later add, modify, or remove any of these requirements.
Any such revision must update this approval record and identify affected
implementation and tests; a later approved revision supersedes only the
decision it changes. Audit-view permissions, retention, archival/purge, and
tamper protection remain unresolved and outside this approval.

### 3.2 Approved reminder reconciliation decisions — current baseline

The project owner approved the following decisions for reminder auditing:

- Use the existing nullable user actor as `NULL`; do not impersonate a staff
  user or add a new actor type. Every reminder event includes registered,
  fixed `actor_kind: "system"` and
  `task: "reconcile_appointment_reminders"` metadata.
- Emit `reminder.created` and `reminder.updated` for individual notification
  records whose persisted state changes. Emit `reminder.removed` for each
  removed reminder. Emit one `reminder.reconciliation.completed` summary only
  when a reconciliation run creates, updates, or removes at least one
  reminder. Do not emit per-item events for skipped/no-op work or summary
  events for no-change runs.
- Creation/update target the saved `AppointmentNotification`; removal targets
  its `Appointment` because the notification is deleted, with its notification
  ID and a fixed allowlisted removal reason in metadata. Summary has no target
  and records only bounded created/updated/removed counts.
- Reminder processing remains in-app record generation/reconciliation only;
  it does not send email, SMS, or patient-facing messages. Do not record
  delivery success.
- Reminder writes and their required audit events commit or roll back together
  within the existing per-appointment transaction. If persistence fails,
  roll back the current appointment's reminder changes and abort the command;
  earlier appointment transactions may already have committed. Do not emit a
  success or failure event for the rolled-back operation, and do not log raw
  exception data. No new retry behavior is introduced.

The supervisor may subsequently add, modify, or remove these requirements.
Future revisions must update this approval record and state their
implementation and test impact; a later approved revision supersedes the
affected earlier decision. This approval does not resolve reminder delivery,
viewer access, retention, archival/purge, or tamper-protection policy.

### 3.3 Approved nursing-observation audit decision — current baseline

The project owner approved a Nurse-only nursing-observation workflow. Each
observation is linked to an existing appointment and its patient and is
attributed to the authenticated Nurse who recorded it. The shared audit
registry records `nursing_observation.created`, targeting the saved
observation. Its only metadata fields are the approved patient identifier and
observation record ID; measurement values, notes, appointment reasons, and
other clinical details are excluded. The observation write and required audit
event succeed or roll back together in one database transaction. Audit
storage failures are reported operationally without raw exception data or
clinical values. No observation update/delete workflow or event is approved.
Future supervisor revisions must update this record and identify implementation
and test impact; later approval supersedes only decisions it changes.

## 4. Proposed audit-view access matrix

The following is a conservative **proposal only**. Existing role permissions
remain unchanged. Every proposed grant, including Administrator access, needs
explicit approval; “No proposed access” is not a claim that a policy has
already been approved. Clinical event access must not be inferred from
administrative authority.

| Audit capability | Administrator | Receptionist | Doctor/Clinician | Nurse |
|---|---|---|---|---|
| View general operational events (staff-account and system events, excluding clinical-linked metadata) | Proposed: yes, limited to approved event classes; **approval required** | Proposed: no; **approval required** | Proposed: own initiated events only; **approval required** | Proposed: no until a Nurse workflow and need are approved |
| View patient-linked nonclinical events | Proposed: only approved patient-demographic and appointment event fields; no clinical metadata by default; **approval required** | Proposed: only events within existing demographic/appointment duties, with metadata minimized; **approval required** | Proposed: patient events only within assigned-care scope; **approval required** | Proposed: no until role scope and need are defined |
| View clinical-linked event metadata | Proposed: no by default; any exception requires a separate decision and justification | Proposed: no | Proposed: assigned-care events only, and only metadata needed for accountability; **approval required** | Proposed: no until a nursing clinical workflow/scope is approved |
| Search/filter | Only within the approved event scope; **approval required** | Only if viewer access is approved and scoped | Only within approved own/assigned-care scope | Only if role access is approved |
| Export audit records | Disabled by default; **approval required** | Disabled by default | Disabled by default | Disabled by default |
| Archive or purge audit events | No ordinary role permission proposed; separate approved operational authorization required | No | No | No |

If a viewer is approved, enforce permissions server-side on every request,
including direct URLs, searches, pagination, and exports. A hidden navigation
link is not authorization. Patient-linked and clinical event scope must use
the existing patient-care boundary where applicable; a guessed identifier
must not broaden access. Whether Administrators may see any clinical-linked
metadata, and whether any role may export or manage retention, remain explicit
approval decisions.

## 5. Metadata, privacy, and event integrity requirements

The following are proposed requirements, pending approval:

- Store event timestamps consistently using the project's timezone-aware UTC
  configuration (`USE_TZ=True`, `TIME_ZONE="UTC"`). Viewer presentation may
  localize timestamps, but stored ordering and comparisons must remain
  timezone-aware and consistent.
- Record the initiating staff account when authenticated. Represent
  unauthenticated attempts and automated tasks distinctly. Automated jobs
  must use a stable task identity and must not appear to be a staff user.
- Validate action names against a reviewed registry. Validate target type,
  identifier format, permitted metadata keys, value types, and reasonable
  size limits. Do not treat arbitrary request data as event metadata.
- Record only the minimum context needed to explain who performed what
  operation, on which target, when, and with what outcome. Prefer changed
  field names and approved state transitions to copying before/after values.
- Exclude passwords, reset tokens, session tokens/cookies, secret values,
  credentials, raw form/request payloads, and unnecessary patient or clinical
  details. Do not place clinical note text in event metadata.
- For a successful business operation designated as requiring an event, make
  the business change and event transactionally consistent: either both
  commit or both roll back. Add tests that prove this behavior.
- Define a separate failure path for event-storage failures. Do not silently
  report a fully successful audited operation if its required event was not
  stored. Whether such failures block the underlying operation, and how an
  operational alert is raised without exposing sensitive data, requires owner
  approval. Authentication and unauthenticated failure events need an
  explicitly approved availability/fail-closed policy.
- Correct historical event data by adding a new, attributable correction
  record; do not silently rewrite an existing event. Any exceptional repair
  process must be separately authorized and leave an explanation outside the
  altered record.
- Application-level controls may restrict ordinary application users from
  editing/deleting event rows. Such controls do not protect against a
  database administrator, filesystem access, malicious code running with
  database privileges, or replacement/restoration of the database file.
- Do not claim immutability, tamper evidence, completeness, or compliance
  without a design and evidence that establish that property. Stronger
  tamper-evident or externally protected storage (for example, a separately
  controlled append-only destination) is a future design decision, not an
  existing capability.

## 6. Retention, archival, backup, and restore decisions

No retention period or legal retention rule is selected. Before implementing
archival or purge, obtain approval for each of these decisions:

1. The retention period or criteria, including how the decision accounts for
   the project's data purpose and applicable jurisdiction; do not infer a
   legal requirement.
2. Who may authorize, execute, and review archival or purge, and whether
   approval must be separated from execution.
3. Whether archived events remain searchable, by whom, and whether they may
   be restored to active search.
4. Whether audit rows are retained in ordinary database backups and how
   backup copies inherit the approved access, retention, and disposal rules.
5. How event counts, database integrity, and any future tamper-evidence
   mechanism are checked after restore. SQLite integrity checking alone would
   establish database structural integrity, not audit completeness or
   tamper-resistance.
6. How to handle an event whose generic target has been removed or no longer
   resolves. The actor FK uses `SET_NULL`, and a generic target does not
   enforce target existence.
7. Whether audit-view access, export, archival, purge, and exceptional repair
   operations themselves generate events, and how those events are preserved.
8. Whether backup copies are subject to the same deletion/purge request or
   expire only under a separately approved backup policy.

The current documented SQLite backup copies the database as a whole, so
existing audit rows are included in a database backup. The backup commands do
not provide an audit-specific archive, retention, integrity, or recovery
policy. See [database_backup.md](./database_backup.md).

## 7. Outstanding approval register

The authentication/session decisions in Section 3.1 are approved for the
current baseline. Other entries below remain unresolved; listing them does not
approve them.

| Decision | Required approval |
|---|---|
| Event coverage outside the approved authentication/session events, including selected denied requests, report access, and operational failures | Project owner/supervisor |
| Event names, outcome definitions, actor identity for automated tasks, and required target identifiers outside the approved authentication/session decisions | Project owner/supervisor |
| Permitted metadata per event outside the approved authentication/session decisions, including patient identifiers, department changes, schedule details, and failure categories | Project owner/supervisor with privacy review |
| Which roles may view general, patient-linked, and clinical-linked events; assigned-care scope; whether Administrator access to any clinical metadata is justified | Project owner/supervisor with privacy review |
| Whether search, export, audit-access logging, archive, and purge features are in scope | Project owner/supervisor |
| Event-write failure behavior, operational alerting, and transaction boundary for operation classes outside the approved authentication/session decisions | Project owner/supervisor and implementation review |
| Retention criteria/duration, archival, purge authorization, and treatment of backup copies | Project owner/supervisor; legal/privacy advice if applicable |
| Required protection against application-level changes versus direct database/filesystem access | Project owner/supervisor and technical owner |
| Correction model for medical-history entries and future destructive workflows | Project owner/supervisor and clinical workflow owner |

## 8. Future implementation acceptance criteria

Implementation should not begin until the decisions relevant to that
implementation are approved. For the approved authentication/session
baseline, acceptance includes tests demonstrating:

1. Every approved successful action creates exactly the required event with
   the approved action, actor, timestamp, target, outcome, and permitted
   metadata; unapproved events are not added implicitly.
2. Automated operations use the approved system/task attribution; an
   unauthenticated request is not attributed to a staff account.
3. Approved failure events are created for the selected failure classes
   without disclosing account existence or sensitive request details.
4. Event metadata validation rejects unapproved keys/values and tests prove
   passwords, session/reset tokens, secrets, raw request data, and
   unnecessary clinical details are excluded.
5. Each covered business operation has the approved transaction behavior;
   injected event-write failure proves the operation either rolls back or
   follows the explicitly approved failure policy, with no success-shaped
   silent fallback.
6. Historical corrections are additive and attributable; existing events are
   not silently rewritten. Missing generic targets are handled and displayed
   without errors or accidental disclosure.
7. If a viewer is approved, tests verify each role's exact event scope,
   server-side direct-URL denial, patient/clinical scope, and safe handling of
   invalid filters. Search results are paginated and do not exceed the
   approved page-size policy.
8. If export is approved, tests verify role/scope enforcement, data
   minimization, and that export actions themselves are recorded if required
   by policy.
9. If retention/purge is approved, tests verify authorization, retention
   boundaries, archive/search behavior, purge limits, and required recording
   of purge actions. A restore test verifies the approved audit checks without
   targeting the active database.
10. Existing authentication, authorization, clinical privacy, appointment,
    patient, and reminder tests remain green. Tests use isolated databases and
    do not modify `src/db.sqlite3`.

These are future acceptance criteria only. No tests or implementation are
added in this requirements stage.

## Implementation status after Stage 3C.4

The shared audit service validates registered appointment, clinical,
patient, and web staff-management actions. Patient and web staff-management
create/update/archive/restore/status operations described in the respective
increments have actor-attributed event writers and transaction coverage.
Authentication/session coverage is implemented under the approved Section
3.1 decisions. These events use empty metadata. Successful login, logout,
password change, and reset completion target the account. Login failures and
reset requests have null actors and no targets; reset completion has a null
actor. Failed-login and reset-request events preserve generic responses.
Successful-login event failure clears the session, password-change and
reset-completion event failures roll back the password write, and logout
continues after an operationally logged event-storage failure. Reset-request
email delivery is external to audit persistence and is not atomic with it.
Reminder creation/update/removal and reconciliation summary events are now
written under Section 3.2. They use a null actor, fixed system/task metadata,
and minimal targets; skipped/no-op items do not emit events. Reminder
reconciliation does not send reminders externally. Reminder, report-access,
viewer, export,
retention/purge, and tamper-protection work beyond the approved reminder

The owner-requested reminder email extension records delivery timestamps,
attempt counts, and a generic provider error code on the reminder row. Email
delivery is invoked separately from reconciliation and has no dedicated
`AuditEvent` action at present; the notification record is the current delivery
state evidence. The provider call is an external side effect and is not atomic
with database persistence.

The `create_staff_admin` bootstrap management command can create the first
Administrator without an authenticated application user. It is not covered
by the web staff-management events because the approved staff-event actor rule
requires an authenticated Administrator and no bootstrap/system actor rule
is defined here. Do not invent or impersonate an actor to log that command;
its attribution requires an explicit policy decision.
