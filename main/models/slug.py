from django.db import models
import uuid
from datetime import datetime

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
    content = models.TextField()
    date = models.DateField(default=datetime.now(datetime.timezone.utc))
    creator = models.ForeignKey("users.User", verbose_name="Creator", on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name_plural = "Slugs"

    def save(self, *args, **kwargs):
        # Check if the record exists to determine if this is an update operation
        if self.pk and Slug.objects.filter(pk=self.pk).exists():
            # Copy the current state to SlugHistory before updating
            SlugHistory.objects.create(
                slug_id=self.id,
                parent=self.parent,
                name=self.name,
                meta_tags=self.meta_tags,
                meta_description=self.meta_description,
                content=self.content,
                date=self.date,
                creator=self.creator,
                date=self.date
            )
        # Proceed with the save (create or update)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"


class SlugHistory(models.Model):
    # Reference to the original Slug
    id = models.UUIDField()
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="history_children")
    name = models.CharField(max_length=120)
    meta_tags = models.CharField(max_length=300)
    meta_description = models.CharField(max_length=150)
    content = models.TextField()
    date = models.DateField()
    creator = models.ForeignKey("users.User", verbose_name="Creator", on_delete=models.SET_NULL, null=True)
    date = models.DateTimeField()  # Timestamp of when this version was created in the history

    class Meta:
        verbose_name_plural = "Slug Histories"

    def __str__(self):
        return f"History for {self.id} - {self.date}"
