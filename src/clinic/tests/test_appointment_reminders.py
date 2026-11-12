from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clinic.models import (
    AuditEvent,
    Appointment,
    AppointmentNotification,
    Department,
    Patient,
    StaffProfile,
)

User = get_user_model()


@override_settings(APPOINTMENT_REMINDER_LEAD_TIME_HOURS=24)
class AppointmentReminderCommandTests(TestCase):
    def setUp(self):
        department = Department.objects.create(name="General Practice")
        self.account = User.objects.create_user(
            username="reminder-clinician",
            email="clinician@example.test",
        )
        self.clinician = StaffProfile.objects.create(
            account=self.account,
            role=StaffProfile.Role.CLINICIAN,
        )
        self.clinician.departments.add(department)
        self.patient = Patient.objects.create(
            full_name="Fictional Reminder Patient",
        )

    def create_appointment(self, *, starts_in_hours=20, status=Appointment.Status.SCHEDULED):
        start = timezone.now() + timedelta(hours=starts_in_hours)
        return Appointment.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            appointment_at=start,
            ends_at=start + timedelta(minutes=30),
            status=status,
        )

    def run_command(self):
        output = StringIO()
        call_command("reconcile_appointment_reminders", stdout=output)
        return output.getvalue()

    def reminder_for(self, appointment):
        return AppointmentNotification.objects.get(
            appointment=appointment,
            recipient=self.account,
            notification_type="appointment_reminder",
        )

    def test_command_creates_reminder_when_lead_time_is_reached(self):
        appointment = self.create_appointment(starts_in_hours=20)

        output = self.run_command()

        reminder = self.reminder_for(appointment)
        expected_due = appointment.appointment_at - timedelta(hours=24)
        self.assertLessEqual(reminder.scheduled_for, timezone.now())
        self.assertAlmostEqual(
            reminder.scheduled_for.timestamp(),
            expected_due.timestamp(),
            delta=2,
        )
        self.assertIn("1 created", output)
        event = AuditEvent.objects.get(action="reminder.created")
        self.assertIsNone(event.actor)
        self.assertEqual(event.content_object, reminder)
        self.assertEqual(
            event.metadata,
            {
                "actor_kind": "system",
                "task": "reconcile_appointment_reminders",
            },
        )
        summary = AuditEvent.objects.get(
            action="reminder.reconciliation.completed"
        )
        self.assertIsNone(summary.actor)
        self.assertIsNone(summary.content_object)
        self.assertEqual(
            summary.metadata,
            {
                "actor_kind": "system",
                "task": "reconcile_appointment_reminders",
                "created": 1,
                "updated": 0,
                "removed": 0,
            },
        )

    def test_command_skips_appointments_not_yet_within_lead_time(self):
        appointment = self.create_appointment(starts_in_hours=30)

        output = self.run_command()

        self.assertFalse(
            AppointmentNotification.objects.filter(appointment=appointment).exists()
        )
        self.assertIn("1 skipped", output)

    def test_repeated_command_runs_do_not_duplicate_or_reset_read_reminders(self):
        appointment = self.create_appointment()
        self.run_command()
        reminder = self.reminder_for(appointment)
        read_at = timezone.now()
        reminder.read_at = read_at
        reminder.save(update_fields=("read_at", "updated_at"))

        self.run_command()
        self.run_command()

        reminder.refresh_from_db()
        self.assertEqual(
            AppointmentNotification.objects.filter(
                appointment=appointment,
                recipient=self.account,
                notification_type="appointment_reminder",
            ).count(),
            1,
        )
        self.assertEqual(reminder.read_at, read_at)
        self.assertEqual(
            AuditEvent.objects.filter(action="reminder.created").count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                action="reminder.reconciliation.completed"
            ).count(),
            1,
        )

    def test_no_change_reconciliation_emits_no_events(self):
        appointment = self.create_appointment(starts_in_hours=30)

        self.run_command()
        self.run_command()

        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(
            AppointmentNotification.objects.filter(appointment=appointment).exists()
        )

    def test_cancelled_appointment_removes_reminder_and_is_not_recreated(self):
        appointment = self.create_appointment(status=Appointment.Status.CANCELLED)
        reminder = AppointmentNotification.objects.create(
            appointment=appointment,
            recipient=self.account,
            notification_type="appointment_reminder",
            scheduled_for=timezone.now(),
        )

        self.run_command()

        self.assertFalse(AppointmentNotification.objects.filter(pk=reminder.pk).exists())
        event = AuditEvent.objects.get(action="reminder.removed")
        self.assertIsNone(event.actor)
        self.assertEqual(event.content_object, appointment)
        self.assertEqual(
            event.metadata,
            {
                "actor_kind": "system",
                "task": "reconcile_appointment_reminders",
                "notification_id": reminder.pk,
                "reason": "appointment_ineligible",
            },
        )
        summary = AuditEvent.objects.get(
            action="reminder.reconciliation.completed"
        )
        self.assertEqual(summary.metadata["removed"], 1)

    def test_rescheduling_recalculates_due_time_and_resets_read_state(self):
        appointment = self.create_appointment()
        self.run_command()
        reminder = self.reminder_for(appointment)
        reminder.read_at = timezone.now()
        reminder.save(update_fields=("read_at", "updated_at"))
        appointment.appointment_at += timedelta(hours=3)
        appointment.ends_at += timedelta(hours=3)
        appointment.save(update_fields=("appointment_at", "ends_at", "updated_at"))

        output = self.run_command()

        reminder.refresh_from_db()
        self.assertEqual(
            reminder.scheduled_for,
            appointment.appointment_at - timedelta(hours=24),
        )
        self.assertIsNone(reminder.read_at)
        self.assertIn("1 updated", output)
        update_event = AuditEvent.objects.get(action="reminder.updated")
        self.assertIsNone(update_event.actor)
        self.assertEqual(update_event.content_object, reminder)
        self.assertEqual(
            update_event.metadata,
            {
                "actor_kind": "system",
                "task": "reconcile_appointment_reminders",
            },
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                action="reminder.reconciliation.completed"
            ).count(),
            2,
        )

    def test_past_appointment_reminder_is_removed(self):
        appointment = self.create_appointment(starts_in_hours=-1)
        reminder = AppointmentNotification.objects.create(
            appointment=appointment,
            recipient=self.account,
            notification_type="appointment_reminder",
            scheduled_for=timezone.now() - timedelta(hours=25),
        )

        self.run_command()

        self.assertFalse(AppointmentNotification.objects.filter(pk=reminder.pk).exists())

    def test_completed_appointment_reminder_is_removed(self):
        appointment = self.create_appointment(status=Appointment.Status.COMPLETED)
        reminder = AppointmentNotification.objects.create(
            appointment=appointment,
            recipient=self.account,
            notification_type="appointment_reminder",
            scheduled_for=timezone.now(),
        )

        self.run_command()

        self.assertFalse(AppointmentNotification.objects.filter(pk=reminder.pk).exists())

    def test_inactive_clinician_does_not_receive_reminder(self):
        appointment = self.create_appointment()
        self.clinician.is_active = False
        self.clinician.save(update_fields=("is_active", "updated_at"))

        self.run_command()

        self.assertFalse(
            AppointmentNotification.objects.filter(appointment=appointment).exists()
        )

    def test_database_constraint_prevents_duplicate_reminder_keys(self):
        appointment = self.create_appointment()
        AppointmentNotification.objects.create(
            appointment=appointment,
            recipient=self.account,
            notification_type="appointment_reminder",
            scheduled_for=timezone.now(),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AppointmentNotification.objects.create(
                    appointment=appointment,
                    recipient=self.account,
                    notification_type="appointment_reminder",
                    scheduled_for=timezone.now(),
                )

    def test_audit_failure_rolls_back_reminder_creation_and_aborts_command(self):
        appointment = self.create_appointment()

        with patch(
            "clinic.appointment_reminders.record_audit_event",
            side_effect=RuntimeError("storage failure"),
        ):
            with self.assertRaisesMessage(RuntimeError, "storage failure"):
                self.run_command()

        self.assertFalse(
            AppointmentNotification.objects.filter(appointment=appointment).exists()
        )
        self.assertFalse(AuditEvent.objects.exists())

    def test_due_time_visibility_and_dashboard_unread_filter(self):
        now = timezone.now()
        unread_appointment = self.create_appointment(starts_in_hours=25)
        read_appointment = self.create_appointment(starts_in_hours=26)
        not_due_appointment = self.create_appointment(starts_in_hours=27)
        unread = AppointmentNotification.objects.create(
            appointment=unread_appointment,
            recipient=self.account,
            notification_type="appointment_reminder",
            scheduled_for=now + timedelta(minutes=1),
        )
        read = AppointmentNotification.objects.create(
            appointment=read_appointment,
            recipient=self.account,
            notification_type="appointment_reminder",
            scheduled_for=now,
            read_at=now,
        )
        future = AppointmentNotification.objects.create(
            appointment=not_due_appointment,
            recipient=self.account,
            notification_type="appointment_reminder",
            scheduled_for=now + timedelta(minutes=2),
        )
        self.client.force_login(self.account)

        with patch("clinic.appointment_views.timezone.now", return_value=now):
            reminders_before_due = self.client.get(
                reverse("clinic_appointments:appointment_reminders")
            )
        self.assertNotContains(
            reminders_before_due,
            unread_appointment.appointment_identifier,
        )
        self.assertNotContains(
            reminders_before_due,
            not_due_appointment.appointment_identifier,
        )
        self.assertContains(
            reminders_before_due,
            read_appointment.appointment_identifier,
        )
        self.assertContains(reminders_before_due, "Read")

        due_now = unread.scheduled_for
        with patch("clinic.appointment_views.timezone.now", return_value=due_now):
            reminders_at_due = self.client.get(
                reverse("clinic_appointments:appointment_reminders")
            )
        self.assertContains(
            reminders_at_due,
            unread_appointment.appointment_identifier,
        )
        self.assertContains(reminders_at_due, "Unread")
        self.assertNotContains(
            reminders_at_due,
            not_due_appointment.appointment_identifier,
        )

        with patch("clinic.auth_views.timezone.now", return_value=due_now):
            dashboard_at_due = self.client.get(reverse("clinic_auth:staff_home"))
        dashboard_reminder_ids = {
            reminder.pk
            for reminder in dashboard_at_due.context["upcoming_reminders"]
        }
        self.assertEqual(dashboard_reminder_ids, {unread.pk})
        self.assertNotIn(read.pk, dashboard_reminder_ids)
        self.assertNotIn(future.pk, dashboard_reminder_ids)
        self.assertTrue(AppointmentNotification.objects.filter(pk=read.pk).exists())
        self.assertTrue(AppointmentNotification.objects.filter(pk=future.pk).exists())
