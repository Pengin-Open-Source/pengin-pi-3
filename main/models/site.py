# main/models/site.py
import uuid
from django.db import models
from django.conf import settings

from .mixins import HistoryMixin, AbstractHistory


class Site(HistoryMixin, models.Model):
    """
    Single global record of the site/company's own identity - not a
    business object. Every app that used to hardcode a company name/
    address/phone, or that promoted a page-content model (like an "About"
    page) to global template scope just to expose these fields, should
    read them from here instead via the `site` context variable
    (main.context_processors.site_context) or util.seo.build_organization_schema
    for JSON-LD.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    company_name = models.CharField(max_length=200, blank=True)
    tagline = models.CharField(max_length=300, blank=True)

    address1 = models.CharField(max_length=200, blank=True)
    address2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zipcode = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)
    google_maps_url = models.URLField(blank=True)

    phone = models.CharField(max_length=30, blank=True)
    webmaster = models.EmailField(blank=True)

    facebook = models.URLField(blank=True)
    twitter = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    youtube = models.URLField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Site"

    def __str__(self):
        return self.company_name or "Site"


class SiteHistory(AbstractHistory):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    object = models.ForeignKey(
        Site,
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
        verbose_name_plural = "Site Histories"

    def __str__(self):
        return f"Site {self.object_id} @ {self.changed_at}"
