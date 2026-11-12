from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.test import TestCase
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from clinic.models import (
    Appointment,
    AuditEvent,
    Department,
    NursingObservation,
    Patient,
    StaffProfile,
)

User = get_user_model()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class NursingWorkflowTests(TestCase):
    def setUp(self):
        department = Department.objects.create(name="General Practice")
        self.admin = self.create_staff("nursing-admin", StaffProfile.Role.ADMINISTRATOR)
        self.receptionist = self.create_staff(
            "nursing-reception",
            StaffProfile.Role.RECEPTIONIST,
        )
        self.clinician = self.create_staff(
            "nursing-doctor",
            StaffProfile.Role.CLINICIAN,
        )
        self.nurse = self.create_staff("nursing-user", StaffProfile.Role.NURSE)
        for profile in (self.admin, self.receptionist, self.clinician, self.nurse):
            profile.departments.add(department)
        self.patient = Patient.objects.create(
            full_name="Fictional Nursing Patient",
            gender=Patient.Gender.PREFER_NOT_TO_SAY,
        )
        start = timezone.now() + timedelta(days=1)
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            appointment_at=start,
            ends_at=start + timedelta(minutes=30),
            status=Appointment.Status.CONFIRMED,
            reason_for_visit="Private appointment detail",
        )

    def create_staff(self, username, role):
        account = User.objects.create_user(
            username=username,
            email=f"{username}@example.test",
            password="Valid-Test-Password-927!",
        )
        return StaffProfile.objects.create(account=account, role=role)

    def login_as(self, profile):
        self.client.force_login(profile.account)

    def observation_url(self, appointment=None):
        return reverse(
            "clinic_nursing:observation_create",
            args=[(appointment or self.appointment).pk],
        )

    def test_nurse_dashboard_has_search_and_real_upcoming_appointments(self):
        self.login_as(self.nurse)

        response = self.client.get(reverse("clinic_auth:staff_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h1>Nurse dashboard</h1>", html=True)
        self.assertContains(response, "Find a patient")
        self.assertContains(response, self.patient.patient_identifier)
        self.assertContains(response, reverse("clinic_appointments:appointment_list"))
        self.assertNotContains(response, "Registered patients")
        self.assertNotContains(response, "Staff directory")
        self.assertNotContains(response, "Appointment report")
        self.assertEqual(response.context["today_appointment_count"], None)

    def test_nurse_can_search_and_view_active_demographics_without_editing(self):
        archived = Patient.objects.create(
            full_name="Archived Fictional Patient",
            is_archived=True,
        )
        self.login_as(self.nurse)

        search_response = self.client.get(
            reverse("clinic_patients:patient_list"),
            {"query": self.patient.patient_identifier},
        )
        profile_response = self.client.get(
            reverse(
                "clinic_patients:patient_profile",
                args=[self.patient.patient_identifier],
            )
        )

        self.assertEqual(search_response.status_code, 200)
        self.assertContains(search_response, self.patient.patient_identifier)
        self.assertNotContains(search_response, archived.patient_identifier)
        self.assertNotContains(search_response, "555-")
        self.assertNotContains(search_response, "Register patient")
        self.assertEqual(profile_response.status_code, 200)
        self.assertContains(profile_response, self.patient.full_name)
        self.assertNotContains(profile_response, "Edit demographics")
        self.assertNotContains(profile_response, "Emergency contact")
        self.assertNotContains(profile_response, "Address")
        self.assertEqual(
            self.client.get(
                reverse(
                    "clinic_patients:patient_profile",
                    args=[archived.patient_identifier],
                )
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("clinic_patients:patient_list"),
                {"status": "all"},
            ).status_code,
            400,
        )

    def test_nurse_can_view_full_schedule_but_cannot_manage_appointments(self):
        self.login_as(self.nurse)
        list_response = self.client.get(
            reverse("clinic_appointments:appointment_list")
        )
        detail_response = self.client.get(
            reverse(
                "clinic_appointments:appointment_detail",
                args=[self.appointment.pk],
            )
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, self.patient.patient_identifier)
        self.assertNotContains(list_response, "Schedule appointment")
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, self.patient.patient_identifier)
        self.assertNotContains(detail_response, "Private appointment detail")
        self.assertContains(detail_response, "Record observation")
        for url in (
            reverse("clinic_appointments:appointment_create"),
            reverse(
                "clinic_appointments:appointment_edit",
                args=[self.appointment.pk],
            ),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(
                reverse(
                    "clinic_appointments:appointment_cancel",
                    args=[self.appointment.pk],
                )
            ).status_code,
            403,
        )

    def test_nurse_appointment_mutation_posts_require_csrf_and_remain_forbidden(self):
        self.login_as(self.nurse)
        detail_url = reverse(
            "clinic_appointments:appointment_detail",
            args=[self.appointment.pk],
        )

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.nurse.account)
        detail_response = csrf_client.get(detail_url)
        csrf_token = detail_response.cookies["csrftoken"].value

        before = {
            "status": self.appointment.status,
            "appointment_at": self.appointment.appointment_at,
            "ends_at": self.appointment.ends_at,
            "patient_id": self.appointment.patient_id,
            "clinician_id": self.appointment.clinician_id,
            "reason_for_visit": self.appointment.reason_for_visit,
            "cancellation_reason": self.appointment.cancellation_reason,
        }
        mutation_actions = (
            "appointment.created",
            "appointment.updated",
            "appointment.rescheduled",
            "appointment.cancelled",
        )
        before_events = set(
            AuditEvent.objects.filter(action__in=mutation_actions).values_list(
                "pk",
                flat=True,
            )
        )

        changed_start = self.appointment.appointment_at + timedelta(days=7)
        edit_url = reverse(
            "clinic_appointments:appointment_edit",
            args=[self.appointment.pk],
        )
        edit_data = {
            "patient": str(self.appointment.patient_id),
            "clinician": str(self.appointment.clinician_id),
            "reason_for_visit": "Unauthorized Nurse edit attempt",
            "appointment_date": changed_start.date().isoformat(),
            "appointment_time": changed_start.time().strftime("%H:%M"),
        }

        missing_edit_token = csrf_client.post(edit_url, edit_data)
        self.assertEqual(missing_edit_token.status_code, 403)

        valid_edit_token = csrf_client.post(
            edit_url,
            edit_data,
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(valid_edit_token.status_code, 403)

        cancel_url = reverse(
            "clinic_appointments:appointment_cancel",
            args=[self.appointment.pk],
        )
        missing_cancel_token = csrf_client.post(
            cancel_url,
            {"cancellation_reason": "Unauthorized Nurse cancellation"},
        )
        self.assertEqual(missing_cancel_token.status_code, 403)

        valid_cancel_token = csrf_client.post(
            cancel_url,
            {"cancellation_reason": "Unauthorized Nurse cancellation"},
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(valid_cancel_token.status_code, 403)

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, before["status"])
        self.assertEqual(self.appointment.appointment_at, before["appointment_at"])
        self.assertEqual(self.appointment.ends_at, before["ends_at"])
        self.assertEqual(self.appointment.patient_id, before["patient_id"])
        self.assertEqual(self.appointment.clinician_id, before["clinician_id"])
        self.assertEqual(
            self.appointment.reason_for_visit,
            before["reason_for_visit"],
        )
        self.assertEqual(
            self.appointment.cancellation_reason,
            before["cancellation_reason"],
        )
        self.assertEqual(
            set(
                AuditEvent.objects.filter(
                    action__in=mutation_actions
                ).values_list("pk", flat=True)
            ),
            before_events,
        )

    def test_valid_observation_uses_authenticated_nurse_and_audits_without_values(self):
        self.login_as(self.nurse)
        response = self.client.post(
            self.observation_url(),
            {
                "body_temperature_celsius": "36.7",
                "pulse_rate_bpm": "72",
                "systolic_blood_pressure_mm_hg": "118",
                "diastolic_blood_pressure_mm_hg": "76",
                "respiratory_rate_bpm": "16",
                "weight_kg": "64.25",
                "notes": "Fictional observation note.",
                "recorded_by": str(self.admin.pk),
            },
        )

        observation = NursingObservation.objects.get()
        event = AuditEvent.objects.get(action="nursing_observation.created")
        self.assertRedirects(
            response,
            reverse(
                "clinic_appointments:appointment_detail",
                args=[self.appointment.pk],
            ),
        )
        self.assertEqual(observation.appointment, self.appointment)
        self.assertEqual(observation.recorded_by, self.nurse)
        self.assertEqual(event.actor, self.nurse.account)
        self.assertEqual(event.content_object, observation)
        self.assertEqual(
            event.metadata,
            {
                "patient_identifier": self.patient.patient_identifier,
                "record_id": observation.pk,
            },
        )
        self.assertNotIn("36.7", str(event.metadata))
        self.assertNotIn("Fictional observation note", str(event.metadata))

        detail_response = self.client.get(
            reverse(
                "clinic_appointments:appointment_detail",
                args=[self.appointment.pk],
            )
        )
        self.assertContains(detail_response, "36.7")
        self.assertContains(detail_response, "Fictional observation note.")
        self.assertContains(detail_response, "nursing-user")

    def test_invalid_or_incomplete_observations_are_rejected(self):
        self.login_as(self.nurse)
        url = self.observation_url()

        no_measurement = self.client.post(url, {"notes": "Note without a measurement"})
        partial_pressure = self.client.post(
            url,
            {"systolic_blood_pressure_mm_hg": "120"},
        )
        negative_value = self.client.post(
            url,
            {"pulse_rate_bpm": "-1"},
        )

        self.assertEqual(no_measurement.status_code, 200)
        self.assertEqual(partial_pressure.status_code, 200)
        self.assertEqual(negative_value.status_code, 200)
        self.assertFalse(NursingObservation.objects.exists())
        self.assertFalse(
            AuditEvent.objects.filter(action="nursing_observation.created").exists()
        )

    def test_observation_model_rejects_non_nurse_authorship(self):
        observation = NursingObservation(
            appointment=self.appointment,
            recorded_by=self.clinician,
            pulse_rate_bpm=72,
        )

        with self.assertRaises(ValidationError):
            observation.full_clean()

    def test_observation_write_and_audit_roll_back_together_on_storage_failure(self):
        self.login_as(self.nurse)

        with self.assertLogs("clinic.nursing_views", level="ERROR") as log_output:
            with patch(
                "clinic.nursing_views.record_audit_event",
                side_effect=DatabaseError("storage unavailable"),
            ):
                response = self.client.post(
                    self.observation_url(),
                    {"pulse_rate_bpm": "72"},
                )

        self.assertEqual(response.status_code, 503)
        self.assertFalse(NursingObservation.objects.exists())
        self.assertFalse(
            AuditEvent.objects.filter(action="nursing_observation.created").exists()
        )
        self.assertNotIn(
            "storage unavailable",
            "\n".join(log_output.output),
        )

    def test_observation_post_requires_csrf_and_authentication(self):
        url = self.observation_url()
        csrf_client = Client(enforce_csrf_checks=True)
        self.assertEqual(
            csrf_client.post(url, {"pulse_rate_bpm": "72"}).status_code,
            403,
        )

        csrf_client.force_login(self.nurse.account)
        response = csrf_client.get(url)
        csrf_token = response.cookies["csrftoken"].value
        self.assertEqual(csrf_client.post(url, {"pulse_rate_bpm": "72"}).status_code, 403)
        self.assertFalse(NursingObservation.objects.exists())

        accepted = csrf_client.post(
            url,
            {"pulse_rate_bpm": "72"},
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(NursingObservation.objects.count(), 1)

    def test_only_nurses_can_record_observations_and_unrelated_actors_retain_roles(self):
        url = self.observation_url()
        for profile in (self.admin, self.receptionist, self.clinician):
            with self.subTest(role=profile.role):
                self.login_as(profile)
                self.assertEqual(self.client.get(url).status_code, 403)
        self.login_as(self.nurse)
        self.assertEqual(
            self.client.get(
                self.observation_url(
                    Appointment.objects.create(
                        patient=Patient.objects.create(
                            full_name="Unrelated Fictional Patient"
                        ),
                        clinician=self.clinician,
                        appointment_at=timezone.now() + timedelta(days=2),
                        ends_at=timezone.now() + timedelta(days=2, minutes=30),
                    )
                )
            ).status_code,
            200,
        )
