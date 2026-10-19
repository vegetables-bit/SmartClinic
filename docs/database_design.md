# M02 database design

> **Status: IMPLEMENTED DEVELOPMENT SCHEMA / APPROVED DOMAIN BOUNDARY.**
> Django models and migrations described here exist in the local SQLite
> project and reflect the approved M01 requirements and project implementation.
> The project uses fictional patient and staff data only.

## 1. Database design objectives

- Add the M02 domain tables to the existing SQLite database without changing
  Django's already-applied authentication schema or deleting data.
- Keep account credentials in Django's built-in user model; store staff role
  and organization data in a related profile.
- Keep patient identity/demographics in one canonical Patient row and link
  appointments and clinical records by foreign key.
- Preserve history through archival/inactivation and protective foreign keys.
- Use database constraints for simple rules SQLite can enforce and clearly
  distinguish them from model validation or future workflow behavior.
- Implement database structure only; do not add login pages, role enforcement,
  booking workflows, clinical workflows, reminder delivery, or automatic audit
  capture.

## 2. Tables/models and purposes

| Model | Table | Purpose |
|---|---|---|
| Django built-in User | `auth_user` | Existing staff account/credential identity. No custom user migration or patient account model is added. |
| `Department` | `clinic_department` | Named clinic department with active flag. |
| `StaffProfile` | `clinic_staffprofile` | One-to-one role and staff information for a Django user; departments are many-to-many. |
| `Patient` | `clinic_patient` | Canonical demographics, generated public identifier, archive state. |
| `Appointment` | `clinic_appointment` | Scheduled interval, patient, assigned staff clinician, status and optional visit/cancellation text. |
| `Consultation` | `clinic_consultation` | Patient encounter notes, clinician, encounter time, optional appointment. |
| `ConsultationRevision` | `clinic_consultationrevision` | Snapshot of prior consultation time, appointment, and text fields with the revising clinician; created when a consultation is amended. |
| `MedicalHistoryEntry` | `clinic_medicalhistoryentry` | Discrete, attributable longitudinal history note; not a duplicate appointment note. |
| `AppointmentNotification` | `clinic_appointmentnotification` | In-app notification/reminder record related to an appointment and optional recipient. |
| `AuditEvent` | `clinic_auditevent` | Minimal event/actor/target metadata storage. Model creation does not create audit events automatically. |

`StaffProfile.departments` also creates Django's implicit many-to-many join
table.

## 3. Important fields and types

Every clinic model except AuditEvent inherits `created_at` and `updated_at`
from an abstract timestamp model. AuditEvent stores `occurred_at`.

| Model | Fields (Django types) |
|---|---|
| Department | `name` CharField(120); `description` TextField optional; `is_active` BooleanField. |
| StaffProfile | `account` protected OneToOneField to configured Django user; `staff_identifier` optional unique CharField(50); `role` CharField(20); `phone_number` optional CharField(30); `is_active` BooleanField; `departments` optional ManyToManyField. |
| Patient | `patient_identifier` unique non-editable CharField(35); `full_name` CharField(200); required `gender` CharField(20) with approved choices; optional `date_of_birth` DateField, phone CharField(30), address TextField, emergency-contact name CharField(200), emergency-contact phone CharField(30); `is_archived` BooleanField. |
| Appointment | protected Patient and StaffProfile ForeignKeys; `appointment_at` and `ends_at` DateTimeFields; optional `reason_for_visit` and `cancellation_reason` TextFields; `status` CharField(12). |
| Consultation | protected patient and clinician ForeignKeys; optional protected appointment ForeignKey; `consultation_at` DateTimeField; optional symptoms, diagnosis, treatment, clinician notes TextFields. |
| ConsultationRevision | protected consultation and revising clinician ForeignKeys; optional protected previous appointment ForeignKey; prior consultation time and symptoms, diagnosis, treatment, clinician-notes fields; timestamps. |
| MedicalHistoryEntry | protected patient and author ForeignKeys; required `entry_text` TextField; optional `effective_date` DateField; `recorded_at` DateTimeField. |
| AppointmentNotification | protected appointment ForeignKey; optional user recipient ForeignKey (`SET_NULL`); `notification_type` CharField(50); optional `scheduled_for` and `read_at` DateTimeFields. |
| AuditEvent | optional actor user ForeignKey (`SET_NULL`); `action` CharField(100); `occurred_at` DateTimeField; optional ContentType ForeignKey (`SET_NULL`) and `object_id` CharField(64); `metadata` JSONField. |

