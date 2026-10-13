from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clinic.models import Appointment, Department, Patient, StaffProfile

User = get_user_model()


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class PatientManagementTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="General Practice")
        self.profiles = {
            StaffProfile.Role.ADMINISTRATOR: self.create_staff(
                "admin", StaffProfile.Role.ADMINISTRATOR
            ),
            StaffProfile.Role.RECEPTIONIST: self.create_staff(
                "reception", StaffProfile.Role.RECEPTIONIST
            ),
            StaffProfile.Role.CLINICIAN: self.create_staff(
                "clinician", StaffProfile.Role.CLINICIAN
            ),
            StaffProfile.Role.NURSE: self.create_staff(
                "nurse", StaffProfile.Role.NURSE
            ),
        }
        self.patient = Patient.objects.create(
            full_name="Fictional Patient",
            gender=Patient.Gender.FEMALE,
            phone_number="555-0101",
            address="12 Example Street",
            emergency_contact_name="Fictional Contact",
            emergency_contact_phone="555-0102",
        )

    def create_staff(self, username, role):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.test",
            password="Fictional-Password-924!",
        )
        return StaffProfile.objects.create(account=user, role=role)

    def login_as(self, role):
        self.client.force_login(self.profiles[role].account)

    def registration_data(self, **overrides):
        data = {
            "full_name": "Fictional New Patient",
            "gender": Patient.Gender.FEMALE,
            "date_of_birth": "1985-03-14",
            "phone_number": "555-0110",
            "address": "34 Example Avenue",
            "emergency_contact_name": "Fictional Relative",
            "emergency_contact_phone": "555-0111",
        }
        data.update(overrides)
        return data

    def test_receptionist_can_register_patient_and_identifier_is_generated(self):
        self.login_as(StaffProfile.Role.RECEPTIONIST)

        response = self.client.post(
            reverse("clinic_patients:patient_create"),
            self.registration_data(),
        )

        created = Patient.objects.get(full_name="Fictional New Patient")
        self.assertRedirects(
            response,
            reverse(
                "clinic_patients:patient_profile",
                args=[created.patient_identifier],
            ),
        )
        self.assertRegex(created.patient_identifier, r"^PT-[A-F0-9]{32}$")
        self.assertEqual(created.date_of_birth, date(1985, 3, 14))
        self.assertFalse(created.is_archived)

    def test_required_full_name_is_validated(self):
        self.login_as(StaffProfile.Role.RECEPTIONIST)

        response = self.client.post(
            reverse("clinic_patients:patient_create"),
            self.registration_data(full_name="   "),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Patient.objects.filter(full_name="").exists())

    def test_future_date_of_birth_is_rejected(self):
        self.login_as(StaffProfile.Role.RECEPTIONIST)
        future_date = (timezone.localdate() + timedelta(days=1)).isoformat()

        response = self.client.post(
            reverse("clinic_patients:patient_create"),
            self.registration_data(date_of_birth=future_date),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "date_of_birth",
            response.context["form"].errors,
        )
        self.assertFalse(
            Patient.objects.filter(full_name="Fictional New Patient").exists()
        )

    def test_identifier_collision_retries_without_duplicating_patient(self):
        self.login_as(StaffProfile.Role.RECEPTIONIST)
        with patch(
            "clinic.patient_forms.generate_patient_identifier",
            side_effect=[
                self.patient.patient_identifier,
                "PT-11111111111111111111111111111111",
            ],
        ):
            response = self.client.post(
                reverse("clinic_patients:patient_create"),
                self.registration_data(),
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Patient.objects.count(), 2)
        self.assertTrue(
            Patient.objects.filter(
                patient_identifier="PT-11111111111111111111111111111111"
            ).exists()
        )

    def test_identifier_generation_exhaustion_returns_safe_validation_response(self):
        self.login_as(StaffProfile.Role.RECEPTIONIST)
        with patch(
            "clinic.patient_forms.generate_patient_identifier",
            return_value=self.patient.patient_identifier,
        ):
            response = self.client.post(
                reverse("clinic_patients:patient_create"),
                self.registration_data(),
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.status_code, 503)
        self.assertIn(
            "A unique patient identifier could not be generated",
            response.content.decode(),
        )
        self.assertNotIn("sqlite", response.content.decode().lower())
        self.assertEqual(Patient.objects.count(), 1)

    def test_patient_list_and_profile_render_demographic_data_only(self):
        self.login_as(StaffProfile.Role.RECEPTIONIST)

        list_response = self.client.get(reverse("clinic_patients:patient_list"))
        profile_response = self.client.get(
            reverse(
                "clinic_patients:patient_profile",
                args=[self.patient.patient_identifier],
            )
        )

        self.assertContains(list_response, self.patient.patient_identifier)
        self.assertContains(list_response, self.patient.full_name)
        self.assertContains(profile_response, self.patient.address)
        self.assertContains(profile_response, self.patient.emergency_contact_name)
        self.assertNotContains(profile_response, "Diagnosis")
        self.assertNotContains(profile_response, "Medical history")

    def test_receptionist_can_edit_patient_demographics(self):
        self.login_as(StaffProfile.Role.RECEPTIONIST)
        patient_identifier = self.patient.patient_identifier

        response = self.client.post(
            reverse(
                "clinic_patients:patient_edit",
                args=[self.patient.patient_identifier],
            ),
            self.registration_data(
                full_name="Fictional Updated Patient",
                date_of_birth="1980-06-01",
            ),
        )

        self.assertRedirects(
            response,
            reverse(
                "clinic_patients:patient_profile",
                args=[patient_identifier],
            ),
        )
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.full_name, "Fictional Updated Patient")
        self.assertEqual(self.patient.date_of_birth, date(1980, 6, 1))
        self.assertEqual(self.patient.patient_identifier, patient_identifier)

    def test_search_matches_identifier_name_and_phone(self):
        self.login_as(StaffProfile.Role.RECEPTIONIST)

        for query in (
            self.patient.patient_identifier[-6:],
            "Fictional Patient",
            "555-0101",
        ):
            with self.subTest(query=query):
                response = self.client.get(
                    reverse("clinic_patients:patient_list"),
                    {"query": query},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    list(response.context["patients"].object_list),
                    [self.patient],
                )

    def test_invalid_search_input_returns_validation_feedback(self):
        self.login_as(StaffProfile.Role.RECEPTIONIST)

        response = self.client.get(
            reverse("clinic_patients:patient_list"),
            {"query": "x" * 101},
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.context["search_form"].errors)

    def test_patient_list_paginates(self):
        self.login_as(StaffProfile.Role.RECEPTIONIST)
        Patient.objects.bulk_create(
            [
                Patient(full_name=f"Fictional Patient {index:02}")
                for index in range(30)
            ]
        )

        response = self.client.get(reverse("clinic_patients:patient_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["patients"].object_list), 25)
        self.assertEqual(response.context["patients"].paginator.num_pages, 2)

    def test_archived_patients_are_filtered_and_can_be_restored(self):
        self.login_as(StaffProfile.Role.ADMINISTRATOR)
        appointment = Appointment.objects.create(
            patient=self.patient,
            clinician=self.profiles[StaffProfile.Role.CLINICIAN],
            appointment_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, minutes=30),
        )
        profile_url = reverse(
            "clinic_patients:patient_profile",
            args=[self.patient.patient_identifier],
        )

        archive_response = self.client.post(
            reverse(
                "clinic_patients:patient_archive",
                args=[self.patient.patient_identifier],
            )
        )
        self.assertRedirects(archive_response, profile_url)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.is_archived)
        self.assertTrue(Appointment.objects.filter(pk=appointment.pk).exists())

        active_list = self.client.get(reverse("clinic_patients:patient_list"))
        archived_list = self.client.get(
            reverse("clinic_patients:patient_list"),
            {"status": "archived"},
        )
        self.assertNotContains(active_list, self.patient.patient_identifier)
        self.assertContains(archived_list, self.patient.patient_identifier)

        restore_response = self.client.post(
            reverse(
                "clinic_patients:patient_restore",
                args=[self.patient.patient_identifier],
            )
        )
        self.assertRedirects(restore_response, profile_url)
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_archived)
        self.assertTrue(Appointment.objects.filter(pk=appointment.pk).exists())

    def test_archive_and_restore_are_post_only(self):
        self.login_as(StaffProfile.Role.ADMINISTRATOR)

        archive_response = self.client.get(
            reverse(
                "clinic_patients:patient_archive",
                args=[self.patient.patient_identifier],
            )
        )
        restore_response = self.client.get(
            reverse(
                "clinic_patients:patient_restore",
                args=[self.patient.patient_identifier],
            )
        )

        self.assertEqual(archive_response.status_code, 405)
        self.assertEqual(restore_response.status_code, 405)
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_archived)

    def test_csrf_is_required_for_archive_and_valid_token_allows_post(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(
            self.profiles[StaffProfile.Role.ADMINISTRATOR].account
        )
        profile_url = reverse(
            "clinic_patients:patient_profile",
            args=[self.patient.patient_identifier],
        )
        csrf_client.get(profile_url)
        token = csrf_client.cookies["csrftoken"].value
        archive_url = reverse(
            "clinic_patients:patient_archive",
            args=[self.patient.patient_identifier],
        )

        rejected = csrf_client.post(archive_url)
        self.assertEqual(rejected.status_code, 403)
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_archived)

        accepted = csrf_client.post(
            archive_url,
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(accepted.status_code, 302)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.is_archived)

    def test_only_administrator_can_archive_or_restore(self):
        self.login_as(StaffProfile.Role.RECEPTIONIST)

        archive_response = self.client.post(
            reverse(
                "clinic_patients:patient_archive",
                args=[self.patient.patient_identifier],
            )
        )
        restore_response = self.client.post(
            reverse(
                "clinic_patients:patient_restore",
                args=[self.patient.patient_identifier],
            )
        )

        self.assertEqual(archive_response.status_code, 403)
        self.assertEqual(restore_response.status_code, 403)
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_archived)

    def test_clinician_and_nurse_cannot_access_patient_management(self):
        urls = (
            reverse("clinic_patients:patient_list"),
            reverse("clinic_patients:patient_create"),
            reverse(
                "clinic_patients:patient_profile",
                args=[self.patient.patient_identifier],
            ),
            reverse(
                "clinic_patients:patient_edit",
                args=[self.patient.patient_identifier],
            ),
        )
        for role in (StaffProfile.Role.CLINICIAN, StaffProfile.Role.NURSE):
            self.login_as(role)
            for url in urls:
                with self.subTest(role=role, url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 403)

    def test_clinician_and_nurse_cannot_create_or_edit_patients_by_post(self):
        create_url = reverse("clinic_patients:patient_create")
        edit_url = reverse(
            "clinic_patients:patient_edit",
            args=[self.patient.patient_identifier],
        )
        for role in (StaffProfile.Role.CLINICIAN, StaffProfile.Role.NURSE):
            self.login_as(role)
            for url in (create_url, edit_url):
                with self.subTest(role=role, url=url):
                    response = self.client.post(
                        url,
                        self.registration_data(
                            full_name="Unauthorized Fictional Change"
                        ),
                    )
                    self.assertEqual(response.status_code, 403)

        self.patient.refresh_from_db()
        self.assertEqual(self.patient.full_name, "Fictional Patient")
        self.assertFalse(
            Patient.objects.filter(
                full_name="Unauthorized Fictional Change"
            ).exists()
        )

    def test_unauthenticated_users_cannot_access_patient_records(self):
        patient_identifier = self.patient.patient_identifier
        protected_requests = (
            ("get", reverse("clinic_patients:patient_list")),
            ("get", reverse("clinic_patients:patient_create")),
            (
                "get",
                reverse(
                    "clinic_patients:patient_profile",
                    args=[patient_identifier],
                ),
            ),
            (
                "get",
                reverse(
                    "clinic_patients:patient_edit",
                    args=[patient_identifier],
                ),
            ),
            (
                "post",
                reverse(
                    "clinic_patients:patient_archive",
                    args=[patient_identifier],
                ),
            ),
            (
                "post",
                reverse(
                    "clinic_patients:patient_restore",
                    args=[patient_identifier],
                ),
            ),
        )

        for method, url in protected_requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("clinic_auth:login"), response.url)

    def test_unknown_patient_identifier_returns_404_without_database_details(self):
        self.login_as(StaffProfile.Role.RECEPTIONIST)

        response = self.client.get(
            reverse(
                "clinic_patients:patient_profile",
                args=["PT-NOT-A-REAL-IDENTIFIER"],
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Traceback", status_code=404)

    def test_admin_and_receptionist_can_view_patient_list_and_profile(self):
        for role in (
            StaffProfile.Role.ADMINISTRATOR,
            StaffProfile.Role.RECEPTIONIST,
        ):
            with self.subTest(role=role):
                self.login_as(role)
                self.assertEqual(
                    self.client.get(
                        reverse("clinic_patients:patient_list")
                    ).status_code,
                    200,
                )
                self.assertEqual(
                    self.client.get(
                        reverse(
                            "clinic_patients:patient_profile",
                            args=[self.patient.patient_identifier],
                        )
                    ).status_code,
                    200,
                )
