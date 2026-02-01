from django.db import models
import uuid
from datetime import datetime, timezone


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
    date = models.DateTimeField(default=datetime.now(timezone.utc))
    creator = models.ForeignKey("users.User", verbose_name="Creator", on_delete=models.SET_NULL, null=True)


    class Meta:
        verbose_name_plural = "Slugs"


    def save(self, *args, user=None, **kwargs):
        if user:
            self.modify_user = user
        self.modify_date = datetime.now(timezone.utc)
        
        if self.pk and Slug.objects.filter(pk=self.pk).exists():
            SlugHistory.objects.create(
                slug_id=self.id,
                parent=self.parent,
                name=self.name,
                meta_tags=self.meta_tags,
                meta_description=self.meta_description,
                template_name=self.template_name,
                render_template=self.render_template,
                json=self.json,
                date=self.date,
                creator=self.creator,
                modify_date=self.modify_date,
                modify_user=self.modify_user
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"


class SlugHistory(models.Model):
    id = models.UUIDField()
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="history_children")
    name = models.CharField(max_length=120)
    meta_tags = models.CharField(max_length=300)
    meta_description = models.CharField(max_length=150)
    template_name = models.CharField(max_length=300)
    render_template = models.TextField()
    json = models.TextField()
    date = models.DateTimeField()
    creator = models.ForeignKey("users.User", verbose_name="Creator", on_delete=models.SET_NULL, null=True)
    modify_date = models.DateTimeField()
    

    class Meta:
        verbose_name_plural = "Slug Histories"


    def __str__(self):
        return f"History for {self.id} - {self.date}"
