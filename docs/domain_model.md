# Domain model and database mapping

> **Status: IMPLEMENTATION REFERENCE FOR THE APPROVED M01 BASELINE.** M01 is
> approved and remains authoritative. This document records the implemented
> schema; it does not add new clinical or operational policy. Where the
> approved requirements do not specify a technical detail, this document
> identifies the current implementation choice.

## Django application organization

M02 implements one non-empty Django application, `clinic`, with model code
split by domain responsibility under `src/clinic/models/`:

- `organization.py`: Department and StaffProfile.
- `patients.py`: Patient and patient identifier generation.
- `appointments.py`: Appointment and stored status values.
- `clinical.py`: Consultation and MedicalHistoryEntry.
- `notifications.py`: AppointmentNotification.
- `audit.py`: AuditEvent.
- `base.py`: shared abstract timestamps.

The shared app is a proportionate database foundation for these related records;
it avoids several artificial apps with tightly coupled foreign keys. The
modules remain separately organized. Splitting into focused Django apps can be
revisited when workflows/ownership justify it.

## Entity mapping

| Entity/table | Purpose and principal fields |
|---|---|
| Django `auth_user` | Existing built-in account and credential record. M02 does not replace Django's user model or add login workflows. |
| `clinic_department` | `id` primary key; `name`, optional `description`, `is_active`, `created_at`, `updated_at`. Department names are unique case-insensitively. |
| `clinic_staffprofile` | `id`; one-to-one protected `account`; optional unique `staff_identifier`; `role` choice; optional `phone_number`; `is_active`; timestamps; many-to-many `departments`. |
| `clinic_patient` | `id`; unique generated `patient_identifier`; required `full_name` and `gender`; optional `date_of_birth`, phone, address, emergency contact name/phone; `is_archived`; timestamps. |
| `clinic_appointment` | `id`; protected patient and clinician profile foreign keys; `appointment_at`, `ends_at`, optional `reason_for_visit`, status, optional `cancellation_reason`; timestamps. |
| `clinic_consultation` | `id`; protected patient and clinician foreign keys; optional protected appointment foreign key; `consultation_at`; optional symptoms, diagnosis, treatment, and clinician notes; timestamps. |
| `clinic_medicalhistoryentry` | `id`; protected patient and author profile foreign keys; required `entry_text`; optional `effective_date`; `recorded_at`; timestamps. This is a separately authored longitudinal note, not a duplicate consultation. |
| `clinic_appointmentnotification` | `id`; protected appointment foreign key; optional recipient account (set null if removed); `notification_type`; optional `scheduled_for` and `read_at`; timestamps. This stores in-app notification metadata only. |
| `clinic_auditevent` | `id`; optional actor account (set null if removed); action, event timestamp, optional generic content-type/object identifier, and JSON metadata. A generic target is not a database-enforced foreign key. |

All tables use Django's `BigAutoField` primary key unless the entity is part of
the implicit many-to-many relation table. The generated patient identifier is
distinct from the database key.

## Relationships and cardinalities

```text
auth_user       1 ── 0..1 StaffProfile
Department      * ── * StaffProfile
Patient         1 ── * Appointment
StaffProfile    1 ── * Appointment (assigned clinician)
Patient         1 ── * Consultation
StaffProfile    1 ── * Consultation (clinician/author)
Appointment     1 ── 0..* Consultation (each Consultation may have no Appointment)
Patient         1 ── * MedicalHistoryEntry
StaffProfile    1 ── * MedicalHistoryEntry (author)
Appointment     1 ── * AppointmentNotification
auth_user       0..1 ── * AppointmentNotification (recipient)
auth_user       0..1 ── * AuditEvent (actor)
```

The implementation uses an optional foreign key from Consultation to
Appointment, permitting multiple consultations per appointment and a
consultation without an appointment. The approved requirements do not specify
an exact appointment-to-consultation cardinality; this is the current schema
choice and may be revised if a detailed workflow requirement is approved.

## Implemented data choices

- `Patient.full_name` and `Patient.gender` are required by the implemented
  demographic form/model. Gender choices are female, male, non-binary, and
  prefer not to say. Date of birth and contact fields remain optional in the
  current model.
- Staff department membership is many-to-many, reusing the existing
  `Department` model.
- Patient identifier uses `PT-` plus a random UUID4 hexadecimal value. Its
  uniqueness is enforced by the database, and the patient creation workflow
  retries safely after a collision.
- Appointment statuses are `scheduled`, `confirmed`, `attended`, `completed`,
  `cancelled`, and `missed`. The model validates these values; transition
  enforcement is not implemented.
- MedicalHistoryEntry is separate to represent attributable longitudinal notes
  independent of an individual appointment; no clinical categories or decision
  rules are imposed.

## Deletion and archival

- Patient and appointment/clinical record foreign keys use `PROTECT` where a
  delete could destroy historical relationships.
- A patient can be marked `is_archived`; appointments and clinical records
  remain linked. Archiving does not automatically hide records or authorize
  access; later application behavior and retention policy are still needed.
- User-to-profile and staff-to-clinical-record references are protected to
  preserve attribution. Deactivate accounts/profiles instead of deleting them
  when appropriate.
- Deleting a notification recipient or audit actor sets the account reference
  to null while retaining the event/notification row.
- Department active state supports deactivation. The implicit many-to-many
  table does not preserve a deleted department's historical assignment.
- No retention duration, physical-deletion authorization, or legal retention
  rule is defined.

For constraints and application-level limitations, see
[database_design.md](./database_design.md).
