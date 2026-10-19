import re
from io import StringIO
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from clinic.models import Department, StaffProfile

User = get_user_model()
TEST_PASSWORD = "S3cure-Clinic-Password-927!"


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class AuthenticationAndAuthorizationTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="General Practice")
        self.admin_profile = self.create_staff(
            "admin",
            StaffProfile.Role.ADMINISTRATOR,
        )

    def create_staff(
        self,
        username,
        role,
        *,
        active=True,
        profile_active=True,
        staff_identifier=None,
    ):
        user = User.objects.create_user(
            username=username,
            password=TEST_PASSWORD,
            email=f"{username}@example.test",
            is_active=active,
        )
        profile = StaffProfile.objects.create(
            account=user,
            role=role,
            staff_identifier=staff_identifier,
            is_active=profile_active,
        )
        profile.departments.add(self.department)
        return profile

    def post_login(self, username="admin", password=TEST_PASSWORD, **data):
        return self.client.post(
            reverse("clinic_auth:login"),
            {"username": username, "password": password, **data},
        )

    def test_successful_login_redirects_to_staff_home(self):
        response = self.post_login()

        self.assertRedirects(response, reverse("clinic_auth:staff_home"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertFalse(self.admin_profile.account.is_staff)
        self.assertFalse(self.admin_profile.account.is_superuser)

    def test_login_page_uses_common_smart_clinic_wording(self):
        response = self.client.get(reverse("clinic_auth:login"))

        self.assertContains(response, "<h1>Sign in to Smart Clinic</h1>", html=True)
        self.assertContains(response, "Secure access for the clinic team")
        self.assertContains(
            response,
            "clinic account username, email address, or employee identifier",
        )
        self.assertContains(response, reverse("clinic_auth:password_reset"))
        self.assertNotContains(response, "Staff sign in")
        self.assertNotContains(response, "Staff access portal")

    def test_successful_login_shows_role_specific_clinic_dashboard(self):
        profiles = [
            self.admin_profile,
            self.create_staff("reception", StaffProfile.Role.RECEPTIONIST),
            self.create_staff("doctor", StaffProfile.Role.CLINICIAN),
            self.create_staff("nurse", StaffProfile.Role.NURSE),
        ]

        for profile in profiles:
            with self.subTest(role=profile.role):
                self.client.logout()
                response = self.post_login(username=profile.account.username)
                self.assertRedirects(
                    response,
                    reverse("clinic_auth:staff_home"),
                )
                dashboard = self.client.get(response.url)
                self.assertContains(
                    dashboard,
                    f"{profile.get_role_display()} dashboard",
                )

    def test_safe_next_redirects_to_an_authorized_application_page(self):
        response = self.post_login(
            next=reverse("clinic_auth:staff_account_list")
        )

        self.assertRedirects(
            response,
            reverse("clinic_auth:staff_account_list"),
        )

    def test_application_administrator_next_to_django_admin_uses_clinic_home(self):
        response = self.post_login(next=reverse("admin:index"))

        self.assertRedirects(response, reverse("clinic_auth:staff_home"))
        self.assertFalse(self.admin_profile.account.is_staff)
        self.assertFalse(self.admin_profile.account.is_superuser)

        admin_response = self.client.get(reverse("admin:index"))
        self.assertRedirects(
            admin_response,
            f"{reverse('admin:login')}?next={reverse('admin:index')}",
        )

    def test_django_admin_remains_available_to_django_superuser(self):
        django_admin = User.objects.create_superuser(
            username="django-admin",
            email="django-admin@example.test",
            password=TEST_PASSWORD,
        )
        self.client.force_login(django_admin)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)

    def test_public_home_promotes_clinic_login_not_django_admin(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, reverse("clinic_auth:login"))
        self.assertNotContains(response, 'href="/admin/"')
        self.assertContains(response, "Better coordination for every step of care.")
        for feature in (
            "Secure by design",
            "People, connected",
            "Care, coordinated",
        ):
            with self.subTest(feature=feature):
                self.assertContains(response, feature)

    def test_invalid_credentials_return_generic_error(self):
        response = self.post_login(password="wrong password")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct")
        self.assertNotContains(response, "admin@example.test")

    def test_login_accepts_staff_identifier(self):
        profile = self.create_staff(
            "identifier-user",
            StaffProfile.Role.RECEPTIONIST,
            staff_identifier="ST-1001",
        )

        response = self.post_login(username=profile.staff_identifier)

        self.assertRedirects(response, reverse("clinic_auth:staff_home"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_rejects_inactive_user_account(self):
        profile = self.create_staff(
            "inactive-user",
            StaffProfile.Role.RECEPTIONIST,
            active=False,
        )

        response = self.post_login(username=profile.account.username)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_rejects_inactive_staff_profile(self):
        profile = self.create_staff(
            "inactive-profile",
            StaffProfile.Role.RECEPTIONIST,
            profile_active=False,
        )

        response = self.post_login(username=profile.account.username)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, "Please enter a correct")

    def test_login_does_not_accept_account_without_staff_profile(self):
        User.objects.create_user(username="unprofiled", password=TEST_PASSWORD)

        response = self.post_login(username="unprofiled")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_external_login_redirect_is_rejected(self):
        response = self.post_login(next="https://evil.example/steal-session")

        self.assertRedirects(response, reverse("clinic_auth:staff_home"))
        self.assertNotIn("evil.example", response.url)

    def test_logout_requires_post_and_ends_session(self):
        self.client.force_login(self.admin_profile.account)
        logout_url = reverse("clinic_auth:logout")

        self.assertEqual(self.client.get(logout_url).status_code, 405)
        response = self.client.post(logout_url)

        self.assertRedirects(response, reverse("clinic_auth:login"))
        protected = self.client.get(reverse("clinic_auth:staff_home"))
        self.assertEqual(protected.status_code, 302)
        self.assertIn(reverse("clinic_auth:login"), protected.url)

    def test_all_four_active_roles_can_access_staff_home_and_change_password(self):
        profiles = [
            self.admin_profile,
            self.create_staff("reception", StaffProfile.Role.RECEPTIONIST),
            self.create_staff("doctor", StaffProfile.Role.CLINICIAN),
            self.create_staff("nurse", StaffProfile.Role.NURSE),
        ]

        for profile in profiles:
            with self.subTest(role=profile.role):
                self.client.force_login(profile.account)
                self.assertEqual(
                    self.client.get(reverse("clinic_auth:staff_home")).status_code,
                    200,
                )
                self.assertEqual(
                    self.client.get(
                        reverse("clinic_auth:password_change")
                    ).status_code,
                    200,
                )

    def test_unauthenticated_staff_pages_redirect_to_login(self):
        for url in (
            reverse("clinic_auth:staff_home"),
            reverse("clinic_auth:password_change"),
            reverse("clinic_auth:staff_account_list"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("clinic_auth:login"), response.url)

    def test_inactive_profile_is_logged_out_from_existing_session(self):
        profile = self.create_staff("deactivated", StaffProfile.Role.NURSE)
        self.client.force_login(profile.account)
        profile.is_active = False
        profile.save(update_fields=["is_active"])

        response = self.client.get(reverse("clinic_auth:staff_home"))

        self.assertRedirects(response, reverse("clinic_auth:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_non_admin_roles_are_denied_staff_account_endpoints(self):
        profiles = [
            self.create_staff("reception", StaffProfile.Role.RECEPTIONIST),
            self.create_staff("doctor", StaffProfile.Role.CLINICIAN),
            self.create_staff("nurse", StaffProfile.Role.NURSE),
        ]
        account = self.create_staff("target", StaffProfile.Role.RECEPTIONIST)
        urls = (
            reverse("clinic_auth:staff_account_list"),
            reverse("clinic_auth:staff_account_create"),
            reverse("clinic_auth:staff_account_profile", args=[account.pk]),
            reverse(
                "clinic_auth:staff_account_edit",
                args=[account.pk],
            ),
            reverse("clinic_auth:staff_account_status", args=[account.pk]),
        )

        for profile in profiles:
            self.client.force_login(profile.account)
            for url in urls:
                with self.subTest(role=profile.role, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)

    def test_non_admin_post_cannot_create_or_modify_staff_accounts(self):
        receptionist = self.create_staff(
            "reception",
            StaffProfile.Role.RECEPTIONIST,
        )
        target = self.create_staff("target", StaffProfile.Role.NURSE)
        self.client.force_login(receptionist.account)

        create_response = self.client.post(
            reverse("clinic_auth:staff_account_create"),
            {
                "username": "attempted",
                "first_name": "Attempt",
                "last_name": "User",
                "email": "attempt@example.test",
                "role": StaffProfile.Role.ADMINISTRATOR,
                "password1": TEST_PASSWORD,
                "password2": TEST_PASSWORD,
            },
        )
        edit_response = self.client.post(
            reverse("clinic_auth:staff_account_edit", args=[target.pk]),
            {
                "username": "target",
                "first_name": "Changed",
                "last_name": "Name",
                "email": "target@example.test",
                "role": StaffProfile.Role.ADMINISTRATOR,
                "is_active": "on",
            },
        )
        status_response = self.client.post(
            reverse("clinic_auth:staff_account_status", args=[target.pk])
        )

        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(edit_response.status_code, 403)
        self.assertEqual(status_response.status_code, 403)
        self.assertFalse(User.objects.filter(username="attempted").exists())
        target.account.refresh_from_db()
        self.assertNotEqual(target.account.first_name, "Changed")
        target.refresh_from_db()
        self.assertEqual(target.role, StaffProfile.Role.NURSE)

    def test_admin_can_create_hashed_staff_account_with_role_and_department(self):
        self.client.force_login(self.admin_profile.account)

        response = self.client.post(
            reverse("clinic_auth:staff_account_create"),
            {
                "username": "new-clinician",
                "first_name": "Fictional",
                "last_name": "Clinician",
                "email": "new-clinician@example.test",
                "role": StaffProfile.Role.CLINICIAN,
                "staff_identifier": "ST-NEW",
                "phone_number": "000-000-0000",
                "departments": [self.department.pk],
                "password1": TEST_PASSWORD,
                "password2": TEST_PASSWORD,
            },
        )

        profile = User.objects.get(username="new-clinician").staff_profile
        self.assertRedirects(
            response,
            reverse("clinic_auth:staff_account_profile", args=[profile.pk]),
        )
        user = User.objects.get(username="new-clinician")
        self.assertTrue(user.check_password(TEST_PASSWORD))
        self.assertNotEqual(user.password, TEST_PASSWORD)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(profile.role, StaffProfile.Role.CLINICIAN)
        self.assertEqual(profile.staff_identifier, "ST-NEW")
        self.assertEqual(list(profile.departments.all()), [self.department])

    def test_admin_can_assign_each_defined_role(self):
        self.client.force_login(self.admin_profile.account)

        for suffix, role in (
            ("admin", StaffProfile.Role.ADMINISTRATOR),
            ("reception", StaffProfile.Role.RECEPTIONIST),
            ("clinician", StaffProfile.Role.CLINICIAN),
            ("nurse", StaffProfile.Role.NURSE),
        ):
            with self.subTest(role=role):
                response = self.client.post(
                    reverse("clinic_auth:staff_account_create"),
                    {
                        "username": f"role-{suffix}",
                        "first_name": "Fictional",
                        "last_name": "Staff",
                        "email": f"role-{suffix}@example.test",
                        "role": role,
                        "password1": TEST_PASSWORD,
                        "password2": TEST_PASSWORD,
                    },
                )
                profile = User.objects.get(username=f"role-{suffix}").staff_profile
                self.assertRedirects(
                    response,
                    reverse("clinic_auth:staff_account_profile", args=[profile.pk]),
                )
                self.assertEqual(profile.role, role)
                self.assertTrue(profile.staff_identifier.startswith("ST-"))

    def test_first_admin_command_creates_non_superuser_with_hashed_password(self):
        output = StringIO()
        with (
            patch("builtins.input", side_effect=[
                "first-admin",
                "first-admin@example.test",
                "First",
                "Admin",
            ]),
            patch(
                "clinic.management.commands.create_staff_admin.getpass",
                side_effect=[TEST_PASSWORD, TEST_PASSWORD],
            ),
        ):
            call_command("create_staff_admin", stdout=output)

        user = User.objects.get(username="first-admin")
        self.assertTrue(user.check_password(TEST_PASSWORD))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(
            user.staff_profile.role,
            StaffProfile.Role.ADMINISTRATOR,
        )
        self.assertIn("created", output.getvalue())

    def test_invalid_role_and_weak_password_do_not_create_account(self):
        self.client.force_login(self.admin_profile.account)
        response = self.client.post(
            reverse("clinic_auth:staff_account_create"),
            {
                "username": "invalid-role",
                "first_name": "Fictional",
                "last_name": "Staff",
                "email": "invalid@example.test",
                "role": "superuser",
                "password1": "password",
                "password2": "password",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="invalid-role").exists())
        self.assertTrue(response.context["form"].errors)

    def test_admin_can_update_role_details_and_departments(self):
        target = self.create_staff("target", StaffProfile.Role.RECEPTIONIST)
        self.client.force_login(self.admin_profile.account)

        response = self.client.post(
            reverse("clinic_auth:staff_account_edit", args=[target.pk]),
            {
                "username": target.account.username,
                "first_name": "Fictional",
                "last_name": "Clinician",
                "email": target.account.email,
                "role": StaffProfile.Role.CLINICIAN,
                "staff_identifier": "ST-EDIT",
                "phone_number": "000-000-0001",
                "departments": [self.department.pk],
            },
        )

        self.assertRedirects(
            response,
            reverse("clinic_auth:staff_account_profile", args=[target.pk]),
        )
        target.refresh_from_db()
        target.account.refresh_from_db()
        self.assertEqual(target.role, StaffProfile.Role.CLINICIAN)
        self.assertTrue(target.is_active)
        self.assertTrue(target.account.is_active)
        self.assertEqual(target.account.last_name, "Clinician")

    def test_last_active_admin_cannot_be_demoted(self):
        self.client.force_login(self.admin_profile.account)
        response = self.client.post(
            reverse(
                "clinic_auth:staff_account_edit",
                args=[self.admin_profile.pk],
            ),
            {
                "username": "admin",
                "first_name": "Admin",
                "last_name": "User",
                "email": "admin@example.test",
                "role": StaffProfile.Role.RECEPTIONIST,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.admin_profile.refresh_from_db()
        self.assertEqual(
            self.admin_profile.role,
            StaffProfile.Role.ADMINISTRATOR,
        )

    def test_admin_can_deactivate_staff_account_and_prevent_login(self):
        target = self.create_staff("target", StaffProfile.Role.NURSE)
        self.client.force_login(self.admin_profile.account)
        response = self.client.post(
            reverse("clinic_auth:staff_account_status", args=[target.pk]),
        )

        self.assertRedirects(
            response,
            reverse("clinic_auth:staff_account_profile", args=[target.pk]),
        )
        target.refresh_from_db()
        target.account.refresh_from_db()
        self.assertFalse(target.is_active)
        self.assertFalse(target.account.is_active)
        self.client.logout()
        login_response = self.post_login(username="target")
        self.assertEqual(login_response.status_code, 200)
        self.assertFalse(login_response.wsgi_request.user.is_authenticated)

    def test_staff_directory_renders_searches_and_filters(self):
        target = self.create_staff(
            "directory-nurse",
            StaffProfile.Role.NURSE,
            staff_identifier="ST-DIRECTORY",
        )
        target.account.first_name = "Fictional"
        target.account.last_name = "Caregiver"
        target.account.save(update_fields=("first_name", "last_name"))
        target.phone_number = "555-0101"
        target.save(update_fields=("phone_number",))
        self.client.force_login(self.admin_profile.account)

        directory_url = reverse("clinic_auth:staff_account_list")
        for query in (
            "ST-DIRECTORY",
            "Fictional",
            "555-0101",
        ):
            with self.subTest(query=query):
                response = self.client.get(directory_url, {"query": query})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Fictional Caregiver")
                self.assertEqual(
                    [profile.pk for profile in response.context["staff_profiles"]],
                    [target.pk],
                )
        department_response = self.client.get(
            directory_url,
            {"query": "General Practice"},
        )
        self.assertIn(
            target.pk,
            [
                profile.pk
                for profile in department_response.context["staff_profiles"]
            ],
        )

        role_response = self.client.get(
            directory_url,
            {"role": StaffProfile.Role.NURSE, "status": "active"},
        )
        self.assertEqual(role_response.status_code, 200)
        self.assertContains(role_response, "ST-DIRECTORY")

        inactive_response = self.client.get(
            directory_url,
            {"status": "inactive"},
        )
        self.assertEqual(inactive_response.status_code, 200)
        self.assertNotContains(inactive_response, "ST-DIRECTORY")

    def test_staff_directory_paginates_and_profile_does_not_expose_hashes(self):
        target = self.create_staff(
            "profile-nurse",
            StaffProfile.Role.NURSE,
            staff_identifier="ST-PROFILE",
        )
        for index in range(26):
            self.create_staff(f"page-{index}", StaffProfile.Role.NURSE)
        self.client.force_login(self.admin_profile.account)

        response = self.client.get(reverse("clinic_auth:staff_account_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["staff_profiles"].paginator.num_pages, 2)
        self.assertContains(response, "Next")

        profile_response = self.client.get(
            reverse("clinic_auth:staff_account_profile", args=[target.pk])
        )
        self.assertEqual(profile_response.status_code, 200)
        self.assertContains(profile_response, "ST-PROFILE")
        self.assertContains(profile_response, "Nurse")
        self.assertNotContains(profile_response, target.account.password)
        self.assertNotContains(profile_response, "pbkdf2_sha256$")

    def test_staff_registration_requires_fields_and_rejects_duplicate_identity(self):
        self.client.force_login(self.admin_profile.account)
        create_url = reverse("clinic_auth:staff_account_create")
        base_data = {
            "username": "another-nurse",
            "first_name": "Fictional",
            "last_name": "Nurse",
            "email": "another-nurse@example.test",
            "role": StaffProfile.Role.NURSE,
            "password1": TEST_PASSWORD,
            "password2": TEST_PASSWORD,
        }

        missing = self.client.post(create_url, {"username": "missing"})
        self.assertEqual(missing.status_code, 200)
        self.assertTrue(missing.context["form"].errors)
        self.assertFalse(User.objects.filter(username="missing").exists())

        self.create_staff(
            "duplicate-identifier",
            StaffProfile.Role.NURSE,
            staff_identifier="ST-TAKEN",
        )
        duplicate_identifier = self.client.post(
            create_url,
            {**base_data, "staff_identifier": "st-taken"},
        )
        self.assertEqual(duplicate_identifier.status_code, 200)
        self.assertIn(
            "staff_identifier",
            duplicate_identifier.context["form"].errors,
        )
        self.assertFalse(User.objects.filter(username="another-nurse").exists())

        duplicate_email = self.client.post(
            create_url,
            {**base_data, "email": self.admin_profile.account.email.upper()},
        )
        self.assertEqual(duplicate_email.status_code, 200)
        self.assertIn("email", duplicate_email.context["form"].errors)
        self.assertFalse(User.objects.filter(username="another-nurse").exists())

    def test_inactive_department_cannot_be_assigned(self):
        inactive_department = Department.objects.create(
            name="Retired Unit",
            is_active=False,
        )
        self.client.force_login(self.admin_profile.account)
        response = self.client.post(
            reverse("clinic_auth:staff_account_create"),
            {
                "username": "invalid-department",
                "first_name": "Fictional",
                "last_name": "Staff",
                "email": "invalid-department@example.test",
                "role": StaffProfile.Role.NURSE,
                "departments": [inactive_department.pk],
                "password1": TEST_PASSWORD,
                "password2": TEST_PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("departments", response.context["form"].errors)
        self.assertFalse(User.objects.filter(username="invalid-department").exists())

    def test_admin_cannot_deactivate_self_or_last_active_administrator(self):
        self.client.force_login(self.admin_profile.account)
        self_deactivation = self.client.post(
            reverse(
                "clinic_auth:staff_account_status",
                args=[self.admin_profile.pk],
            )
        )
        self.assertRedirects(
            self_deactivation,
            reverse(
                "clinic_auth:staff_account_profile",
                args=[self.admin_profile.pk],
            ),
        )
        self.admin_profile.refresh_from_db()
        self.assertTrue(self.admin_profile.is_active)

        second_admin = self.create_staff(
            "second-admin",
            StaffProfile.Role.ADMINISTRATOR,
        )
        self.client.post(
            reverse("clinic_auth:staff_account_status", args=[second_admin.pk])
        )
        second_admin.refresh_from_db()
        self.assertFalse(second_admin.is_active)
        self.assertFalse(second_admin.account.is_active)

    def test_inactive_staff_can_be_reactivated_by_administrator(self):
        target = self.create_staff(
            "reactivate",
            StaffProfile.Role.RECEPTIONIST,
            active=False,
            profile_active=False,
        )
        self.client.force_login(self.admin_profile.account)
        response = self.client.post(
            reverse("clinic_auth:staff_account_status", args=[target.pk])
        )
        self.assertRedirects(
            response,
            reverse("clinic_auth:staff_account_profile", args=[target.pk]),
        )
        target.refresh_from_db()
        target.account.refresh_from_db()
        self.assertTrue(target.is_active)
        self.assertTrue(target.account.is_active)

    def test_password_change_uses_validators_and_preserves_session(self):
        profiles = [
            self.admin_profile,
            self.create_staff("reception", StaffProfile.Role.RECEPTIONIST),
            self.create_staff("doctor", StaffProfile.Role.CLINICIAN),
            self.create_staff("nurse", StaffProfile.Role.NURSE),
        ]

        for index, profile in enumerate(profiles):
            with self.subTest(role=profile.role):
                self.client.force_login(profile.account)
                response = self.client.post(
                    reverse("clinic_auth:password_change"),
                    {
                        "old_password": TEST_PASSWORD,
                        "new_password1": f"New-Secure-Password-{index}-88!",
                        "new_password2": f"New-Secure-Password-{index}-88!",
                    },
                )
                self.assertRedirects(
                    response,
                    reverse("clinic_auth:password_change_done"),
                )
                profile.account.refresh_from_db()
                self.assertTrue(
                    profile.account.check_password(
                        f"New-Secure-Password-{index}-88!"
                    )
                )
                self.assertEqual(
                    self.client.get(reverse("clinic_auth:staff_home")).status_code,
                    200,
                )
                profile.account.set_password(TEST_PASSWORD)
                profile.account.save(update_fields=["password"])

    def test_password_change_rejects_password_that_fails_validators(self):
        self.client.force_login(self.admin_profile.account)
        response = self.client.post(
            reverse("clinic_auth:password_change"),
            {
                "old_password": TEST_PASSWORD,
                "new_password1": "admin",
                "new_password2": "admin",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.admin_profile.account.refresh_from_db()
        self.assertTrue(self.admin_profile.account.check_password(TEST_PASSWORD))

    def test_staff_account_pages_render_without_password_fields(self):
        self.client.force_login(self.admin_profile.account)
        response = self.client.get(reverse("clinic_auth:staff_account_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, TEST_PASSWORD)
        self.assertNotContains(response, "pbkdf2_sha256$")
        self.assertContains(response, "admin")

    def test_csrf_protects_login_logout_and_account_changes(self):
        client = Client(enforce_csrf_checks=True)
        login_url = reverse("clinic_auth:login")
        logout_url = reverse("clinic_auth:logout")
        create_url = reverse("clinic_auth:staff_account_create")
        status_url = reverse(
            "clinic_auth:staff_account_status",
            args=[self.admin_profile.pk],
        )

        self.assertEqual(client.get(login_url).status_code, 200)
        self.assertEqual(
            client.post(login_url, {"username": "admin", "password": TEST_PASSWORD}).status_code,
            403,
        )
        client.force_login(self.admin_profile.account)
        self.assertEqual(client.post(logout_url).status_code, 403)
        self.assertEqual(
            client.post(create_url, {"username": "csrf-attempt"}).status_code,
            403,
        )
        self.assertEqual(client.get(status_url).status_code, 405)
        self.assertEqual(client.post(status_url).status_code, 403)

    @override_settings(
        MAILERS={
            "default": {
                "BACKEND": "django.core.mail.backends.locmem.EmailBackend"
            }
        }
    )
    def test_password_reset_delivers_token_only_for_active_staff_and_resets(self):
        response = self.client.post(
            reverse("clinic_auth:password_reset"),
            {"email": self.admin_profile.account.email},
        )

        self.assertRedirects(response, reverse("clinic_auth:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        reset_path = re.search(
            r"http://testserver(/accounts/password/reset/[^\s]+)",
            mail.outbox[0].body,
        ).group(1)
        parsed_path = urlsplit(reset_path).path
        confirm_response = self.client.get(parsed_path)
        self.assertEqual(confirm_response.status_code, 302)
        confirm_url = urlsplit(confirm_response.url).path
        form_response = self.client.get(confirm_url)
        self.assertEqual(form_response.status_code, 200)
        self.assertContains(form_response, "Choose a new password")
        reset_response = self.client.post(
            confirm_url,
            {
                "new_password1": "Password-Reset-Secure-927!",
                "new_password2": "Password-Reset-Secure-927!",
            },
        )
        self.assertRedirects(
            reset_response,
            reverse("clinic_auth:password_reset_complete"),
        )
        self.admin_profile.account.refresh_from_db()
        self.assertTrue(
            self.admin_profile.account.check_password(
                "Password-Reset-Secure-927!"
            )
        )

    @override_settings(
        MAILERS={
            "default": {
                "BACKEND": "django.core.mail.backends.locmem.EmailBackend"
            }
        }
    )
    def test_password_reset_does_not_disclose_unknown_or_inactive_staff(self):
        inactive = self.create_staff(
            "inactive",
            StaffProfile.Role.NURSE,
            profile_active=False,
        )
        for email in ("unknown@example.test", inactive.account.email):
            with self.subTest(email=email):
                response = self.client.post(
                    reverse("clinic_auth:password_reset"),
                    {"email": email},
                )
                self.assertRedirects(
                    response,
                    reverse("clinic_auth:password_reset_done"),
                )
        self.assertEqual(len(mail.outbox), 0)
