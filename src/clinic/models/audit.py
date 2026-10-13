from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        blank=True,
        null=True,
    )
    action = models.CharField(max_length=100)
    occurred_at = models.DateTimeField(auto_now_add=True)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    object_id = models.CharField(max_length=64, blank=True, null=True)
    content_object = GenericForeignKey("content_type", "object_id")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(
                fields=["actor", "occurred_at"],
                name="clinic_audit_actor_ts_idx",
            ),
            models.Index(
                fields=["action", "occurred_at"],
                name="clinic_audit_action_ts_idx",
            ),
            models.Index(
                fields=["content_type", "object_id"],
                name="clinic_audit_target_idx",
            ),
        ]

    def __str__(self):
        return f"{self.action} at {self.occurred_at:%Y-%m-%d %H:%M:%S}"
