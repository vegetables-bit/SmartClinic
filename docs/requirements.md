# Requirements and domain scope

> **Status: APPROVED M01 REQUIREMENTS.** This specification reflects the
> approved project requirements and the current implementation. The project
> follows the four approved staff roles and the documented permission model.
> This document records the current approved scope.

## 1. Purpose and scope

The Smart Clinic project is a web-based appointment and patient-records
tracking system for a university Computer Science mini-project. The approved
M01 scope covers staff authentication and access control, patient
registration and retrieval, appointments, consultations, medical history,
staff and department information, reminders, reports, administration, audit
events, and data-management considerations.

Patient-facing accounts are out of scope for the current approved project
requirements. Only the four approved staff roles below are in use. A patient
portal would require a separate access/privacy design and explicit approval.

This document reflects the approved M01 scope and implemented system
boundaries.

## 2. User roles and boundaries

The approved staff roles are Administrator, Receptionist, Doctor/Clinician, and
Nurse. Access is defined in
[role_permission_matrix.md](./role_permission_matrix.md). Role names do not
grant automatic access to every record: access is limited by assigned
responsibility and the minimum information needed for the task.

| Role | Approved responsibility | Boundary |
|---|---|---|
| Administrator | Manage staff accounts, role assignments, departments, system configuration, and approved operational reports. | No routine clinical-note access by virtue of administration alone. Exceptional access must be separately approved and restricted. |
| Receptionist | Register and update permitted demographics, find records for identity confirmation, and manage appointment logistics. | No unrestricted diagnosis, treatment, clinician-note, or longitudinal medical-history access by default. |
| Doctor/Clinician | Review relevant patient information and record or amend consultations and clinical history for patients under their care. | Clinical access is limited to an assigned care relationship or other approved basis; amendment history must be preserved. |
| Nurse | Support assigned patient care, review permitted patient information/history, and record only approved nursing observations or care-related information. | Clinical documentation rights remain limited to approved workflows; no implied ability to amend clinician notes. |

## 3. Functional requirements

Each ID represents one observable behavior in the approved project scope.
Verification language reflects the implemented or testable acceptance criteria
for the current project state.

| ID | Proposed requirement | Future acceptance evidence |
|---|---|---|
| FR-01 | The system shall authenticate an active staff account before granting access to protected functions. | An unauthenticated request to a protected function is denied or redirected, and a valid active account can sign in. |
| FR-02 | The system shall authorize each staff action according to the account's assigned role and permitted scope. | A test matrix checks allowed and denied operations for each role, including direct requests. |
| FR-03 | The system shall allow an authorized staff member to create a patient record with the fields approved for registration. | A valid record is saved; missing required and invalid values are rejected with field-specific feedback. |
| FR-04 | The system shall allow only authorized staff to update permitted patient demographic fields. | Permitted edits persist, while an unauthorized role/action is denied and recorded as required. |
| FR-05 | The system shall allow authorized staff to search and retrieve patient records using approved search fields. | Matching records are returned for allowed search criteria, and inaccessible clinical details are not disclosed. |
| FR-06 | The system shall allow an authorized staff member to create an appointment for a patient with a selected clinician, date, time, and approved appointment details. | A valid appointment is stored with its patient, clinician, and scheduled time; invalid references/times are rejected. |
| FR-07 | The system shall allow authorized staff to reschedule an appointment while preserving its previous schedule and recording the change. | The new schedule is displayed and the prior schedule/change event remains auditable. |
| FR-08 | The system shall allow authorized staff to cancel an eligible appointment and record the cancellation event. | The status changes to the approved cancelled state and the event is retained. |
| FR-09 | The system shall display appointments in the approved upcoming, completed, cancelled, and missed categories. | Records appear in the correct category according to approved status definitions and date rules. |
| FR-10 | The system shall allow an authorized clinician to record a consultation linked to a patient and appointment, when one exists. | Authorized data persists with author and timestamps; roles without the permission are denied. |
| FR-11 | The system shall allow authorized clinical staff to retrieve permitted consultation and medical-history records for a patient. | The permitted history is returned in the approved order and unauthorized fields/records are withheld. |
| FR-12 | The system shall preserve previously saved consultation content when an authorized amendment is made. | The current record reflects the amendment and the prior version/change metadata remains retrievable by authorized users. |
| FR-13 | The system shall allow authorized users to maintain staff profiles and department assignments within their permissions. | Authorized changes persist; other roles cannot create or change staff authorization data. |
| FR-14 | The system shall create an in-application reminder record for an eligible upcoming appointment when the approved reminder rule is met. | The reminder is associated with the correct appointment and deduplication/retry behavior follows an approved policy. |
| FR-15 | The system shall present reminders to the intended authorized staff recipient or recipients. | Only the approved recipients can view the reminder and its delivery/read state is tracked as designed. |
| FR-16 | The system shall provide approved operational dashboard summaries and reports to authorized roles. | A role-specific test verifies approved measures, date filters, and access boundaries. |
| FR-17 | The system shall record an audit event for each action designated sensitive by the approved audit policy. | Tests verify required actor, action, target, time, outcome, and permitted contextual metadata are recorded. |
| FR-18 | The system shall support the approved archive/deactivation process for patient and staff records without silently erasing required history. | Archived/deactivated records are excluded or included according to approved retrieval rules, with history retained as approved. |
| FR-19 | The system shall allow an authorized administrator to configure only the settings designated in the approved administration scope. | An authorization test restricts settings changes to designated users and records sensitive changes. |
| FR-20 | The system shall make appointment status transitions only through the approved transition rules. | Tests reject transitions not present in the approved transition table and preserve each accepted transition. |

