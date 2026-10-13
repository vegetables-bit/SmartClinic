# Milestone 01 Report

## 1. Objective

Produce a clear, internally consistent requirements and domain
design specification for the Web-Based Smart Clinic Appointment and Patient
Records Tracking System. This milestone is documentation and analysis only; it
must not implement business features or begin Milestone 02.

**Result: PASS** for the stated documentation and scope criteria. All business
requirements in M01 were subsequently approved by the project supervisor.
This approved baseline remains authoritative. Narrow technical/workflow values
not specified in the documents are implementation details, not a pending
approval of M01.

## 2. Documents inspected

Before editing, the following current files were read:

- `README.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `reports/MILESTONE_00_REPORT.md` (all 258 lines, in two bounded reads)

The current project tree was also inspected. At inspection it contained the
Milestone 00 Django project under `src/config`, `src/manage.py`, the landing
template, and `src/db.sqlite3`. No domain app, Django model source file, or
migration directory/file was present. The report was treated as historical
documentation and compared with the actual tree, not accepted as proof of the
current implementation state without inspection.

## 3. Work completed

- Replaced the brief initial requirements with functional and non-functional
  requirements, unique IDs, acceptance evidence, and explicit implementation
  details not specified in M01.
- Replaced the starter architecture notes with system boundaries, security
  principles, data ownership, interactions, and dependencies.
- Added a least-privilege role/permission matrix for Administrator,
  Receptionist, Doctor/Clinician, and Nurse, consistent with the approved role
  model.
- Added a domain model with entity purposes, fields, relationships,
  cardinality details, and rules against unnecessary duplication.
- Documented the requested workflows as clear text sequences.
- Updated the README's documentation-tree description and distinguished
  approved requirements from behavior not yet implemented.
- Created this report with actual inspection and validation results.

No Django business code, models, migrations, authentication flows, patient or
appointment pages, reminder services, or notifications were added.

## 4. Requirements summary

The requirements specification defines 20 testable functional requirements
(FR-01 through FR-20) spanning staff authentication and authorization, patient
registration/update/search, appointment booking/rescheduling/cancellation and
status, consultation and medical-history access, amendment preservation,
staff/departments, reminders, dashboards/reports, audit events, archive
handling, administration, and valid status transitions.

It also defines 12 non-functional requirements (NFR-01 through NFR-12):
security, privacy, credential protection, usability, accessibility, integrity,
reliability, maintainability, performance, backup/recovery, browser
compatibility, and configuration security. Numeric targets and legal
obligations are not invented. The documents do not claim compliance with any
healthcare law or standard.

The initial scope assumes staff accounts only; patient login is not included
unless the project owner explicitly approves it.

## 5. Role and permission summary

- **Administrator:** access to staff accounts/roles, selected
  department/system configuration, and approved operational reports; no
  clinical-note access by virtue of admin status alone.
- **Receptionist:** access to necessary patient demographics and
  appointment logistics; no unrestricted consultation or medical-history
  access by default.
- **Doctor/Clinician:** access to relevant records for assigned care
  and authority to create/appropriately amend own/approved consultations.
- **Nurse:** access scoped to assigned care; exact history view and separate
  nursing documentation rights remain for approval. No default right to edit a
  clinician's note.

Server-side authorization, record scope, minimum necessary fields, and audit of
designated sensitive actions are cross-role principles. The current approved
permission matrix is maintained in `docs/role_permission_matrix.md`.

## 6. Domain entities and relationships

The domain model includes UserAccount, StaffProfile, Department, Patient,
Appointment, Consultation, MedicalHistoryEntry, Reminder, and AuditEvent.
Patient demographics are kept in a canonical patient entity; other records
refer to it. Appointment schedule/state is separated from encounter content in
Consultation. A separate history entity represents discrete,
attributable longitudinal facts; it must not duplicate consultation text as an
independently editable copy.

The conceptual relationships include staff profile to account/department; patient
to appointments, consultations, and history entries; clinician staff profile
to appointments and authored records; appointment to optional consultation and
reminders; and actor account to audit events. Account/profile cardinality,
staff multi-department membership, appointment-consultation cardinality, and
reminder attempt design remain open.

## 7. Approved requirements and implementation details

The approved M01 requirements define the project behaviors and staff-role
boundaries. The following notes distinguish those requirements from detailed
technical or operational values that the written baseline does not enumerate:

- Identifier formatting, duplicate resolution, and field-level validation.
- Appointment duration, time zone, clinician availability, buffers, and exact
  conflict/status-transition behavior.
- Detailed consultation amendment/version data and nurse-specific record
  types.
- Reminder delivery/retry settings, audit-event detail, and data-retention
  durations.
- Entity relationships are represented by the schema described in the
  corresponding database and architecture documentation.

## 8. Implementation details not specified in M01

M01 is approved. Its implementation notes identify narrower operational or
technical details that are not fully specified by the written requirements,
including appointment durations/time zones and overlap rules; identifier
formatting and duplicate-record resolution; detailed clinical/amendment
fields; reminder delivery/retry values; report measures; and retention,
deployment, and quantitative accessibility/performance targets. These details
do not alter the approved requirements, project scope, or four staff roles.

## 9. Files created or modified

- **Modified:** `README.md`
- **Modified:** `docs/requirements.md`
- **Modified:** `docs/architecture.md`
- **Created:** `docs/role_permission_matrix.md`
- **Created:** `docs/domain_model.md`
- **Created:** `reports/MILESTONE_01_REPORT.md`

No source code, model, or migration file was modified or added.

## 10. Verification and consistency checks

- **PASS** — All four requested source documents were inspected before edits;
  the project tree was independently inspected.
- **PASS** — Required documentation paths were checked to exist after editing.
- **PASS** — Requirement IDs were checked for uniqueness; FR-01 through FR-20
  and NFR-01 through NFR-12 are the documented sequences.
- **PASS** — Role names, least-privilege intent, clinical-note
  restriction for reception, and patient-account assumption are present in the
  requirements and permission documents.
- **PASS** — Entity names/relationships in the architecture summary correspond
  to the domain-model catalogue.
- **PASS** — M01 approval is recorded; narrower implementation details are
  distinguished from approved requirements.
- **PASS** — Current `src` tree was rechecked; no domain model files,
  migration directory, or migration files were present. The pre-existing
  `src/db.sqlite3` remains the Milestone 00 framework database; it was not
  modified intentionally in this documentation milestone.
- **NOT TESTED** — No Django test/check command was run for this
  documentation-only milestone; no code changes were made.
- **NOT TESTED** — No usability, security, legal, or performance evaluation
  was performed as part of this documentation milestone.

## 11. Acceptance checklist using PASS, FAIL, NOT TESTED or BLOCKED

1. **PASS** — Administrator, Receptionist, Doctor/Clinician, and Nurse roles
   and the permission baseline are documented.
2. **PASS** — Functional requirements use unique IDs and describe testable
   behavior.
3. **PASS** — Non-functional requirements cover security/privacy, usability,
   integrity, reliability, maintainability, performance, backup/recovery, and
   browser compatibility.
4. **PASS** — Entities, purposes, fields, relationships, and details requiring
   technical decisions are explained.
5. **PASS** — Appointment and consultation requirements, preservation,
   cancellation, missed status, archiving, and audit considerations are
   documented, with unspecified workflow details identified.
6. **PASS** — All six requested workflows are described step by step.
7. **PASS** — Assumptions and open questions are explicit.
8. **PASS** — Required documentation files exist and are aligned.
9. **PASS** — No business-feature code or migrations were added.
10. **PASS** — This detailed report documents work and evidence for each
    acceptance criterion.

## 12. Known limitations

- The M01 requirements are approved and authoritative. This report describes
  the documentation work and does not claim that all specified functionality
  was implemented in M01.
- No compliance assessment or legal advice has been performed.
- Performance, browser, accessibility, backup, recovery, retention, and
  operational targets are qualitative or unresolved.
- The current local SQLite database and Django settings remain the
  Milestone 00 development foundation, not a production-ready configuration.

## 13. Recommended next milestone

**Milestone 02 — Database Design and Configuration** was the next milestone
and has since been completed. M03 authentication and access control and later
milestones are documented in their respective reports.
