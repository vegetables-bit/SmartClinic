import json
import re
from datetime import datetime

from django.db import models

from clinic.models import AuditEvent

MAX_METADATA_BYTES = 2048
APPOINTMENT_STATUSES = {
    "scheduled",
    "confirmed",
    "attended",
    "completed",
    "cancelled",
    "missed",
}
QUEUE_STATUSES = {
    "not_checked_in",
    "waiting",
    "called",
    "in_consultation",
    "completed",
}
PATIENT_FIELDS = {
    "full_name",
    "gender",
    "date_of_birth",
    "phone_number",
    "address",
    "emergency_contact_name",
    "emergency_contact_phone",
}
APPOINTMENT_FIELDS = {"patient", "clinician", "reason_for_visit", "schedule"}
CONSULTATION_FIELDS = {
    "consultation_at",
    "appointment",
    "symptoms",
    "diagnosis",
    "treatment",
    "clinician_notes",
}
STAFF_ACCOUNT_FIELDS = {
    "username",
    "first_name",
    "last_name",
    "email",
    "staff_identifier",
    "phone_number",
}
ANONYMOUS_ACTOR_ACTIONS = {
    "auth.login.failed",
    "auth.password_reset.requested",
    "auth.password_reset.completed",
}
TARGETLESS_ACTIONS = {
    "auth.login.failed",
    "auth.password_reset.requested",
    "reminder.reconciliation.completed",
}
SYSTEM_ACTOR_ACTIONS = {
    "reminder.created",
    "reminder.updated",
    "reminder.removed",
    "reminder.reconciliation.completed",
}


class AuditEventValidationError(ValueError):
    pass


ACTION_SCHEMAS = {
    "appointment.created": {
        "appointment_identifier": "appointment_identifier",
        "status": "appointment_status",
    },
    "appointment.updated": {"changed_fields": "appointment_fields"},
    "appointment.rescheduled": {
        "changed_fields": "rescheduled_fields",
        "previous_start": "datetime",
        "previous_end": "datetime",
        "new_start": "datetime",
        "new_end": "datetime",
    },
    "appointment.cancelled": {
        "appointment_identifier": "appointment_identifier",
        "previous_status": "appointment_status",
        "status": "appointment_status",
    },
    "queue.status_changed": {
        "appointment_identifier": "appointment_identifier",
        "previous_status": "queue_status",
        "status": "queue_status",
    },
    "consultation.created": {
        "patient_identifier": "patient_identifier",
        "record_id": "record_id",
    },
    "consultation.amended": {
        "patient_identifier": "patient_identifier",
        "record_id": "record_id",
        "changed_fields": "consultation_fields",
    },
    "medical_history.created": {
        "patient_identifier": "patient_identifier",
        "record_id": "record_id",
    },
    "nursing_observation.created": {
        "patient_identifier": "patient_identifier",
        "record_id": "record_id",
    },
    "patient.created": {
        "patient_identifier": "patient_identifier",
        "record_id": "record_id",
    },
    "patient.demographics_updated": {
        "patient_identifier": "patient_identifier",
        "record_id": "record_id",
        "changed_fields": "patient_fields",
    },
    "patient.archived": {
        "patient_identifier": "patient_identifier",
        "record_id": "record_id",
        "previous_is_archived": "false",
        "is_archived": "true",
    },
    "patient.restored": {
        "patient_identifier": "patient_identifier",
        "record_id": "record_id",
        "previous_is_archived": "true",
        "is_archived": "false",
    },
    "staff.account.created": {"account_id": "record_id"},
    "staff.account.updated": {
        "account_id": "record_id",
        "changed_fields": "staff_account_fields",
    },
    "staff.role.changed": {
        "account_id": "record_id",
        "changed_fields": "staff_role_fields",
    },
    "staff.departments.changed": {
        "account_id": "record_id",
        "changed_fields": "staff_department_fields",
    },
    "staff.account.activated": {"account_id": "record_id"},
    "staff.account.deactivated": {"account_id": "record_id"},
    "auth.login.succeeded": {},
    "auth.login.failed": {},
    "auth.logout": {},
    "auth.password.changed": {},
    "auth.password_reset.requested": {},
    "auth.password_reset.completed": {},
    "reminder.created": {
        "actor_kind": "system_actor_kind",
        "task": "reminder_task",
    },
    "reminder.updated": {
        "actor_kind": "system_actor_kind",
        "task": "reminder_task",
    },
    "reminder.removed": {
        "actor_kind": "system_actor_kind",
        "task": "reminder_task",
        "notification_id": "record_id",
        "reason": "reminder_removal_reason",
    },
    "reminder.reconciliation.completed": {
        "actor_kind": "system_actor_kind",
        "task": "reminder_task",
        "created": "count",
        "updated": "count",
        "removed": "count",
    },
}