## 4. Non-functional requirements

These are the project quality requirements currently approved for
implementation. Numeric service targets and policy values are intentionally
not invented without an explicit approval decision.

| ID | Proposed requirement | Confirmation / future verification |
|---|---|---|
| NFR-01 Security | Protected data and actions shall require authentication and server-side, least-privilege authorization; hiding a UI control alone is insufficient. | Review permission tests, direct-request denials, and session behavior before release. |
| NFR-02 Privacy | Patient data shall be limited to approved purposes and roles; sensitive access and changes shall follow an approved audit and retention policy. | Obtain project-owner/supervisor review; do not imply regulatory compliance. |
| NFR-03 Credential protection | Passwords shall be managed using Django's supported password hashing and authentication mechanisms; secrets shall not be committed or displayed. | Inspect configuration and test credential handling before authentication milestone completion. |
| NFR-04 Usability | Staff shall be able to complete approved core tasks using clearly labeled forms, validation feedback, and consistent navigation. | Conduct task-based review with representative users; exact usability targets require approval. |
| NFR-05 Accessibility | User interfaces should support keyboard use, semantic structure, readable contrast, and accessible labels. | Select an accessibility target and evaluate pages before sign-off; no conformance claim is made here. |
| NFR-06 Data integrity | Patient, appointment, consultation, and audit relationships shall remain valid; conflicting writes and invalid status transitions shall be rejected. | Exercise database constraints and application validation with automated tests. |
| NFR-07 Reliability | Failed requests or notification attempts shall not be represented as successful; recoverable failures shall be surfaced and handled according to an approved policy. | Test error paths and document operational recovery once delivery channels are selected. |
| NFR-08 Maintainability | The application shall keep project configuration separate from focused domain applications and include tests and documentation for implemented behavior. | Review module boundaries, migrations, and test coverage in later implementation milestones. |
| NFR-09 Performance | Common record search and schedule views shall return results within a response-time target to be selected for the expected data volume and environment. | Agree on workload and measurable response-time threshold before performance acceptance. |
| NFR-10 Backup and recovery | The project shall define a protected backup schedule, retention, restore procedure, and recovery objectives before real patient data is used. | Exercise a restore and record recovery objectives before operational deployment. |
| NFR-11 Browser compatibility | The user interface shall work in the organization-approved versions of common browsers. | Confirm browser/version support and execute a browser test matrix before release. |
| NFR-12 Configuration | Environment-specific settings and secrets shall be external to tracked source; production configuration shall not use development debug settings. | Review deployment settings and repository ignore/tracking behavior before deployment. |

## 5. Candidate workflows

Text sequences are used rather than adding a diagram dependency or assuming
that the repository has a Mermaid rendering convention.

### Patient registration

1. An authorized staff member searches for a likely existing record using
   approved matching fields to reduce duplicate creation.
2. The staff member enters the approved minimum required demographics.
3. The system validates required values and candidate duplicate matches.
4. The staff member resolves or escalates a possible duplicate according to an
   approved policy; the system does not silently merge records.
5. On confirmation, the system creates the patient record and records the
   creator and creation time as approved.

### Appointment booking

1. An authorized staff member selects or identifies a patient.
2. The staff member chooses a clinician, department/service if applicable, and
   requested date and time.
3. The system checks the clinician's approved availability and appointment
   conflict rules.
4. The staff member confirms the booking; the system records the appointment
   in its initial approved state and records the responsible actor.
5. If reminders are enabled and the approved rule applies, the system records
   the reminder for later handling.

### Appointment attendance and consultation

1. Staff locate the scheduled appointment and confirm attendance using the
   approved check-in process.
2. The appointment status is changed using an allowed transition.
3. An authorized clinician reviews the relevant patient profile and permitted
   history.