The model's field `blank`/`null` settings are authoritative. Most patient
demographics remain optional except the required `gender` field, which is now
implemented as part of the approved demographic set. Model `choices`
validation is separate from database constraints; Appointment status and
StaffProfile role additionally have explicit database checks.

## 4. Primary keys, foreign keys, and relationships

Primary keys are Django `BigAutoField` values; the public patient identifier
does not reveal or reuse that key.

| Relationship | Cardinality and deletion rule |
|---|---|
| User to StaffProfile | One account has at most one profile; profile's account FK uses `PROTECT`. |
| Department to StaffProfile | Many-to-many; the implicit join rows are removed when either endpoint is deleted. Department should normally be deactivated, not deleted, if assignment history matters. |
| Patient to Appointment | One patient may have many appointments; appointment.patient uses `PROTECT`. |
| StaffProfile to Appointment | One clinician may have many appointments; appointment.clinician uses `PROTECT`. |
| Patient to Consultation | One patient may have many consultations; consultation.patient uses `PROTECT`. |
| Appointment to Consultation | Each consultation may have zero or one appointment; an appointment may have many consultations. Optional FK uses `PROTECT`. This resolves M01's open cardinality permissively and needs confirmation. |
| StaffProfile to Consultation | One clinician may author many consultations; FK uses `PROTECT`. |
| Patient to MedicalHistoryEntry | One patient may have many entries; FK uses `PROTECT`. |
| StaffProfile to MedicalHistoryEntry | One staff profile may author many entries; FK uses `PROTECT`. |
| Appointment to AppointmentNotification | One appointment may have many notifications; FK uses `PROTECT`. |
| User to AppointmentNotification | Recipient may be absent; deletion uses `SET_NULL` to preserve the notification row. |
| User to AuditEvent | Actor may be absent; deletion uses `SET_NULL` to preserve the event. |
| AuditEvent to target | `GenericForeignKey` using content type and object ID; Django does not create a relational FK to the target row. |

## 5. Unique constraints and indexes

Database constraints:

- Unique `Patient.patient_identifier`.
- Unique `StaffProfile.staff_identifier` when non-null.
- Case-insensitive unique department name via `UniqueConstraint(Lower("name"))`.
- Non-empty patient full name (empty string is rejected; whitespace-only is not
  normalized by this constraint).
- Required patient `gender` value drawn from the approved choices.
- Staff role limited to Administrator, Receptionist, Clinician, or Nurse.
- Appointment status limited to Scheduled, Confirmed, Attended, Completed,
  Cancelled, or Missed.
- Appointment `ends_at` strictly later than `appointment_at`.
- A non-null recipient may have only one `appointment_reminder` notification
  per appointment; other notification types and recipient-less historical rows
  are not covered by this conditional unique constraint.
- One-to-one user/profile uniqueness is provided by Django's OneToOneField.

Explicit query indexes:

- Patient full name.
- Appointment by patient/start, clinician/start, and status/start.
- Consultation by patient/consultation time.
- Medical-history entry by patient/recorded time.
- Notification by recipient/read time.
- Audit event by actor/time, action/time, and generic target.

The `reconcile_appointment_reminders` management command creates a reminder
when the configured lead-time point is reached, updates reminders after a
reschedule, and removes reminders for cancelled, past, or otherwise ineligible
appointments. It must be invoked periodically by an external scheduler; Django
does not run the command automatically. See
[appointment_reminders.md](./appointment_reminders.md) for invocation and
polling-delay details.

