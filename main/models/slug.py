import uuid
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from .mixins import HistoryMixin, AbstractHistory
from util.json_schema import validate_schema_document, InvalidSchemaError


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

    # When set, this Slug is a "content type" definition rather than (or in
    # addition to) a normal page: `json` must hold a JSON Schema describing
    # a dynamic form, and slug/<parent_id>/create|edit render that form to
    # create/edit child instances of it. See main/views/slug_dynamic.py.
    is_dynamic = models.BooleanField(default=False)

    # A Slug's own content (render_template/json) can embed a raw <form>
    # that posts back to this same page - SlugView doesn't define a POST
    # handler yet (nothing needs one today), but its dispatch() already
    # checks this flag on any POST it does receive and requires a valid
    # reCAPTCHA token before proceeding, so that capability is safe to add
    # later without every future form author having to remember to wire
    # bot protection in themselves - see main.views.slug.SlugView.dispatch.
    requires_recaptcha = models.BooleanField(
        default=False,
        help_text="If this page's content embeds a form that posts back to it, "
                   "require a valid reCAPTCHA token on that POST."
    )

    # Generic Foreign Key linkage to bind ANY model instance dynamically
    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    object_id = models.UUIDField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    # Set on every page within a wiki, including the root itself (which
    # points to itself) - lets a page's wiki membership, and which wiki
    # tree it belongs to, be found in one query instead of walking `parent`
    # ancestry on every render. None means this Slug isn't part of a wiki.
    # Any existing Slug can become a wiki root on a whim (see
    # main/views/wiki.py) - this is deliberately not a separate model, per
    # the "wiki is a subset of slug" design: a wiki page is a plain Slug,
    # just one with wiki_root/wiki_body set and rendered through the wiki
    # layout instead of template_name/render_template/json.
    wiki_root = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="wiki_pages",
    )

    # Markdown article body for a wiki page (main.views.wiki), rendered via
    # util.wiki_markdown - supports [[Page Name]] / [[Page Name|Display
    # Text]] links resolved within this page's wiki_root tree. Kept
    # separate from render_template/json, which non-wiki Slugs still use.
    wiki_body = models.TextField(blank=True)

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

    def clean(self):
        super().clean()
        if self.is_dynamic:
            if not self.parent_id:
                raise ValidationError({'parent': "A dynamic slug must have a parent."})
            if not self.json:
                raise ValidationError({
                    'json': "A dynamic slug requires a JSON Schema describing its form fields."})
            try:
                validate_schema_document(self.json)
            except InvalidSchemaError as e:
                raise ValidationError({'json': f"Not a valid JSON Schema: {e}"})

    def save(self, *args, **kwargs):
        self.name = self.name.lower()
        # Enforced here too (not just in SlugForm) so is_dynamic's
        # invariants hold no matter how a Slug gets saved - the admin,
        # a script, a data migration, not just the staff create/edit form.
        self.clean()
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

    @property
    def is_wiki_root(self):
        return self.wiki_root_id is not None and self.wiki_root_id == self.id

    @property
    def is_wiki_page(self):
        return self.wiki_root_id is not None


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