4. The clinician records the consultation information approved for the form.
5. The system links the consultation to the patient and, where applicable, the
   appointment; it stores authorship and timestamps.
6. Later corrections follow the amendment/version-preservation rule rather than
   silently replacing prior content.

### Viewing patient history

1. An authenticated user searches for and selects a patient.
2. The system checks role and record scope on the server.
3. The system presents only the demographics, consultations, and history
   sections allowed for that user's role and purpose.
4. Sensitive access is recorded where the approved audit policy requires it.

### Appointment cancellation

1. An authorized staff member locates an appointment and requests cancellation.
2. The system verifies that cancellation is permitted from the current state.
3. The staff member supplies any cancellation reason required by the approved
   policy.
4. The system changes status, preserves the event and actor, and recalculates
   any applicable reminder state.
5. The system does not delete the appointment or reuse its identifier.

### Staff account creation and access control

1. An authorized administrator creates a staff account and selects the
   approved role and staff profile.
2. The system prevents unauthorized role assignment and applies approved
   credential setup and activation steps.
3. The administrator verifies the account's permitted scope without sharing
   credentials insecurely.
4. The system audits the account/role change as required.
5. When access is no longer appropriate, an authorized administrator deactivates
   the account; historical attribution remains intact.

## 6. Implementation details not prescribed by M01

M01 is approved and remains the authoritative requirements baseline. The
following implementation-specific values or detailed operational rules are
not specified at the level needed for every workflow. Their absence is a
narrow technical or workflow detail, not a pending approval of M01:

- Patient accounts are excluded from the current baseline; no patient login
  model or portal is implemented.
- Detailed staff onboarding steps, authentication factors, session policy,
  account recovery, and external identity-provider integration.
- Detailed clinician-to-patient assignment rules, nurse documentation scope,
  and any exceptional administrator access beyond the role matrix in
  `role_permission_matrix.md`.
- Identifier formatting beyond the uniqueness requirements, duplicate-record
  resolution, patient correction/merge procedures, and archival/reactivation
  workflow details beyond the implemented soft-archive behavior.
- Appointment duration, clinic hours, time zone, buffers, provider availability,
  double-booking, waitlists, cancellation windows, and detailed status
  transition conditions.
- Who may mark attendance, completion, and missed appointments, and when a
  scheduled appointment becomes missed.
- Consultation fields and the meaning/structure of diagnosis, treatment,
  symptoms, notes, amendments, signatures, and clinical history.
- Whether medical history is a distinct set of longitudinal entries, a
  consultation-derived view, or both, and who may author each entry.
- Reminder channels, recipients, consent, timing, time-zone handling,
  delivery/retry behavior, failure display, and deduplication.
- Role-to-department scope and department-based clinical access details. The
  current schema reuses the existing Department model and supports multiple
  department assignments.
- Report definitions, data aggregation, export needs, date ranges, and
  role-specific disclosure.
- Audit events, access logging, retention, tamper protection, and who may view
  audit data.
- Data retention/deletion durations, privacy jurisdiction, applicable
  law/standards, hosting, backup frequency, recovery objectives, expected data
  volume, and browser support.
- Applicable usability/accessibility acceptance targets and performance
  thresholds.

## 7. Approval and traceability

The current content reflects the approved M01 scope and the implementation in
this repository. Requirement IDs and role references remain stable within the
approved baseline, and any future change should be recorded with the
corresponding domain-design and test updates.

## 8. M02 database implementation baseline

The following technical choices have been implemented for the M02 development
schema within the approved project baseline:

- The existing Django user model is retained. A staff profile stores the
  approved role and optional staff identifier/contact, and can be linked to
  multiple departments.
- A patient requires a full name and receives a generated, unique `PT-` UUID
  identifier. Date of birth, phone, address, emergency-contact details, and
  the approved `gender` field are included in the implemented demographic set
  as approved for M05.
- Appointments store start/end times and one of six allowed status values.
  Start/end ordering is database-enforced; availability, interval conflicts,
  and status transitions are not.
- Consultations link to a patient and clinician and optionally to an
  appointment. The schema permits more than one consultation per appointment
  because M01 cardinality was unresolved.
- Medical history is represented by separately authored text entries to avoid
  copying consultation diagnosis/treatment into a second record.
- Appointment notifications store in-app metadata; no external channel or
  delivery behavior exists. Audit events have a storage model only; no
  automatic sensitive-action logging exists.

These entries describe the current database implementation and its remaining
technical/workflow limits; they do not defer or supersede the approved M01
requirements. Implemented fields, relationships, and integrity boundaries are
documented in [database_design.md](./database_design.md).
