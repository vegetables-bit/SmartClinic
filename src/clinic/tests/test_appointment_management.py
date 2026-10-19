from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clinic.appointment_reminders import sync_appointment_reminder

from clinic.appointment_reminders import sync_appointment_reminder
from clinic.models import (
    Appointment,
    AppointmentNotification,
    AuditEvent,
    Department,
    Patient,
    StaffProfile,
)

User = get_user_model()
PASSWORD = "S3cure-Clinic-Password-927!"


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class AppointmentManagementTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="General Practice")
        self.admin = self.create_staff("admin", StaffProfile.Role.ADMINISTRATOR)
        self.receptionist = self.create_staff(
            "reception",
            StaffProfile.Role.RECEPTIONIST,
        )
        self.clinician = self.create_staff("doctor", StaffProfile.Role.CLINICIAN)
        self.other_clinician = self.create_staff(
            "doctor2",
            StaffProfile.Role.CLINICIAN,
        )
        self.nurse = self.create_staff("nurse", StaffProfile.Role.NURSE)
        self.patient = Patient.objects.create(
            full_name="Fictional Patient",
            gender=Patient.Gender.FEMALE,
        )
        self.other_patient = Patient.objects.create(
            full_name="Another Fictional Patient",
            gender=Patient.Gender.MALE,
        )

    def create_staff(self, username, role, *, active=True):
        account = User.objects.create_user(
            username=username,
            email=f"{username}@example.test",
            password=PASSWORD,
            is_active=active,
        )
        profile = StaffProfile.objects.create(
            account=account,
            role=role,
            is_active=active,
        )
        profile.departments.add(self.department)
        return profile

    def login_as(self, profile):
        self.client.force_login(profile.account)

    def post_data(self, **overrides):
        data = {
            "patient": str(self.patient.pk),
            "clinician": str(self.clinician.pk),
            "appointment_date": (timezone.localdate() + timedelta(days=10)).isoformat(),
            "appointment_time": "09:00",
            "reason_for_visit": "Routine follow-up",
        }
        data.update(overrides)
        return data

    def aware_datetime(self, appointment_date, appointment_time):
        return timezone.make_aware(
            datetime.combine(appointment_date, appointment_time),
            timezone.get_current_timezone(),
        )

    def create_appointment(
        self,
        *,
        patient=None,
        clinician=None,
        appointment_date=None,
        appointment_time=None,
        duration=30,
        status=Appointment.Status.SCHEDULED,
    ):
        appointment_date = appointment_date or timezone.localdate() + timedelta(days=10)
        appointment_time = appointment_time or time(9)
        start = self.aware_datetime(appointment_date, appointment_time)
        appointment = Appointment.objects.create(
            patient=patient or self.patient,
            clinician=clinician or self.clinician,
            appointment_at=start,
            ends_at=start + timedelta(minutes=duration),
            reason_for_visit="Fictional appointment",
            status=status,
        )
        return appointment

    def test_receptionist_can_create_and_persist_appointment(self):
        self.login_as(self.receptionist)

        response = self.client.post(
            reverse("clinic_appointments:appointment_create"),
            self.post_data(),
        )

        appointment = Appointment.objects.get()
        self.assertRedirects(
            response,
            reverse(
                "clinic_appointments:appointment_detail",
                args=[appointment.pk],
            ),
        )
        self.assertEqual(appointment.patient, self.patient)
        self.assertEqual(appointment.clinician, self.clinician)
        self.assertEqual(appointment.status, Appointment.Status.SCHEDULED)
        self.assertEqual(appointment.appointment_at.date(), timezone.localdate() + timedelta(days=10))
        self.assertEqual(appointment.ends_at - appointment.appointment_at, timedelta(minutes=30))
        self.assertTrue(
            AuditEvent.objects.filter(
                action="appointment.created",
                actor=self.receptionist.account,
                object_id=str(appointment.pk),
            ).exists()
        )

    def test_required_fields_return_visible_field_errors(self):
        self.login_as(self.receptionist)

        response = self.client.post(
            reverse("clinic_appointments:appointment_create"),
            self.post_data(
                patient="",
                clinician="",
                appointment_date="",
                appointment_time="",
                reason_for_visit="",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Appointment.objects.count(), 0)
        form = response.context["form"]
        for field in (
            "patient",
            "clinician",
            "appointment_date",
            "appointment_time",
            "reason_for_visit",
        ):
            with self.subTest(field=field):
                self.assertIn(field, form.errors)
                self.assertContains(response, form[field].errors[0])

    def test_invalid_references_and_archived_patient_are_rejected(self):
        archived_patient = Patient.objects.create(
            full_name="Archived Fictional Patient",
            is_archived=True,
        )
        inactive_clinician = self.create_staff(
            "inactive_doctor",
            StaffProfile.Role.CLINICIAN,
            active=False,
        )
        self.login_as(self.admin)

        for values in (
            {"patient": str(archived_patient.pk)},
            {"clinician": str(self.receptionist.pk)},
            {"clinician": str(inactive_clinician.pk)},
        ):
            with self.subTest(values=values):
                response = self.client.post(
                    reverse("clinic_appointments:appointment_create"),
                    self.post_data(**values),
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertEqual(Appointment.objects.count(), 0)

    def test_invalid_date_and_time_are_rejected(self):
        self.login_as(self.admin)

        response = self.client.post(
            reverse("clinic_appointments:appointment_create"),
            self.post_data(appointment_date="not-a-date", appointment_time="27:80"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("appointment_date", response.context["form"].errors)
        self.assertIn("appointment_time", response.context["form"].errors)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_same_clinician_overlapping_interval_is_rejected(self):
        appointment_date = timezone.localdate() + timedelta(days=10)
        self.create_appointment(
            appointment_date=appointment_date,
            appointment_time=time(9),
        )
        self.login_as(self.receptionist)

        response = self.client.post(
            reverse("clinic_appointments:appointment_create"),
            self.post_data(
                patient=str(self.other_patient.pk),
                appointment_date=appointment_date.isoformat(),
                appointment_time="09:15",
            ),
        )

        self.assertIn("clinician", response.context["form"].errors)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_same_patient_overlapping_interval_is_rejected_for_other_clinician(self):
        appointment_date = timezone.localdate() + timedelta(days=10)
        self.create_appointment(
            appointment_date=appointment_date,
            appointment_time=time(9),
        )
        self.login_as(self.admin)

        response = self.client.post(
            reverse("clinic_appointments:appointment_create"),
            self.post_data(
                clinician=str(self.other_clinician.pk),
                appointment_date=appointment_date.isoformat(),
                appointment_time="09:15",
            ),
        )

        self.assertIn("patient", response.context["form"].errors)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_adjacent_bookings_are_allowed(self):
        appointment_date = timezone.localdate() + timedelta(days=10)
        self.create_appointment(
            appointment_date=appointment_date,
            appointment_time=time(9),
        )
        self.login_as(self.receptionist)

        response = self.client.post(
            reverse("clinic_appointments:appointment_create"),
            self.post_data(
                patient=str(self.other_patient.pk),
                appointment_date=appointment_date.isoformat(),
                appointment_time="09:30",
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Appointment.objects.count(), 2)

    def test_cancelled_appointments_do_not_block_a_new_booking(self):
        appointment_date = timezone.localdate() + timedelta(days=10)
        self.create_appointment(
            appointment_date=appointment_date,
            appointment_time=time(9),
            status=Appointment.Status.CANCELLED,
        )
        self.login_as(self.admin)

        response = self.client.post(
            reverse("clinic_appointments:appointment_create"),
            self.post_data(
                appointment_date=appointment_date.isoformat(),
                appointment_time="09:15",
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Appointment.objects.count(), 2)

    def test_edit_revalidates_conflicts_and_preserves_original_on_error(self):
        appointment_date = timezone.localdate() + timedelta(days=10)
        existing = self.create_appointment(
            appointment_date=appointment_date,
            appointment_time=time(9),
        )
        moving = self.create_appointment(
            patient=self.other_patient,
            clinician=self.other_clinician,
            appointment_date=appointment_date,
            appointment_time=time(11),
        )
        self.login_as(self.admin)

        response = self.client.post(
            reverse("clinic_appointments:appointment_edit", args=[moving.pk]),
            self.post_data(
                patient=str(existing.patient_id),
                clinician=str(existing.clinician_id),
                appointment_date=appointment_date.isoformat(),
                appointment_time="09:15",
            ),
        )

        self.assertEqual(response.status_code, 200)
        moving.refresh_from_db()
        self.assertEqual(moving.appointment_at.time(), time(11))
        self.assertEqual(Appointment.objects.count(), 2)

    def test_reschedule_persists_new_time_and_audits_previous_schedule(self):
        appointment = self.create_appointment()
        old_start = appointment.appointment_at
        new_date = timezone.localdate() + timedelta(days=11)
        self.login_as(self.receptionist)

        response = self.client.post(
            reverse("clinic_appointments:appointment_edit", args=[appointment.pk]),
            self.post_data(
                appointment_date=new_date.isoformat(),
                appointment_time="10:30",
            ),
        )

        self.assertRedirects(
            response,
            reverse("clinic_appointments:appointment_detail", args=[appointment.pk]),
        )
        appointment.refresh_from_db()
        self.assertEqual(appointment.appointment_at.date(), new_date)
        event = AuditEvent.objects.get(
            action="appointment.rescheduled",
            object_id=str(appointment.pk),
        )
        self.assertEqual(event.actor, self.receptionist.account)
        self.assertEqual(event.metadata["previous_start"], old_start.isoformat())
        self.assertEqual(event.metadata["new_start"], appointment.appointment_at.isoformat())

    def test_editing_reason_preserves_existing_appointment_duration(self):
        appointment = self.create_appointment(duration=45)
        self.login_as(self.admin)

        response = self.client.post(
            reverse("clinic_appointments:appointment_edit", args=[appointment.pk]),
            self.post_data(reason_for_visit="Updated fictional reason"),
        )

        self.assertEqual(response.status_code, 302)
        appointment.refresh_from_db()
        self.assertEqual(appointment.ends_at - appointment.appointment_at, timedelta(minutes=45))

    def test_list_searches_by_appointment_identifier_and_patient(self):
        appointment = self.create_appointment()
        self.login_as(self.receptionist)

        for query in (appointment.appointment_identifier, self.patient.patient_identifier, self.patient.full_name):
            with self.subTest(query=query):
                response = self.client.get(
                    reverse("clinic_appointments:appointment_list"),
                    {"query": query},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(list(response.context["appointments"]), [appointment])

    def test_list_filters_by_date_status_and_clinician(self):
        first = self.create_appointment()
        second = self.create_appointment(
            patient=self.other_patient,
            clinician=self.other_clinician,
            appointment_date=timezone.localdate() + timedelta(days=12),
            appointment_time=time(13),
            status=Appointment.Status.CONFIRMED,
        )
        self.login_as(self.admin)

        response = self.client.get(
            reverse("clinic_appointments:appointment_list"),
            {
                "appointment_date": (timezone.localdate() + timedelta(days=12)).isoformat(),
                "status": Appointment.Status.CONFIRMED,
                "clinician": str(self.other_clinician.pk),
            },
        )

        self.assertEqual(list(response.context["appointments"]), [second])
        self.assertNotIn(first, response.context["appointments"])

    def test_list_supports_upcoming_and_status_categories(self):
        upcoming = self.create_appointment()
        completed = self.create_appointment(
            patient=self.other_patient,
            clinician=self.other_clinician,
            appointment_date=timezone.localdate() - timedelta(days=2),
            status=Appointment.Status.COMPLETED,
        )
        cancelled = self.create_appointment(
            patient=self.other_patient,
            clinician=self.other_clinician,
            appointment_date=timezone.localdate() - timedelta(days=1),
            status=Appointment.Status.CANCELLED,
        )
        missed = self.create_appointment(
            patient=self.other_patient,
            clinician=self.other_clinician,
            appointment_date=timezone.localdate() - timedelta(days=3),
            status=Appointment.Status.MISSED,
        )
        self.login_as(self.admin)

        for category, expected in (
            ("upcoming", [upcoming]),
            ("completed", [completed]),
            ("cancelled", [cancelled]),
            ("missed", [missed]),
        ):
            with self.subTest(category=category):
                response = self.client.get(
                    reverse("clinic_appointments:appointment_list"),
                    {"category": category},
                )
                self.assertEqual(list(response.context["appointments"]), expected)

    def test_list_has_empty_state_and_paginates(self):
        self.login_as(self.receptionist)
        empty_response = self.client.get(
            reverse("clinic_appointments:appointment_list"),
            {"query": "no matching patient"},
        )
        self.assertContains(empty_response, "No appointments match these filters.")

        for index in range(26):
            self.create_appointment(
                patient=self.patient if index % 2 == 0 else self.other_patient,
                clinician=self.clinician if index % 2 == 0 else self.other_clinician,
                appointment_date=timezone.localdate() + timedelta(days=20 + index),
            )
        first_page = self.client.get(reverse("clinic_appointments:appointment_list"))
        second_page = self.client.get(
            reverse("clinic_appointments:appointment_list"),
            {"page": "2"},
        )
        self.assertEqual(first_page.context["appointments"].paginator.count, 26)
        self.assertEqual(len(first_page.context["appointments"]), 25)
        self.assertEqual(len(second_page.context["appointments"]), 1)

    def test_manager_and_assigned_clinician_can_view_details(self):
        appointment = self.create_appointment()
        url = reverse("clinic_appointments:appointment_detail", args=[appointment.pk])
        for profile in (self.admin, self.receptionist, self.clinician):
            with self.subTest(role=profile.role):
                self.login_as(profile)
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_clinician_can_only_view_assigned_appointments(self):
        appointment = self.create_appointment(clinician=self.other_clinician)
        self.login_as(self.clinician)

        response = self.client.get(
            reverse("clinic_appointments:appointment_detail", args=[appointment.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_clinician_cannot_manage_appointments_and_nurse_is_denied(self):
        create_url = reverse("clinic_appointments:appointment_create")
        list_url = reverse("clinic_appointments:appointment_list")
        appointment = self.create_appointment()
        edit_url = reverse("clinic_appointments:appointment_edit", args=[appointment.pk])
        cancel_url = reverse("clinic_appointments:appointment_cancel", args=[appointment.pk])

        self.login_as(self.clinician)
        self.assertEqual(self.client.get(list_url).status_code, 200)
        for url in (create_url, edit_url):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(cancel_url).status_code, 403)

        self.login_as(self.nurse)
        for url in (list_url, create_url, edit_url):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(cancel_url).status_code, 403)

    def test_unauthenticated_user_is_redirected_and_unknown_id_is_404(self):
        list_url = reverse("clinic_appointments:appointment_list")
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("clinic_auth:login"), response.url)

        self.login_as(self.admin)
        self.assertEqual(
            self.client.get(
                reverse("clinic_appointments:appointment_detail", args=[999999])
            ).status_code,
            404,
        )

    def test_cancellation_is_post_only_and_records_event(self):
        appointment = self.create_appointment(status=Appointment.Status.CONFIRMED)
        url = reverse("clinic_appointments:appointment_cancel", args=[appointment.pk])
        self.login_as(self.receptionist)

        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(
            url,
            {"cancellation_reason": "Patient requested a new date"},
        )

        self.assertRedirects(
            response,
            reverse("clinic_appointments:appointment_detail", args=[appointment.pk]),
        )
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)
        self.assertEqual(appointment.cancellation_reason, "Patient requested a new date")
        event = AuditEvent.objects.get(
            action="appointment.cancelled",
            object_id=str(appointment.pk),
        )
        self.assertEqual(event.metadata["previous_status"], Appointment.Status.CONFIRMED)

    def test_completed_appointment_cannot_be_cancelled_or_edited(self):
        appointment = self.create_appointment(status=Appointment.Status.COMPLETED)
        self.login_as(self.admin)

        cancel_response = self.client.post(
            reverse("clinic_appointments:appointment_cancel", args=[appointment.pk])
        )
        edit_response = self.client.get(
            reverse("clinic_appointments:appointment_edit", args=[appointment.pk])
        )

        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.COMPLETED)
        self.assertRedirects(
            cancel_response,
            reverse("clinic_appointments:appointment_detail", args=[appointment.pk]),
        )
        self.assertRedirects(
            edit_response,
            reverse("clinic_appointments:appointment_detail", args=[appointment.pk]),
        )
        self.assertFalse(AuditEvent.objects.filter(object_id=str(appointment.pk)).exists())

    def test_cancelled_appointment_cannot_be_edited(self):
        appointment = self.create_appointment(status=Appointment.Status.CANCELLED)
        self.login_as(self.admin)

        response = self.client.get(
            reverse("clinic_appointments:appointment_edit", args=[appointment.pk])
        )

        self.assertRedirects(
            response,
            reverse("clinic_appointments:appointment_detail", args=[appointment.pk]),
        )

    def test_edit_form_cannot_apply_unapproved_status_transitions(self):
        appointment = self.create_appointment(status=Appointment.Status.SCHEDULED)
        self.login_as(self.admin)

        response = self.client.post(
            reverse("clinic_appointments:appointment_edit", args=[appointment.pk]),
            self.post_data(
                appointment_date=(timezone.localdate() + timedelta(days=11)).isoformat(),
                appointment_time="10:00",
                status=Appointment.Status.ATTENDED,
            ),
        )

        self.assertEqual(response.status_code, 302)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.SCHEDULED)
        self.assertFalse(
            AuditEvent.objects.filter(
                action="appointment.status_changed",
                object_id=str(appointment.pk),
            ).exists()
        )

    def test_cancellation_requires_csrf_token(self):
        appointment = self.create_appointment()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin.account)
        detail = client.get(
            reverse("clinic_appointments:appointment_detail", args=[appointment.pk])
        )
        csrf_token = detail.cookies["csrftoken"].value
        cancel_url = reverse("clinic_appointments:appointment_cancel", args=[appointment.pk])

        rejected = client.post(cancel_url)
        self.assertEqual(rejected.status_code, 403)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.SCHEDULED)

        accepted = client.post(cancel_url, HTTP_X_CSRFTOKEN=csrf_token)
        self.assertEqual(accepted.status_code, 302)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)

    def test_appointment_creation_creates_reminder_for_assigned_clinician(self):
        appointment = self.create_appointment()
        appointment.appointment_at = timezone.now() + timedelta(hours=12)
        appointment.ends_at = appointment.appointment_at + timedelta(minutes=30)
        appointment.save(update_fields=("appointment_at", "ends_at", "updated_at"))
        sync_appointment_reminder(appointment)
        reminder = AppointmentNotification.objects.get(
            appointment=appointment,
            recipient=self.clinician.account,
        )
        self.assertEqual(reminder.notification_type, "appointment_reminder")
        self.assertIsNotNone(reminder.scheduled_for)
        self.assertIsNone(reminder.read_at)

    def test_cancelled_appointments_do_not_keep_active_reminders(self):
        appointment = self.create_appointment()
        reminder = AppointmentNotification.objects.create(
            appointment=appointment,
            recipient=self.clinician.account,
            notification_type="appointment_reminder",
            scheduled_for=appointment.appointment_at - timedelta(hours=24),
        )
        self.assertTrue(AppointmentNotification.objects.filter(pk=reminder.pk).exists())

        self.login_as(self.admin)
        response = self.client.post(
            reverse("clinic_appointments:appointment_cancel", args=[appointment.pk]),
            {"cancellation_reason": "No-show"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            AppointmentNotification.objects.filter(
                appointment=appointment,
                recipient=self.clinician.account,
            ).exists()
        )

    def test_duplicate_reminders_are_not_created_for_same_appointment(self):
        appointment = self.create_appointment()
        appointment.appointment_at = timezone.now() + timedelta(hours=12)
        appointment.ends_at = appointment.appointment_at + timedelta(minutes=30)
        appointment.save(update_fields=("appointment_at", "ends_at", "updated_at"))
        sync_appointment_reminder(appointment)
        sync_appointment_reminder(appointment)
        self.assertEqual(
            AppointmentNotification.objects.filter(
                appointment=appointment,
                recipient=self.clinician.account,
                notification_type="appointment_reminder",
            ).count(),
            1,
        )

    def test_rescheduling_replaces_the_existing_reminder(self):
        appointment = self.create_appointment()
        appointment.appointment_at = timezone.now() + timedelta(hours=20)
        appointment.ends_at = appointment.appointment_at + timedelta(minutes=30)
        appointment.save(update_fields=("appointment_at", "ends_at", "updated_at"))
        original = AppointmentNotification.objects.create(
            appointment=appointment,
            recipient=self.clinician.account,
            notification_type="appointment_reminder",
            scheduled_for=appointment.appointment_at - timedelta(hours=24),
            read_at=timezone.now(),
        )
        appointment.appointment_at += timedelta(hours=2)
        appointment.ends_at += timedelta(hours=2)
        appointment.save(update_fields=("appointment_at", "ends_at", "updated_at"))
        sync_appointment_reminder(appointment)

        reminder = AppointmentNotification.objects.get(pk=original.pk)
        self.assertEqual(
            reminder.scheduled_for,
            appointment.appointment_at - timedelta(hours=24),
        )
        self.assertIsNone(reminder.read_at)

    def test_reminders_are_only_visible_to_the_assigned_recipient(self):
        appointment = self.create_appointment()
        reminder = AppointmentNotification.objects.create(
            appointment=appointment,
            recipient=self.clinician.account,
            notification_type="appointment_reminder",
            scheduled_for=timezone.now(),
        )
        self.login_as(self.clinician)
        response = self.client.get(reverse("clinic_appointments:appointment_reminders"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, appointment.appointment_identifier)

        self.login_as(self.receptionist)
        response = self.client.get(reverse("clinic_appointments:appointment_reminders"))
        self.assertEqual(response.status_code, 403)

    def test_reminder_can_be_marked_read_and_unauthorized_updates_are_rejected(self):
        appointment = self.create_appointment()
        reminder = AppointmentNotification.objects.create(
            appointment=appointment,
            recipient=self.clinician.account,
            notification_type="appointment_reminder",
            scheduled_for=timezone.now(),
        )

        self.login_as(self.clinician)
        response = self.client.post(
            reverse(
                "clinic_appointments:appointment_reminder_mark_read",
                args=[reminder.pk],
            )
        )
        self.assertEqual(response.status_code, 302)
        reminder.refresh_from_db()
        self.assertIsNotNone(reminder.read_at)

    def test_another_clinician_cannot_mark_recipient_reminder_as_read(self):
        appointment = self.create_appointment()
        reminder = AppointmentNotification.objects.create(
            appointment=appointment,
            recipient=self.clinician.account,
            notification_type="appointment_reminder",
            scheduled_for=timezone.now(),
        )

        self.login_as(self.other_clinician)
        response = self.client.post(
            reverse(
                "clinic_appointments:appointment_reminder_mark_read",
                args=[reminder.pk],
            )
        )

        self.assertEqual(response.status_code, 404)
        reminder.refresh_from_db()
        self.assertIsNone(reminder.read_at)

        self.login_as(self.receptionist)
        response = self.client.post(
            reverse(
                "clinic_appointments:appointment_reminder_mark_read",
                args=[reminder.pk],
            )
        )
        self.assertEqual(response.status_code, 403)

    def test_http_requests_with_missing_reminder_are_rejected(self):
        self.login_as(self.clinician)
        response = self.client.post(
            reverse("clinic_appointments:appointment_reminder_mark_read", args=[99999])
        )
        self.assertEqual(response.status_code, 404)

    def test_marking_reminder_read_requires_post_and_csrf(self):
        appointment = self.create_appointment()
        reminder = AppointmentNotification.objects.create(
            appointment=appointment,
            recipient=self.clinician.account,
            notification_type="appointment_reminder",
            scheduled_for=timezone.now(),
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.clinician.account)
        list_url = reverse("clinic_appointments:appointment_reminders")
        detail_response = client.get(list_url)
        csrf_token = detail_response.cookies["csrftoken"].value
        mark_read_url = reverse(
            "clinic_appointments:appointment_reminder_mark_read",
            args=[reminder.pk],
        )

        self.assertEqual(client.get(mark_read_url).status_code, 405)
        self.assertEqual(client.post(mark_read_url).status_code, 403)
        reminder.refresh_from_db()
        self.assertIsNone(reminder.read_at)

        response = client.post(
            mark_read_url,
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 302)
        reminder.refresh_from_db()
        self.assertIsNotNone(reminder.read_at)
