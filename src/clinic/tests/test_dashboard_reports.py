from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import constants as message_constants
from django.contrib.messages.storage.base import Message
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clinic.models import Appointment, Consultation, Department, Patient, StaffProfile

User = get_user_model()


class DashboardAndAppointmentReportTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="General Practice")
        self.admin = self.create_staff("dashboard-admin", StaffProfile.Role.ADMINISTRATOR)
        self.receptionist = self.create_staff(
            "dashboard-reception",
            StaffProfile.Role.RECEPTIONIST,
        )
        self.clinician = self.create_staff(
            "dashboard-doctor",
            StaffProfile.Role.CLINICIAN,
        )
        self.other_clinician = self.create_staff(
            "dashboard-other-doctor",
            StaffProfile.Role.CLINICIAN,
        )
        self.nurse = self.create_staff("dashboard-nurse", StaffProfile.Role.NURSE)
        self.patient = Patient.objects.create(full_name="Dashboard Test Patient")
        self.other_patient = Patient.objects.create(full_name="Other Test Patient")

    def create_staff(self, username, role):
        account = User.objects.create_user(
            username=username,
            email=f"{username}@example.test",
        )
        profile = StaffProfile.objects.create(account=account, role=role)
        profile.departments.add(self.department)
        return profile

    def create_appointment(
        self,
        appointment_date,
        *,
        appointment_time=time(12),
        status=Appointment.Status.SCHEDULED,
        clinician=None,
        patient=None,
        reason="Fictional appointment reason",
    ):
        starts_at = timezone.make_aware(
            datetime.combine(appointment_date, appointment_time),
            timezone.get_current_timezone(),
        )
        return Appointment.objects.create(
            patient=patient or self.patient,
            clinician=clinician or self.clinician,
            appointment_at=starts_at,
            ends_at=starts_at + timedelta(minutes=30),
            reason_for_visit=reason,
            status=status,
        )

    def login_as(self, profile):
        self.client.force_login(profile.account)

    def test_dashboard_metrics_count_today_upcoming_and_all_statuses(self):
        today = timezone.localdate()
        for status in Appointment.Status.values:
            self.create_appointment(
                today,
                appointment_time=time(0),
                status=status,
            )
        self.create_appointment(
            today - timedelta(days=1),
            appointment_time=time(8),
            status=Appointment.Status.SCHEDULED,
        )
        self.create_appointment(
            today + timedelta(days=1),
            appointment_time=time(8),
            status=Appointment.Status.SCHEDULED,
        )
        self.create_appointment(
            today + timedelta(days=1),
            appointment_time=time(9),
            status=Appointment.Status.CONFIRMED,
        )
        self.login_as(self.admin)

        response = self.client.get(reverse("clinic_auth:staff_home"))

        self.assertEqual(response.context["today_appointment_count"], 6)
        self.assertEqual(response.context["upcoming_appointment_count"], 2)
        self.assertEqual(
            {row["value"]: row["total"] for row in response.context["appointment_status_counts"]},
            {
                Appointment.Status.SCHEDULED: 3,
                Appointment.Status.CONFIRMED: 2,
                Appointment.Status.ATTENDED: 1,
                Appointment.Status.COMPLETED: 1,
                Appointment.Status.CANCELLED: 1,
                Appointment.Status.MISSED: 1,
            },
        )
        self.assertEqual(response.context["registered_patient_count"], 2)

    def test_dashboard_metrics_handle_no_appointments(self):
        self.login_as(self.receptionist)

        response = self.client.get(reverse("clinic_auth:staff_home"))

        self.assertEqual(response.context["today_appointment_count"], 0)
        self.assertEqual(response.context["upcoming_appointment_count"], 0)
        self.assertTrue(
            all(
                row["total"] == 0
                for row in response.context["appointment_status_counts"]
            )
        )
        self.assertEqual(response.context["registered_patient_count"], 2)

    def test_receptionist_dashboard_has_registration_and_scheduling_actions(self):
        self.login_as(self.receptionist)

        response = self.client.get(reverse("clinic_auth:staff_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("clinic_patients:patient_create"),
        )
        self.assertContains(
            response,
            reverse("clinic_appointments:appointment_create"),
        )
        self.assertContains(response, "Register patient")
        self.assertContains(response, "Schedule appointment")

    def test_message_templates_support_success_error_warning_and_info_styles(self):
        request = RequestFactory().get(reverse("clinic_auth:staff_home"))
        request.user = AnonymousUser()
        rendered = render_to_string(
            "clinic/auth/base.html",
            {
                "messages": [
                    Message(message_constants.SUCCESS, "Success message"),
                    Message(message_constants.ERROR, "Error message"),
                    Message(message_constants.WARNING, "Warning message"),
                    Message(message_constants.INFO, "Info message"),
                ]
            },
            request=request,
        )

        for tag in ("success", "error", "warning", "info"):
            self.assertIn(f'message--{tag}', rendered)

    @override_settings(DEBUG=False)
    def test_branded_404_for_authenticated_and_unauthenticated_users(self):
        missing_url = "/missing-m14-page/"

        anonymous_response = self.client.get(missing_url)
        self.assertEqual(anonymous_response.status_code, 404)
        self.assertContains(
            anonymous_response,
            "Page or record not found",
            status_code=404,
        )
        self.assertContains(
            anonymous_response,
            reverse("clinic_auth:login"),
            status_code=404,
        )

        self.login_as(self.receptionist)
        authenticated_response = self.client.get(missing_url)
        self.assertEqual(authenticated_response.status_code, 404)
        self.assertContains(
            authenticated_response,
            "Page or record not found",
            status_code=404,
        )
        self.assertContains(
            authenticated_response,
            reverse("clinic_auth:staff_home"),
            status_code=404,
        )

    def test_dashboard_uses_active_local_timezone_for_calendar_day(self):
        with timezone.override("Pacific/Kiritimati"):
            today = timezone.localdate()
            self.create_appointment(
                today,
                appointment_time=time(0, 15),
            )
            self.create_appointment(
                today - timedelta(days=1),
                appointment_time=time(23, 45),
            )
            self.login_as(self.admin)

            response = self.client.get(reverse("clinic_auth:staff_home"))

        self.assertEqual(response.context["today_appointment_count"], 1)

    def test_clinician_dashboard_metrics_are_limited_to_assigned_appointments(self):
        today = timezone.localdate()
        self.create_appointment(today, clinician=self.clinician)
        self.create_appointment(today, clinician=self.other_clinician)
        self.login_as(self.clinician)

        deterministic_now = timezone.make_aware(
            datetime.combine(today, time(11, 59)),
            timezone.get_current_timezone(),
        )
        with patch("clinic.auth_views.timezone.now", return_value=deterministic_now):
            response = self.client.get(reverse("clinic_auth:staff_home"))

        self.assertEqual(response.context["today_appointment_count"], 1)
        self.assertEqual(response.context["upcoming_appointment_count"], 1)
        self.assertEqual(response.context["registered_patient_count"], None)
        self.assertNotContains(response, "Registered patients")

    def test_nurse_dashboard_does_not_show_appointment_or_patient_totals(self):
        self.login_as(self.nurse)

        response = self.client.get(reverse("clinic_auth:staff_home"))

        self.assertIsNone(response.context["today_appointment_count"])
        self.assertIsNone(response.context["registered_patient_count"])
        self.assertNotContains(response, "Appointments today")
        self.assertNotContains(response, "Registered patients")

    def test_report_includes_both_local_date_boundaries_and_all_statuses(self):
        start_date = timezone.localdate() + timedelta(days=2)
        end_date = start_date + timedelta(days=2)
        for index, status in enumerate(Appointment.Status.values):
            self.create_appointment(
                start_date if index % 2 == 0 else end_date,
                appointment_time=time(0, 1) if index % 2 == 0 else time(23, 59),
                status=status,
            )
        appointment = Appointment.objects.filter(
            appointment_at__date=start_date,
            status=Appointment.Status.SCHEDULED,
        ).first()
        Consultation.objects.create(
            patient=appointment.patient,
            appointment=appointment,
            clinician=appointment.clinician,
            diagnosis="Private diagnosis must not appear in operational reports",
        )
        self.create_appointment(
            start_date - timedelta(days=1),
            status=Appointment.Status.SCHEDULED,
        )
        self.create_appointment(
            end_date + timedelta(days=1),
            status=Appointment.Status.SCHEDULED,
        )
        self.login_as(self.admin)

        response = self.client.get(
            reverse("clinic_appointments:appointment_report"),
            {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_appointments"], 6)
        self.assertEqual(
            {row["value"]: row["total"] for row in response.context["status_counts"]},
            {status: 1 for status in Appointment.Status.values},
        )
        self.assertNotContains(
            response,
            "Private diagnosis must not appear in operational reports",
        )

    def test_report_supports_start_only_and_end_only_filters(self):
        today = timezone.localdate() + timedelta(days=2)
        self.create_appointment(today - timedelta(days=1))
        self.create_appointment(today)
        self.create_appointment(today + timedelta(days=1))
        self.create_appointment(today + timedelta(days=2))
        self.login_as(self.admin)
        report_url = reverse("clinic_appointments:appointment_report")

        start_only = self.client.get(
            report_url,
            {"start_date": today.isoformat()},
        )
        end_only = self.client.get(
            report_url,
            {"end_date": (today + timedelta(days=1)).isoformat()},
        )

        self.assertEqual(start_only.context["total_appointments"], 3)
        self.assertEqual(end_only.context["total_appointments"], 3)

    def test_report_rejects_malformed_dates_and_reversed_ranges(self):
        self.login_as(self.admin)
        report_url = reverse("clinic_appointments:appointment_report")

        malformed = self.client.get(report_url, {"start_date": "not-a-date"})
        reversed_range = self.client.get(
            report_url,
            {
                "start_date": "2030-02-02",
                "end_date": "2030-02-01",
            },
        )

        self.assertEqual(malformed.status_code, 400)
        self.assertContains(malformed, "Enter a valid date", status_code=400)
        self.assertNotContains(malformed, "Total appointments:", status_code=400)
        self.assertEqual(reversed_range.status_code, 400)
        self.assertContains(
            reversed_range,
            "The start date must be on or before the end date.",
            status_code=400,
        )
        self.assertNotContains(
            reversed_range,
            "Total appointments:",
            status_code=400,
        )

    def test_report_rejects_impossible_calendar_date_before_queryset_or_totals(self):
        self.login_as(self.admin)

        with patch("clinic.appointment_views.appointment_queryset_for") as queryset:
            response = self.client.get(
                reverse("clinic_appointments:appointment_report"),
                {"start_date": "2030-02-30"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Enter a valid date", status_code=400)
        self.assertNotContains(response, "Total appointments:", status_code=400)
        queryset.assert_not_called()

    def test_report_shows_empty_state_for_valid_range_with_no_appointments(self):
        self.login_as(self.admin)

        response = self.client.get(
            reverse("clinic_appointments:appointment_report"),
            {"start_date": "2099-01-01", "end_date": "2099-01-31"},
        )

        self.assertEqual(response.context["total_appointments"], 0)
        self.assertContains(response, "No appointments match the selected date range.")
        self.assertTrue(
            all(row["total"] == 0 for row in response.context["status_counts"])
        )

    def test_only_administrators_can_access_the_appointment_report(self):
        report_url = reverse("clinic_appointments:appointment_report")
        for profile in (
            self.receptionist,
            self.clinician,
            self.other_clinician,
            self.nurse,
        ):
            with self.subTest(role=profile.role):
                self.login_as(profile)
                self.assertEqual(self.client.get(report_url).status_code, 403)

        self.login_as(self.admin)
        self.assertEqual(self.client.get(report_url).status_code, 200)

    def test_reminder_navigation_and_dashboard_action_match_endpoint_roles(self):
        for profile in (
            self.admin,
            self.receptionist,
            self.clinician,
            self.nurse,
        ):
            with self.subTest(role=profile.role):
                self.login_as(profile)
                dashboard = self.client.get(reverse("clinic_auth:staff_home"))
                reminder_url = reverse("clinic_appointments:appointment_reminders")
                if profile.role == StaffProfile.Role.CLINICIAN:
                    self.assertContains(dashboard, reminder_url)
                    self.assertEqual(self.client.get(reminder_url).status_code, 200)
                else:
                    self.assertNotContains(dashboard, reminder_url)
                    self.assertEqual(self.client.get(reminder_url).status_code, 403)

    def test_change_password_is_available_in_settings_only(self):
        self.login_as(self.admin)
        dashboard = self.client.get(reverse("clinic_auth:staff_home"))
        nav = dashboard.content.decode().split(
            '<nav class="app-nav"',
            1,
        )[1].split("</nav>", 1)[0]

        self.assertNotContains(dashboard, reverse("clinic_auth:password_change"))
        self.assertNotIn(reverse("clinic_auth:password_change"), nav)
        self.assertContains(dashboard, reverse("clinic_auth:settings"))
        settings_page = self.client.get(reverse("clinic_auth:settings"))
        self.assertContains(settings_page, reverse("clinic_auth:password_change"))

    def test_report_navigation_is_administrator_only(self):
        report_url = reverse("clinic_appointments:appointment_report")
        self.login_as(self.admin)
        self.assertContains(
            self.client.get(reverse("clinic_auth:staff_home")),
            report_url,
        )

        for profile in (self.receptionist, self.clinician, self.nurse):
            with self.subTest(role=profile.role):
                self.login_as(profile)
                self.assertNotContains(
                    self.client.get(reverse("clinic_auth:staff_home")),
                    report_url,
                )
