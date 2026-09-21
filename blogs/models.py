# blogs/models.py
# Ported from tobuwebprod's blogs app. BlogPost.event now targets
# main.Event directly - Event tracking is native pp3 framework
# infrastructure (see main/models/event.py), so this app depends on main
# for it rather than needing a separate events app installed.
import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings
from main.models.mixins import HistoryMixin, AbstractHistory, SitemapEntry
from django.urls import reverse


class BlogPost(SitemapEntry, HistoryMixin, models.Model):
    sitemap_lastmod_field = 'date'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, db_index=True)
    date = models.DateTimeField(default=timezone.now)
    content = models.TextField(blank=True)
    tags = models.CharField(max_length=150, blank=True)
    meta_description = models.CharField(
        max_length=300,
        blank=True,
        help_text="Public-facing SEO description (<meta name=\"description\">). Falls back to a truncated excerpt of the content if left blank."
    )

    # File Attachment
    file = models.CharField(max_length=255, blank=True, null=True, help_text="Stored FileIO/S3 key")
    file_name = models.CharField(max_length=255, blank=True, null=True, help_text="Display title for attached file")

    # Event Integration - lets a post promote a calendar event (e.g. a
    # workshop write-up linking to its public event page/.ics).
    is_event = models.BooleanField(
        default=False,
        help_text="Check if this blog post is announcing a calendar event."
    )
    event = models.ForeignKey(
        'main.Event',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blog_posts",
        help_text="Associated event details."
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blog_posts"
    )

    class Meta:
        ordering = ['-date']
        verbose_name = "Blog Post"
        verbose_name_plural = "Blog Posts"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('blogs:blog_post', kwargs={'pk': self.id})


class BlogHistory(AbstractHistory):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    object = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name="history"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta(AbstractHistory.Meta):
        verbose_name_plural = "Blog Histories"

    def __str__(self):
        return f"Blog {self.object_id} @ {self.changed_at}"
