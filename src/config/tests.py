from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.security_settings import (
    CONSOLE_EMAIL_BACKEND,
    DEVELOPMENT_HOSTS,
    load_security_settings,
)


STRONG_TEST_SECRET = (
    "M12-Configuration-Test-Only-Secret-Value-With-Many-Characters-827!"
)


class SecuritySettingsTests(SimpleTestCase):
    def production_environment(self, **overrides):
        environment = {
            "DJANGO_ENV": "production",
            "DJANGO_SECRET_KEY": STRONG_TEST_SECRET,
            "DJANGO_ALLOWED_HOSTS": "clinic.example.test,records.example.test",
            "DJANGO_HTTPS_REDIRECT": "true",
            "DJANGO_HSTS_SECONDS": "3600",
            "DJANGO_EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        }
        environment.update(overrides)
        return environment

    def test_environment_selection_is_required_and_restricted(self):
        for environment in ({}, {"DJANGO_ENV": "staging"}):
            with self.subTest(environment=environment):
                with self.assertRaisesMessage(
                    ImproperlyConfigured,
                    "DJANGO_ENV must be explicitly set",
                ):
                    load_security_settings(environment)

    def test_production_requires_strong_secret(self):
        for secret in ("", "short-secret", "django-insecure-" + ("a" * 60)):
            with self.subTest(secret_length=len(secret)):
                with self.assertRaisesMessage(
                    ImproperlyConfigured,
                    "DJANGO_SECRET_KEY",
                ):
                    load_security_settings(
                        self.production_environment(DJANGO_SECRET_KEY=secret)
                    )

    def test_production_requires_explicit_nonempty_host_allowlist(self):
        for hosts in ("", " , ", "*", "https://clinic.example.test", "clinic.test,"):
            with self.subTest(hosts=hosts):
                with self.assertRaisesMessage(
                    ImproperlyConfigured,
                    "DJANGO_ALLOWED_HOSTS",
                ):
                    load_security_settings(
                        self.production_environment(DJANGO_ALLOWED_HOSTS=hosts)
                    )

    def test_production_disables_debug_and_enables_secure_cookies(self):
        settings = load_security_settings(self.production_environment())

        self.assertFalse(settings["DEBUG"])
        self.assertTrue(settings["SESSION_COOKIE_SECURE"])
        self.assertTrue(settings["CSRF_COOKIE_SECURE"])
        self.assertEqual(
            settings["ALLOWED_HOSTS"],
            ["clinic.example.test", "records.example.test"],
        )
        self.assertNotIn("SECURE_PROXY_SSL_HEADER", settings)

    def test_boolean_environment_values_are_strict(self):
        for value in ("yes", "1", "on"):
            with self.subTest(value=value):
                with self.assertRaisesMessage(
                    ImproperlyConfigured,
                    "DJANGO_HTTPS_REDIRECT must be 'true' or 'false'",
                ):
                    load_security_settings(
                        self.production_environment(DJANGO_HTTPS_REDIRECT=value)
                    )

    def test_https_redirect_and_hsts_are_explicit(self):
        settings = load_security_settings(
            self.production_environment(
                DJANGO_HTTPS_REDIRECT="false",
                DJANGO_HSTS_SECONDS="0",
            )
        )
        self.assertFalse(settings["SECURE_SSL_REDIRECT"])
        self.assertEqual(settings["SECURE_HSTS_SECONDS"], 0)

        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "DJANGO_HSTS_SECONDS must be 0",
        ):
            load_security_settings(
                self.production_environment(
                    DJANGO_HTTPS_REDIRECT="false",
                    DJANGO_HSTS_SECONDS="3600",
                )
            )

    def test_invalid_hsts_value_is_rejected(self):
        for value in ("-1", "1.5", "invalid"):
            with self.subTest(value=value):
                with self.assertRaisesMessage(
                    ImproperlyConfigured,
                    "DJANGO_HSTS_SECONDS must be a non-negative integer",
                ):
                    load_security_settings(
                        self.production_environment(DJANGO_HSTS_SECONDS=value)
                    )

    def test_production_requires_non_console_email_backend(self):
        for backend in ("", CONSOLE_EMAIL_BACKEND):
            with self.subTest(backend=backend):
                with self.assertRaisesMessage(
                    ImproperlyConfigured,
                    "DJANGO_EMAIL_BACKEND",
                ):
                    load_security_settings(
                        self.production_environment(DJANGO_EMAIL_BACKEND=backend)
                    )

    def test_local_development_preserves_http_test_hosts_and_console_email(self):
        settings = load_security_settings(
            {
                "DJANGO_ENV": "development",
                "DJANGO_SECRET_KEY": "local-development-test-secret",
            }
        )

        self.assertTrue(settings["DEBUG"])
        self.assertEqual(settings["ALLOWED_HOSTS"], DEVELOPMENT_HOSTS)
        self.assertIn("testserver", settings["ALLOWED_HOSTS"])
        self.assertFalse(settings["SECURE_SSL_REDIRECT"])
        self.assertFalse(settings["SESSION_COOKIE_SECURE"])
        self.assertFalse(settings["CSRF_COOKIE_SECURE"])
        self.assertEqual(
            settings["MAILERS"]["default"]["BACKEND"],
            CONSOLE_EMAIL_BACKEND,
        )