def _validate_value(kind, value, key):
    if kind in {
        "appointment_identifier",
        "patient_identifier",
        "datetime",
    }:
        if not isinstance(value, str) or not value or len(value) > 40:
            raise AuditEventValidationError(f"Invalid value for metadata field {key}.")
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise AuditEventValidationError(f"Invalid value for metadata field {key}.")
        if kind == "datetime":
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError as error:
                raise AuditEventValidationError(
                    f"Invalid value for metadata field {key}."
                ) from error
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise AuditEventValidationError(
                    f"Invalid value for metadata field {key}."
                )
        elif kind == "appointment_identifier" and not re.fullmatch(
            r"AP-\d{6,}", value
        ):
            raise AuditEventValidationError(
                f"Invalid value for metadata field {key}."
            )
        elif kind == "patient_identifier" and not re.fullmatch(
            r"PT-[A-F0-9]{32}", value
        ):
            raise AuditEventValidationError(
                f"Invalid value for metadata field {key}."
            )
        return

    if kind == "record_id":
        if type(value) is not int or value < 1:
            raise AuditEventValidationError(f"Invalid value for metadata field {key}.")
        return

    if kind in {"appointment_status", "previous_status", "status"}:
        if not isinstance(value, str) or value not in APPOINTMENT_STATUSES:
            raise AuditEventValidationError(f"Invalid value for metadata field {key}.")
        return

    if kind == "queue_status":
        if not isinstance(value, str) or value not in QUEUE_STATUSES:
            raise AuditEventValidationError(f"Invalid value for metadata field {key}.")
        return

    if kind in {"false", "true"}:
        expected = kind == "true"
        if type(value) is not bool or value is not expected:
            raise AuditEventValidationError(f"Invalid value for metadata field {key}.")
        return

    if kind == "system_actor_kind":
        if value != "system":
            raise AuditEventValidationError(f"Invalid value for metadata field {key}.")
        return

    if kind == "reminder_task":
        if value != "reconcile_appointment_reminders":
            raise AuditEventValidationError(f"Invalid value for metadata field {key}.")
        return

    if kind == "reminder_removal_reason":
        if value not in {
            "appointment_ineligible",
            "reminder_not_due",
            "recipient_changed",
        }:
            raise AuditEventValidationError(f"Invalid value for metadata field {key}.")
        return

    if kind == "count":
        if type(value) is not int or not 0 <= value <= 1_000_000:
            raise AuditEventValidationError(f"Invalid value for metadata field {key}.")
        return

    allowed_fields = {
        "appointment_fields": APPOINTMENT_FIELDS - {"schedule"},
        "rescheduled_fields": APPOINTMENT_FIELDS,
        "consultation_fields": CONSULTATION_FIELDS,
        "patient_fields": PATIENT_FIELDS,
        "staff_account_fields": STAFF_ACCOUNT_FIELDS,
        "staff_role_fields": {"role"},
        "staff_department_fields": {"departments"},
    }
    if kind in allowed_fields:
        if (
            not isinstance(value, list)
            or not value
            or len(value) > len(allowed_fields[kind])
            or any(
                not isinstance(field, str) or field not in allowed_fields[kind]
                for field in value
            )
            or len(set(value)) != len(value)
        ):
            raise AuditEventValidationError(f"Invalid value for metadata field {key}.")
        return

    raise AuditEventValidationError("Unsupported audit metadata schema.")


def validate_audit_metadata(action, metadata):
    schema = ACTION_SCHEMAS.get(action)
    if schema is None:
        raise AuditEventValidationError("Unregistered audit action.")
    if not isinstance(metadata, dict) or set(metadata) != set(schema):
        raise AuditEventValidationError("Audit metadata does not match its schema.")

    for key, kind in schema.items():
        _validate_value(kind, metadata[key], key)

    if action == "appointment.created" and metadata["status"] != "scheduled":
        raise AuditEventValidationError("Invalid status for appointment creation.")
    if action == "appointment.rescheduled" and "schedule" not in metadata[
        "changed_fields"
    ]:
        raise AuditEventValidationError("A reschedule event must include the schedule.")
    if action == "appointment.cancelled" and (
        metadata["previous_status"] not in {"scheduled", "confirmed"}
        or metadata["status"] != "cancelled"
    ):
        raise AuditEventValidationError("Invalid appointment cancellation transition.")

    try:
        encoded = json.dumps(metadata, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError) as error:
        raise AuditEventValidationError(
            "Audit metadata must contain JSON values."
        ) from error
    if len(encoded.encode("ascii")) > MAX_METADATA_BYTES:
        raise AuditEventValidationError("Audit metadata exceeds the allowed size.")


def record_audit_event(*, actor, action, target, metadata):
    if action in SYSTEM_ACTOR_ACTIONS:
        if actor is not None:
            raise AuditEventValidationError(
                "This audit action requires a system actor."
            )
    elif action in ANONYMOUS_ACTOR_ACTIONS:
        if actor is not None:
            raise AuditEventValidationError(
                "This audit action requires an anonymous actor."
            )
    elif (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or actor.pk is None
    ):
        raise AuditEventValidationError("An authenticated actor is required.")
    if target is None:
        if action not in TARGETLESS_ACTIONS:
            raise AuditEventValidationError("A saved target record is required.")
    elif not isinstance(target, models.Model) or target.pk is None:
        raise AuditEventValidationError("A saved target record is required.")

    validate_audit_metadata(action, metadata)
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        content_object=target,
        metadata=metadata,
    )
