from django.core.exceptions import ImproperlyConfigured


DEVELOPMENT_HOSTS = ["localhost", "127.0.0.1", "testserver"]
CONSOLE_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


def _required(environment, name):
    value = environment.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"{name} must be set.")
    return value


def _strict_bool(environment, name):
    value = _required(environment, name).lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise ImproperlyConfigured(f"{name} must be 'true' or 'false'.")


def _production_hosts(environment):
    value = _required(environment, "DJANGO_ALLOWED_HOSTS")
    hosts = [host.strip() for host in value.split(",")]
    if any(
        not host
        or host == "*"
        or "://" in host
        or "/" in host
        or any(character.isspace() for character in host)
        for host in hosts
    ):
        raise ImproperlyConfigured(
            "DJANGO_ALLOWED_HOSTS must be a comma-separated list of hostnames "
            "without schemes, paths, spaces, or wildcards."
        )
    return list(dict.fromkeys(hosts))


def _production_secret(environment):
    secret = _required(environment, "DJANGO_SECRET_KEY")
    if (
        len(secret) < 50
        or len(set(secret)) < 5
        or secret.startswith("django-insecure-")
    ):
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be a strong random value with at least "
            "50 characters and 5 unique characters."
        )
    return secret


def _production_hsts_seconds(environment):
    value = _required(environment, "DJANGO_HSTS_SECONDS")
    if not value.isdecimal():
        raise ImproperlyConfigured("DJANGO_HSTS_SECONDS must be a non-negative integer.")
    return int(value)


def load_security_settings(environment):
    environment_name = environment.get("DJANGO_ENV", "").strip().lower()
    if environment_name not in {"development", "production"}:
        raise ImproperlyConfigured(
            "DJANGO_ENV must be explicitly set to 'development' or 'production'."
        )

    if environment_name == "development":
        secret = _required(environment, "DJANGO_SECRET_KEY")
        return {
            "ENVIRONMENT": environment_name,
            "SECRET_KEY": secret,
            "DEBUG": True,
            "ALLOWED_HOSTS": DEVELOPMENT_HOSTS.copy(),
            "SECURE_SSL_REDIRECT": False,
            "SECURE_HSTS_SECONDS": 0,
            "SESSION_COOKIE_SECURE": False,
            "CSRF_COOKIE_SECURE": False,
            "MAILERS": {
                "default": {"BACKEND": CONSOLE_EMAIL_BACKEND},
            },
        }

    secret = _production_secret(environment)
    hosts = _production_hosts(environment)
    https_redirect = _strict_bool(environment, "DJANGO_HTTPS_REDIRECT")
    hsts_seconds = _production_hsts_seconds(environment)
    if hsts_seconds and not https_redirect:
        raise ImproperlyConfigured(
            "DJANGO_HSTS_SECONDS must be 0 when DJANGO_HTTPS_REDIRECT is false."
        )

    email_backend = _required(environment, "DJANGO_EMAIL_BACKEND")
    if email_backend == CONSOLE_EMAIL_BACKEND:
        raise ImproperlyConfigured(
            "DJANGO_EMAIL_BACKEND must not use the development console backend."
        )

    return {
        "ENVIRONMENT": environment_name,
        "SECRET_KEY": secret,
        "DEBUG": False,
        "ALLOWED_HOSTS": hosts,
        "SECURE_SSL_REDIRECT": https_redirect,
        "SECURE_HSTS_SECONDS": hsts_seconds,
        "SESSION_COOKIE_SECURE": True,
        "CSRF_COOKIE_SECURE": True,
        "MAILERS": {"default": {"BACKEND": email_backend}},
    }
