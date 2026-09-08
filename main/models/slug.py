import uuid
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from .mixins import HistoryMixin, AbstractHistory


class Slug(HistoryMixin, models.Model):
    #TODO: put title in slug for SEO
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
    
    # Updated to native JSONField for flexible data/schema storage
    json = models.JSONField(default=dict, blank=True)

    # Generic Foreign Key linkage to bind ANY model instance dynamically
    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    object_id = models.UUIDField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    def save(self, *args, **kwargs):
        self.name = self.name.lower()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        """Recursively builds the URL path based on parent ancestry."""
        if not self.parent and self.name == 'home':
            return '/'

        parts = [self.name]
        curr = self.parent
        while curr:
            parts.append(curr.name)
            curr = curr.parent
        parts.reverse()
        return f"/{'/'.join(parts)}/"


class SlugHistory(AbstractHistory):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    object = models.ForeignKey(
        Slug,
        on_delete=models.CASCADE,
        related_name="history"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+"
    )

    class Meta(AbstractHistory.Meta):
        verbose_name_plural = "Slug Histories"

    def __str__(self):
        return f"Slug {self.object_id} @ {self.changed_at}"