from django.db import models
import uuid
from django.conf import settings
from django.utils import timezone


class Slug(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
        verbose_name="Parent Slug"
    )
    name = models.CharField(max_length=120)
    meta_tags = models.CharField(max_length=300)
    meta_description = models.CharField(max_length=300)
    template_name = models.CharField(max_length=300)
    render_template = models.TextField()
    json = models.TextField()
    date = models.DateTimeField(auto_now_add=True)  # creation timestamp
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Author",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="slugs_created"
    )

    class Meta:
        verbose_name_plural = "Slugs"

    def save(self, *args, user=None, **kwargs):
        # Save history if updating
        if self.pk and Slug.objects.filter(pk=self.pk).exists():
            SlugHistory.objects.create(
                slug=self,
                parent=self.parent,
                name=self.name,
                meta_tags=self.meta_tags,
                meta_description=self.meta_description,
                template_name=self.template_name,
                render_template=self.render_template,
                json=self.json,
                date=self.date,
                last_author=self.author,
                modify_user=user  # the current user performing the change
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"


class SlugHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.ForeignKey(
        Slug,  # Reference the live slug
        on_delete=models.CASCADE,
        related_name="history_entries",
        null=True
    )
    parent = models.ForeignKey(
        Slug,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="history_children"
    )
    name = models.CharField(max_length=120)
    meta_tags = models.CharField(max_length=300)
    meta_description = models.CharField(max_length=150)
    template_name = models.CharField(max_length=300)
    render_template = models.TextField()
    json = models.TextField()
    date = models.DateTimeField()  # copy the creation timestamp of the Slug
    modify_date = models.DateTimeField(auto_now_add=True)  # timestamp of the history entry
    last_author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Last Author",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="slug_histories_as_last_author"
    )
    modify_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Modifier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="slug_histories_as_modifier"
    )

    class Meta:
        verbose_name_plural = "Slug Histories"

    def __str__(self):
        return f"History for Slug {self.slug.id} - {self.modify_date}"
