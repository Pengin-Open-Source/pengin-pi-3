# main/auth/models.py
# The central RBAC model for the whole project: Group = department (Sales,
# Engineering, Executives, etc. - seed your own via
# `manage.py seed_departments`), TeamRole = a title/position within one
# department (Volunteer, Manager, ...), TeamUserRole = the user<->title
# join. "Administrator" is deliberately NOT a TeamRole - it means
# User.is_superuser (real Django root) - see main/auth/permissions.py for
# that, and for the two named departments that carry site-wide authority
# instead of being scoped to their own roster. Registered under the 'main' app (via main/models/__init__.py)
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

    is_forum_moderator_role = models.BooleanField(
        default=False,
        help_text="Forum-moderator title for this department - grants CRUD-on-posts and "
                   "ban authority over this department's own forum thread (or, for the two "
                   "site-wide departments, every forum thread on the site). Independent of "
                   "is_manager_role - moderating a forum and managing a department's roster "
                   "are separate authorities that don't have to be held by the same title. "
                   "See main/auth/permissions.py.")

    is_blog_author_role = models.BooleanField(
        default=False,
        help_text="Blogger title - grants CRUD authority over every blog post on the site "
                   "(there's only one Blogs app, not one per department, so this flag isn't "
                   "scoped to a specific department the way is_forum_moderator_role is). "
                   "See main/auth/permissions.py.")

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
