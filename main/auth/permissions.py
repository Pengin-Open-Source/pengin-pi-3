# main/auth/permissions.py
# The central RBAC surface for the whole project. Any code needing "can
# this user do X" should import from here rather than rolling its own
# Group-membership check - see main/auth/models.py for the department/
# title model this implements (Group = department, TeamRole = title
# within a department, TeamUserRole = the join).
from django.contrib.auth.models import Group

from main.models.users import User
from .models import TeamRole, TeamUserRole

EXECUTIVES_DEPARTMENT_NAME = "Executives"


def is_root(user):
    """Real Django superuser - bypasses every check in this module. Not a
    stored TeamRole: "Administrator" is a display label for this, not
    something anyone picks from a role dropdown."""
    return bool(user) and user.is_authenticated and user.is_superuser


def is_executive_manager(user):
    """Holding any title in the Executives department grants Manager-tier
    authority across every OTHER department too - but never root. Root
    always satisfies this as well (it satisfies everything)."""
    if is_root(user):
        return True
    if not user or not user.is_authenticated:
        return False
    return TeamUserRole.objects.filter(
        user=user, role__group__name=EXECUTIVES_DEPARTMENT_NAME
    ).exists()


def is_manager_of_group(user, group):
    """Is this user Manager-tier authority for this specific department?
    True for root, for an Executive (any department), or for someone
    holding an is_manager_role=True title in this exact department."""
    if not group:
        return False
    if is_root(user) or is_executive_manager(user):
        return True
    if not user or not user.is_authenticated:
        return False
    return TeamUserRole.objects.filter(
        user=user, role__group=group, role__is_manager_role=True
    ).exists()


def get_managed_groups(user):
    """Every department this user has Manager-tier authority over."""
    if is_root(user) or is_executive_manager(user):
        return Group.objects.all()
    if not user or not user.is_authenticated:
        return Group.objects.none()
    role_ids = TeamUserRole.objects.filter(
        user=user, role__is_manager_role=True
    ).values_list('role__group_id', flat=True)
    return Group.objects.filter(id__in=role_ids)


def can_access_group(user, group):
    """Staff who are either Manager-tier for this department or a plain
    member of it (any title). Accepts a Group instance OR a group id."""
    if not user or not user.is_authenticated or not user.is_staff or not group:
        return False
    if is_manager_of_group(user, group):
        return True
    return TeamUserRole.objects.filter(user=user, role__group=group).exists()


def get_all_groups_for_user_with_extended_rbac(user):
    """Every department this user belongs to in any capacity (as a Group
    queryset) - root/Executive get every department."""
    if is_root(user) or is_executive_manager(user):
        return Group.objects.all()
    if not user or not user.is_authenticated:
        return Group.objects.none()
    role_ids = TeamUserRole.objects.filter(user=user).values_list('role__group_id', flat=True)
    return Group.objects.filter(id__in=role_ids)


def get_users_with_extended_rbac_to_group(department=None):
    """Staff eligible to own an item routed to `department` (or all
    eligible staff if department is None)."""
    queryset = User.objects.filter(is_staff=True, validated=True)
    if department is not None:
        queryset = queryset.filter(team_role_assignments__role__group=department)
    return queryset.distinct()


def display_title_for_user(user, department=None):
    """What to show for this user's title - "Administrator" always wins for
    a superuser regardless of what's actually stored (Administrator isn't a
    real TeamRole). Otherwise their real title in `department` if given, or
    their first title anywhere, or "Employee" if they hold none."""
    if is_root(user):
        return "Administrator"
    assignments = TeamUserRole.objects.filter(user=user)
    if department is not None:
        assignments = assignments.filter(role__group=department)
    first = assignments.select_related('role').first()
    return first.role.name if first else "Employee"