Unique fields and foreign keys also receive database indexes as appropriate.
There is no database constraint preventing overlapping appointment intervals.
M07 performs application-level conflict validation for overlapping half-open
intervals on the same patient or clinician, excluding cancelled records. The
configurable technical default slot duration is 30 minutes
(`APPOINTMENT_DEFAULT_DURATION_MINUTES`); existing durations are preserved
when an appointment is edited. There are no buffers, clinic-hours, or provider
availability rules. SQLite does not provide a database exclusion constraint
for these intervals, so simultaneous conflicting writes remain a limitation.

## 6. Appointment status representation

Stored lowercase values and display labels:

| Stored value | Display |
|---|---|
| `scheduled` | Scheduled |
| `confirmed` | Confirmed |
| `attended` | Attended |
| `completed` | Completed |
| `cancelled` | Cancelled |
| `missed` | Missed |

A database check rejects values outside this set. M07 allows managers to
cancel appointments only from `scheduled` and `confirmed`; it does not permit
editing or cancelling terminal/clinical states. Attendance, completion, and
missed-state transitions are not implemented in M07. Cancellation is retained
on the appointment and recorded in the existing AuditEvent table.

## 7. Patient identifier strategy

On creation, `patient_identifier` defaults to `PT-` followed by an uppercase
random UUID4 hex string. It is independent from the primary key, not manually
editable through ordinary model forms, and protected by a unique database
constraint. The patient creation form safely retries identifier collisions.
The prefix/format is the current technical implementation choice; M01 approval
of the project requirements remains authoritative. No patient's age is stored;
date of birth is optional and age can be derived if a later approved feature
needs it.

## 8. Archival and deletion policies

- Patient archival uses `is_archived`; it does not delete the Patient row or
  cascade into appointments/history. Filtering archived rows and reactivation
  rules are not implemented.
- Staff profiles and departments have active flags. Account/profile and
  clinical-record references use protective deletion where attribution matters.
- Patient, appointment, clinician, author, and notification appointment
  references use `PROTECT` to block deletion that would orphan or erase
  historical records.
- Notification recipient and audit actor references use `SET_NULL` so their
  data can remain if an account is deleted.
- M2M department joins are not historical records and do not retain a deleted
  department association.
- No legal retention period or routine physical-deletion process has been set.

## 9. Data-integrity considerations

Database-enforced rules are in SQL constraints and foreign keys described
above. SQLite tests exercise these rules with invalid direct ORM inserts.

`Consultation.clean()` checks that an optional appointment belongs to the same
patient and clinician as the consultation. This is model-level validation only:
`save()` does not automatically call `full_clean()`, and the SQLite database
does not enforce this cross-table consistency. Future form/service code must
call validation and use transactions as appropriate.

Likewise, Django `choices` without an explicit check, string length validators,
phone/date plausibility, patient duplicate matching, role authorization,
appointment transition checks, overlapping intervals, cancellation policy,
and notification scheduling are not automatically enforced by database schema.

## 10. Known limitations and deferred rules

- M01 is approved. The patient demographic set includes the required `gender`
  field, and the current implementation follows the approved role matrix.
  Additional workflow-specific rules remain deferred to later milestones.
- Consultation and medical-history create, detail, and history workflows use
  the existing models and are restricted by clinician role and assigned-care
  scope. An additive `ConsultationRevision` model stores previous consultation
  values and the revising clinician before an authorized amendment. No
  existing clinical records are rewritten by this migration.
- Consultation amendments retain their previous version; separate medical
  history entries remain append-only and have no edit/delete workflow.
- AuditEvent has no automatic event writer, immutability guarantee, or
  tamper-protection. Do not put secrets or clinical-note contents in metadata.
- Appointment conflict checks are application-level and do not prevent every
  concurrent-write race in SQLite. Availability, cancellation windows,
  attendance/completion/missed transitions, external reminder delivery,
  data-retention schedule, backups/restores, and deployment security are
  deferred. Reminder record generation is implemented, but requires an
  external scheduler invocation.
- SQLite is for local development; concurrent use and production database
  selection have not been assessed.
- No real patient data should be used for testing or demonstration.
