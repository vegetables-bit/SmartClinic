from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from clinic.audit import (
    ACTION_SCHEMAS,
    AuditEventValidationError,
    record_audit_event,
    validate_audit_metadata,
)


class AuditMetadataValidationTests(SimpleTestCase):
    def test_existing_event_action_names_remain_registered(self):
        self.assertTrue(
            {
                "appointment.created",
                "appointment.updated",
                "appointment.rescheduled",
                "appointment.cancelled",
                "consultation.created",
                "consultation.amended",
                "medical_history.created",
                "nursing_observation.created",
                "staff.account.created",
                "staff.account.updated",
                "staff.role.changed",
                "staff.departments.changed",
                "staff.account.activated",
                "staff.account.deactivated",
                "auth.login.succeeded",
                "auth.login.failed",
                "auth.logout",
                "auth.password.changed",
                "auth.password_reset.requested",
                "auth.password_reset.completed",
                "reminder.created",
                "reminder.updated",
                "reminder.removed",
                "reminder.reconciliation.completed",
            }.issubset(ACTION_SCHEMAS)
        )

    def test_authentication_actions_require_empty_metadata(self):
        for action in (
            "auth.login.succeeded",
            "auth.login.failed",
            "auth.logout",
            "auth.password.changed",
            "auth.password_reset.requested",
            "auth.password_reset.completed",
        ):
            with self.subTest(action=action):
                validate_audit_metadata(action, {})

        with self.assertRaises(AuditEventValidationError):
            validate_audit_metadata(
                "auth.login.failed",
                {"username": "not permitted"},
            )

    def test_anonymous_authentication_actions_reject_user_attribution(self):
        authenticated_actor = SimpleNamespace(is_authenticated=True, pk=1)
        with self.assertRaises(AuditEventValidationError):
            record_audit_event(
                actor=authenticated_actor,
                action="auth.login.failed",
                target=None,
                metadata={},
            )

    def test_nursing_observation_audit_metadata_is_minimal_and_registered(self):
        validate_audit_metadata(
            "nursing_observation.created",
            {
                "patient_identifier": "PT-11111111111111111111111111111111",
                "record_id": 1,
            },
        )
        for prohibited_field in (
            "diagnosis",
            "notes",
            "temperature",
            "pulse",
            "password",
        ):
            with self.subTest(field=prohibited_field):
                with self.assertRaises(AuditEventValidationError):
                    validate_audit_metadata(
                        "nursing_observation.created",
                        {
                            "patient_identifier": "PT-11111111111111111111111111111111",
                            "record_id": 1,
                            prohibited_field: "not permitted",
                        },
                    )

    def test_reminder_metadata_is_registered_and_bounded(self):
        base = {
            "actor_kind": "system",
            "task": "reconcile_appointment_reminders",
        }
        validate_audit_metadata("reminder.created", base)
        validate_audit_metadata(
            "reminder.removed",
            {
                **base,
                "notification_id": 5,
                "reason": "appointment_ineligible",
            },
        )
        validate_audit_metadata(
            "reminder.reconciliation.completed",
            {
                **base,
                "created": 1,
                "updated": 0,
                "removed": 2,
            },
        )

        with self.assertRaises(AuditEventValidationError):
            validate_audit_metadata(
                "reminder.created",
                {**base, "message": "not permitted"},
            )

        with self.assertRaises(AuditEventValidationError):
            validate_audit_metadata(
                "reminder.removed",
                {
                    **base,
                    "notification_id": 5,
                    "reason": "patient_cancelled_because_of_diagnosis",
                },
            )

        with self.assertRaises(AuditEventValidationError):
            validate_audit_metadata(
                "reminder.reconciliation.completed",
                {
                    **base,
                    "created": True,
                    "updated": 0,
                    "removed": 0,
                },
            )

    def test_rejects_unregistered_action_and_unapproved_metadata(self):
        with self.assertRaises(AuditEventValidationError):
            validate_audit_metadata("patient.record_viewed", {})

        with self.assertRaises(AuditEventValidationError):
            validate_audit_metadata(
                "patient.created",
                {
                    "patient_identifier": "PT-11111111111111111111111111111111",
                    "record_id": 1,
                    "full_name": "Not permitted",
                },
            )

        with self.assertRaises(AuditEventValidationError):
            validate_audit_metadata(
                "staff.account.created",
                {"account_id": 1, "password": "not permitted"},
            )

    def test_rejects_invalid_metadata_types_and_field_names(self):
        with self.assertRaises(AuditEventValidationError):
            validate_audit_metadata(
                "patient.created",
                {
                    "patient_identifier": "PT-11111111111111111111111111111111",
                    "record_id": True,
                },
            )

        with self.assertRaises(AuditEventValidationError):
            validate_audit_metadata(
                "patient.demographics_updated",
                {
                    "patient_identifier": "PT-11111111111111111111111111111111",
                    "record_id": 1,
                    "changed_fields": ["password"],
                },
            )

    def test_rejects_oversized_or_unbounded_values(self):
        with self.assertRaises(AuditEventValidationError):
            validate_audit_metadata(
                "patient.created",
                {
                    "patient_identifier": "PT-" + ("1" * 38),
                    "record_id": 1,
                },
            )

        with patch("clinic.audit.MAX_METADATA_BYTES", 1):
            with self.assertRaises(AuditEventValidationError):
                validate_audit_metadata(
                    "patient.created",
                    {
                        "patient_identifier": "PT-11111111111111111111111111111111",
                        "record_id": 1,
                    },
                )
