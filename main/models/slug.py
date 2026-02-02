# main/models/slug.py
from django.db import models
import uuid
from django.conf import settings

from .mixins import HistoryMixin
from .history import AbstractHistory


class Slug(HistoryMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children"
    )

    name = models.CharField(max_length=120)
    meta_tags = models.CharField(max_length=300)
    meta_description = models.CharField(max_length=300)

    template_name = models.CharField(max_length=300, blank=True)
    render_template = models.TextField(blank=True)
    json = models.TextField(blank=True)

    date = models.DateTimeField(auto_now_add=True)

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="slugs_created"
    )

    class Meta:
        verbose_name_plural = "Slugs"

    def __str__(self):
        return self.name


class SlugHistory(AbstractHistory):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    object = models.ForeignKey(
        Slug,
        on_delete=models.CASCADE,
        related_name="history"
    )

    class Meta(AbstractHistory.Meta):
        verbose_name_plural = "Slug Histories"

    def __str__(self):
        return f"Slug {self.object_id} @ {self.changed_at}"
