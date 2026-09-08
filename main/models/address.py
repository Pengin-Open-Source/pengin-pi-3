from django.db import models
import uuid
from django.conf import settings
from django.utils import timezone





class Address(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    address1 = models.CharField(max_length=50)
    address2 = models.CharField(max_length=50, null=True, blank=True)
    city = models.CharField(max_length=50)
    zipcode = models.CharField(max_length=20)
    state = models.CharField(max_length=50)
    country = models.CharField(max_length=50)
    date = models.DateTimeField(auto_now_add=True)      # creation timestamp
    modify_date = models.DateTimeField(auto_now=True)   # auto-updated on save
    modify_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name_plural = "Addresses"

    def save(self, *args, user=None, **kwargs):
        if user:
            self.modify_user = user

        # Save history if updating
        if self.pk and Address.objects.filter(pk=self.pk).exists():
            AddressHistory.objects.create(
                address_id=self.id,
                address1=self.address1,
                address2=self.address2,
                city=self.city,
                zipcode=self.zipcode,
                state=self.state,
                country=self.country,
                date=self.date,
                modify_date=self.modify_date,
                modify_user=self.modify_user
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.address1}, {self.city}, {self.state}, {self.country}"


class AddressHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    address = models.ForeignKey(
        Address,  # Reference the live slug
        on_delete=models.CASCADE,
        related_name="history_address",
        null=True
    )  # Track the UUID of the parent Address
    address1 = models.CharField(max_length=50)
    address2 = models.CharField(max_length=50, null=True, blank=True)
    city = models.CharField(max_length=50)
    zipcode = models.CharField(max_length=20)
    state = models.CharField(max_length=50)
    country = models.CharField(max_length=50)
    date = models.DateTimeField(default=timezone.now)  # Original creation date of Address
    modify_date = models.DateTimeField(auto_now=True)  # Modification date for the historical entry
    modify_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name_plural = "Address Histories"

    def __str__(self):
        return f"History for Address ID {self.address_id} - Modified by {self.modify_user} on {self.modify_date}"