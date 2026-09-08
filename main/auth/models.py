# main/auth/models.py
# The central RBAC model for the whole project: Group = department (Sales,
# Engineering, Executives, etc. - seed your own via
# `manage.py seed_departments`), TeamRole = a title/position within one
# department (Employee, Manager, ...), TeamUserRole = the user<->title
# join. "Administrator" is deliberately NOT a TeamRole - it means
# User.is_superuser (real Django root) - and an "Executives" department is
# a cross-department evaluator, not root - see main/auth/permissions.py
# for both. Registered under the 'main' app (via main/models/__init__.py)
# so migrations live in main/migrations/ - there's no separate app here.
import uuid
from django.db import models
from django.conf import settings
from django.contrib.auth.models import Group
from main.models.mixins import HistoryMixin, AbstractHistory


class TeamRole(HistoryMixin, models.Model):
    """A named title scoped to one department (Group) - e.g. "Manager" in
    Sales is a different TeamRole than "Manager" in Engineering."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="team_roles",
        help_text="The department (Group) this title belongs to."
    )
    name = models.CharField(max_length=100, help_text="Title, e.g. 'Manager'.")
    description = models.TextField(blank=True)

    is_manager_role = models.BooleanField(
        default=False,
        help_text="Manager-tier title for this department - grants department-wide "
                   "authority to anyone holding it. See main/auth/permissions.py.")

    class Meta:
        verbose_name = "Team Role"
        verbose_name_plural = "Team Roles"
        unique_together = ('group', 'name')
        ordering = ['group', 'name']

    def __str__(self):
        return f"{self.name} ({self.group.name})"


class TeamRoleHistory(AbstractHistory):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    object = models.ForeignKey(TeamRole, on_delete=models.CASCADE, related_name="history")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta(AbstractHistory.Meta):
        verbose_name_plural = "Team Role Histories"

    def __str__(self):
        return f"TeamRole {self.object_id} @ {self.changed_at}"


class TeamUserRole(HistoryMixin, models.Model):
    """Binds a User to a TeamRole. The user inherits that title's authority
    for that specific department only."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="team_role_assignments")
    role = models.ForeignKey(TeamRole, on_delete=models.CASCADE, related_name="assigned_users")
    date_assigned = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Team User Role Assignment"
        verbose_name_plural = "Team User Role Assignments"
        unique_together = ('user', 'role')

    def __str__(self):
        return f"{self.user} -> {self.role.name} @ {self.role.group.name}"


class TeamUserRoleHistory(AbstractHistory):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    object = models.ForeignKey(TeamUserRole, on_delete=models.CASCADE, related_name="history")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta(AbstractHistory.Meta):
        verbose_name_plural = "Team User Role Assignment Histories"

    def __str__(self):
        return f"TeamUserRole {self.object_id} @ {self.changed_at}"
