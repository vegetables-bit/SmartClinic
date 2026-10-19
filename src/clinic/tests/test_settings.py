from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from clinic.models import Department, StaffProfile

User = get_user_model()
TEST_PASSWORD = "S3cure-Clinic-Password-927!"


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class SettingsTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="General Practice")
        self.admin = self.create_staff("settings-admin", StaffProfile.Role.ADMINISTRATOR)
        self.receptionist = self.create_staff(
            "settings-reception",
            StaffProfile.Role.RECEPTIONIST,
        )
        self.clinician = self.create_staff(
            "settings-clinician",
            StaffProfile.Role.CLINICIAN,
        )
        self.nurse = self.create_staff("settings-nurse", StaffProfile.Role.NURSE)

    def create_staff(self, username, role):
        account = User.objects.create_user(
            username=username,
            first_name="Initial",
            last_name="Staff",
            email=f"{username}@example.test",
            password=TEST_PASSWORD,
        )
        profile = StaffProfile.objects.create(
            account=account,
            role=role,
            staff_identifier=f"ST-{username}",
            phone_number="000-000-0000",
        )
        profile.departments.add(self.department)
        return profile

    def test_settings_and_profile_are_available_to_all_application_roles(self):
        for profile in (self.admin, self.receptionist, self.clinician, self.nurse):
            with self.subTest(role=profile.role):
                self.client.force_login(profile.account)
                settings_response = self.client.get(reverse("clinic_auth:settings"))
                profile_response = self.client.get(reverse("clinic_auth:my_profile"))

                self.assertEqual(settings_response.status_code, 200)
                self.assertContains(settings_response, "Settings")
                self.assertContains(settings_response, "My Profile")
                self.assertContains(settings_response, "Change Password")
                self.assertContains(settings_response, "Settings")
                self.assertEqual(profile_response.status_code, 200)
                self.assertContains(
                    profile_response,
                    f"<dd>{profile.account.username}</dd>",
                    html=True,
                )
                self.assertContains(profile_response, profile.get_role_display())
                if profile.role == StaffProfile.Role.ADMINISTRATOR:
                    self.assertContains(settings_response, "Manage Users")
                else:
                    self.assertNotContains(settings_response, "Manage Users")

    def test_settings_navigation_is_visible_in_shared_authenticated_layout(self):
        self.client.force_login(self.clinician.account)

        response = self.client.get(reverse("clinic_auth:staff_home"))

        self.assertContains(
            response,
            f'href="{reverse("clinic_auth:settings")}"',
        )
        self.assertContains(response, ">Settings</span>", html=False)
        nav = response.content.decode().split('<nav class="app-nav"', 1)[1].split(
            "</nav>",
            1,
        )[0]
        self.assertNotIn(
            reverse("clinic_auth:password_change"),
            nav,
        )

    def test_profile_update_changes_only_current_users_personal_fields(self):
        self.client.force_login(self.receptionist.account)
        response = self.client.post(
            reverse("clinic_auth:my_profile"),
            {
                "first_name": "Updated",
                "last_name": "Receptionist",
                "email": "updated-reception@example.test",
                "phone_number": "000-000-0001",
                "role": StaffProfile.Role.ADMINISTRATOR,
                "username": "promoted",
            },
        )

        self.assertRedirects(response, reverse("clinic_auth:my_profile"))
        self.receptionist.account.refresh_from_db()
        self.receptionist.refresh_from_db()
        self.assertEqual(self.receptionist.account.first_name, "Updated")
        self.assertEqual(self.receptionist.account.last_name, "Receptionist")
        self.assertEqual(
            self.receptionist.account.email,
            "updated-reception@example.test",
        )
        self.assertEqual(self.receptionist.account.username, "settings-reception")
        self.assertEqual(self.receptionist.role, StaffProfile.Role.RECEPTIONIST)
        self.assertEqual(self.receptionist.phone_number, "000-000-0001")

    def test_profile_form_rejects_duplicate_email_and_invalid_email(self):
        self.client.force_login(self.receptionist.account)

        for email in ("settings-clinician@example.test", "not-an-email"):
            with self.subTest(email=email):
                response = self.client.post(
                    reverse("clinic_auth:my_profile"),
                    {
                        "first_name": "Updated",
                        "last_name": "Receptionist",
                        "email": email,
                        "phone_number": "",
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("email", response.context["form"].errors)

        self.receptionist.account.refresh_from_db()
        self.assertEqual(
            self.receptionist.account.email,
            "settings-reception@example.test",
        )

    def test_manage_users_is_server_side_restricted_to_administrator(self):
        manage_url = reverse("clinic_auth:staff_account_list")
        for profile in (self.receptionist, self.clinician, self.nurse):
            with self.subTest(role=profile.role):
                self.client.force_login(profile.account)
                response = self.client.get(manage_url)
                self.assertEqual(response.status_code, 403)

        self.client.force_login(self.admin.account)
        self.assertEqual(self.client.get(manage_url).status_code, 200)

    def test_settings_page_uses_existing_admin_user_creation_flow(self):
        self.client.force_login(self.admin.account)
        settings_response = self.client.get(reverse("clinic_auth:settings"))
        self.assertContains(
            settings_response,
            reverse("clinic_auth:staff_account_list"),
        )

        response = self.client.post(
            reverse("clinic_auth:staff_account_create"),
            {
                "username": "settings-created-nurse",
                "first_name": "New",
                "last_name": "Nurse",
                "email": "settings-created-nurse@example.test",
                "role": StaffProfile.Role.NURSE,
                "password1": TEST_PASSWORD,
                "password2": TEST_PASSWORD,
            },
        )

        profile = StaffProfile.objects.get(
            account__username="settings-created-nurse"
        )
        self.assertRedirects(
            response,
            reverse("clinic_auth:staff_account_profile", args=[profile.pk]),
        )
        self.assertTrue(profile.account.check_password(TEST_PASSWORD))
        self.assertFalse(profile.account.is_staff)
        self.assertFalse(profile.account.is_superuser)

    def test_change_password_card_links_to_existing_secure_password_change(self):
        self.client.force_login(self.clinician.account)

        response = self.client.get(reverse("clinic_auth:settings"))

        self.assertContains(
            response,
            reverse("clinic_auth:password_change"),
        )
        settings_content = response.content.decode().split(
            '<nav class="app-nav"',
            1,
        )[1].split("</nav>", 1)[1]
        self.assertIn(
            reverse("clinic_auth:password_change"),
            settings_content,
        )
        password_form = self.client.get(reverse("clinic_auth:password_change"))
        self.assertEqual(password_form.status_code, 200)
        self.assertContains(password_form, "name=\"old_password\"")
        self.assertContains(password_form, "name=\"new_password1\"")
        self.assertContains(password_form, "name=\"new_password2\"")

    def test_password_change_verifies_current_password_and_updates_hash(self):
        self.client.force_login(self.clinician.account)
        new_password = "Different-Clinic-Password-428!"

        invalid_response = self.client.post(
            reverse("clinic_auth:password_change"),
            {
                "old_password": "incorrect-current-password",
                "new_password1": new_password,
                "new_password2": new_password,
            },
        )
        self.assertEqual(invalid_response.status_code, 200)
        self.assertTrue(invalid_response.context["form"].errors)
        self.assertTrue(self.clinician.account.check_password(TEST_PASSWORD))

        response = self.client.post(
            reverse("clinic_auth:password_change"),
            {
                "old_password": TEST_PASSWORD,
                "new_password1": new_password,
                "new_password2": new_password,
            },
        )

        self.assertRedirects(
            response,
            reverse("clinic_auth:password_change_done"),
        )
        self.clinician.account.refresh_from_db()
        self.assertTrue(self.clinician.account.check_password(new_password))
        self.assertNotEqual(self.clinician.account.password, new_password)
