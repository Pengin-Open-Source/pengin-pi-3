from django.db import models
import uuid
from datetime import datetime, timezone


class Address(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    address1 = models.CharField(max_length=50)
    address2 = models.CharField(max_length=50, null=True, blank=True)
    city = models.CharField(max_length=50)
    zipcode = models.CharField(max_length=20)
    state = models.CharField(max_length=50)
    country = models.CharField(max_length=50)
    date = models.DateTimeField(default=datetime.now(timezone.utc))  # Original creation date
    modify_date = models.DateTimeField(default=datetime.now(timezone.utc))  # Last modification date
    modify_user = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name_plural = "Addresses"

    def save(self, *args, user=None, **kwargs):
        # Update modification date and user if provided
        if user:
            self.modify_user = user
        self.modify_date = datetime.now(timezone.utc)

        # Check if the record exists in the database (indicating an update)
        if self.pk and Address.objects.filter(pk=self.pk).exists():
            # Copy current state to AddressHistory before updating
            AddressHistory.objects.create(
                address_id=self.id,
                address1=self.address1,
                address2=self.address2,
                city=self.city,
                zipcode=self.zipcode,
                state=self.state,
                country=self.country,
                date=self.date,  # Keep the previous date
                modify_date=self.modify_date,  # Record modification timestamp
                modify_user=self.modify_user  # Record modifying user
            )
        # Proceed with saving (create or update)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.address1}, {self.city}, {self.state}, {self.country}"


class AddressHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    address_id = models.UUIDField()  # Track the UUID of the parent Address
    address1 = models.CharField(max_length=50)
    address2 = models.CharField(max_length=50, null=True, blank=True)
    city = models.CharField(max_length=50)
    zipcode = models.CharField(max_length=20)
    state = models.CharField(max_length=50)
    country = models.CharField(max_length=50)
    date = models.DateTimeField()  # Original creation date of Address
    modify_date = models.DateTimeField()  # Modification date for the historical entry
    modify_user = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name_plural = "Address Histories"

    def __str__(self):
        return f"History for Address ID {self.address_id} - Modified by {self.modify_user} on {self.modify_date}"