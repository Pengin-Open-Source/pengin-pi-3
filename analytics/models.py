# analytics/models.py
from django.db import models
import uuid

class PageViewLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    path = models.CharField(max_length=500, db_index=True)
    ip_address = models.GenericIPAddressField(db_index=True)
    email_alias = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Page View Log'
        verbose_name_plural = 'Page View Logs'

    def __str__(self):
        user_str = self.email_alias or "Anonymous"
        return f"{self.path} | {user_str} ({self.ip_address}) @ {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"