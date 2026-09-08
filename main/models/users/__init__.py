from django.db import models
import uuid
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
    Group,
    Permission
)

from main.models.mixins import HistoryMixin, AbstractHistory


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(HistoryMixin, AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    image = models.CharField(max_length=255, blank=True, null=True)
    
    validated = models.BooleanField(default=False)
    validation_date = models.DateTimeField(default=timezone.now)
    validation_id = models.UUIDField(default=uuid.uuid4, unique=True)
    prt = models.UUIDField(default=uuid.uuid4, unique=True)
    prt_reset_date = models.DateTimeField(null=True, blank=True)
    prt_consumption_date = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        app_label = 'main'

    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        related_name='%(app_label)s_%(class)s_groups',
        related_query_name="user",
        help_text=(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
    )

    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        related_name='%(app_label)s_%(class)s_user_permissions',
        related_query_name="user",
        help_text='Specific permissions for this user.',
    )

    def __str__(self):
        return str(self.email)


class UserHistory(AbstractHistory):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    object = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="history")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta(AbstractHistory.Meta):
        app_label = 'main'
        verbose_name_plural = "User Histories"

    def __str__(self):
        return f"User {self.object_id} @ {self.changed_at}"