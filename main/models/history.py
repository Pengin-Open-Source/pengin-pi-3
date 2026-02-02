# main/models/history.py
from django.db import models
from django.conf import settings


class AbstractHistory(models.Model):
    snapshot = models.JSONField()
    changed_at = models.DateTimeField()

    last_author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+"
    )

    modify_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+"
    )

    class Meta:
        abstract = True
        ordering = ("-changed_at",)
