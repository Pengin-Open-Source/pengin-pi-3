# main/models/seo.py
from django.db import models

class RobotsRule(models.Model):
    user_agent = models.CharField(max_length=50, default="*")
    path = models.CharField(max_length=255, help_text="Path pattern e.g. /admin/ or /slug/edit/")
    allow = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Robots Rules"

    def __str__(self):
        action = "Allow" if self.allow else "Disallow"
        return f"{self.user_agent} -> {action}: {self.path}"