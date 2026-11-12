from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.utils.module_loading import import_string


class MailerRouterBackend(BaseEmailBackend):
    """Resolve the configured clinic mailer at send time, including overrides."""

    def send_messages(self, email_messages):
        backend_path = settings.MAILERS["default"]["BACKEND"]
        backend_class = import_string(backend_path)
        backend = backend_class(fail_silently=self.fail_silently)
        return backend.send_messages(email_messages)
