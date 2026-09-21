# main/auth/permissions.py
# The central RBAC surface for the whole project. Any code needing "can
# this user do X" should import from here rather than rolling its own
# Group-membership check - see main/auth/models.py for the department/
# title model this implements (Group = department, TeamRole = title
# within a department, TeamUserRole = the join).
#
# Two named departments carry site-wide authority instead of being scoped
# to just their own roster (see is_executive_manager/is_manager_of_group
# below) - deliberately matched by NAME rather than a generic "scope"
# flag, since there are exactly two of them and they're asymmetric with
# each other in a way a single boolean couldn't express:
#   - Tobu Pengin, L.L.C.'s Manager title is the site-wide boss: full
#     authority over every department, including Tobu Pengin's own
#     roster.
#   - Independent Contributor - Volunteer's Maintainer title manages
#     every OTHER department (itself plus every app department) but
#     never Tobu Pengin, L.L.C.'s own roster - that's the company itself,
#     one level above the volunteer community.
# This can't be done with a plain Django Group permission either: a
# permission assigned to the Tobu Pengin Group would apply to every
# member of it equally (its 6 Interns included), when only whoever holds
# the specific Manager TITLE within that Group should get the authority -
# a distinction that only exists in TeamRole/TeamUserRole, not in
# Group membership itself.
from django.contrib.auth.models import Group

from main.models.users import User
from .models import TeamRole, TeamUserRole

TOBU_PENGIN_DEPARTMENT_NAME = "Tobu Pengin, L.L.C."
INDEPENDENT_CONTRIBUTOR_DEPARTMENT_NAME = "Independent Contributor - Volunteer"


def is_root(user):
    """Real Django superuser - bypasses every check in this module. Not a
    stored TeamRole: "admin" is a display label for this, not something
    anyone picks from a role dropdown."""
    return bool(user) and user.is_authenticated and user.is_superuser


def _has_manager_role_in_department(user, department_name):
    if not user or not user.is_authenticated:
        return False
    return TeamUserRole.objects.filter(
        user=user, role__group__name=department_name, role__is_manager_role=True
    ).exists()


def is_tobu_pengin_manager(user):
    """Holds Tobu Pengin, L.L.C.'s own Manager title - the site-wide boss."""
    return _has_manager_role_in_department(user, TOBU_PENGIN_DEPARTMENT_NAME)


def is_independent_contributor_maintainer(user):
    """Holds Independent Contributor - Volunteer's Maintainer title -
    manages every department except Tobu Pengin, L.L.C.'s own roster."""
    return _has_manager_role_in_department(user, INDEPENDENT_CONTRIBUTOR_DEPARTMENT_NAME)


def is_executive_manager(user):
    """Blanket "manages basically everything" check - root, Tobu Pengin's
    Manager, or Independent Contributor's Maintainer. Safe to use as a
    plain yes/no bypass anywhere (can_change_event, can_access_group,
    get_all_groups_for_user_with_extended_rbac) - the one place the two
    site-wide titles actually differ (Independent Contributor never
    manages Tobu Pengin, L.L.C.'s own roster) is handled specifically in
    is_manager_of_group/get_managed_groups below, not here."""
    if is_root(user):
        return True
    return is_tobu_pengin_manager(user) or is_independent_contributor_maintainer(user)


def is_manager_of_group(user, group):
    """Is this user Manager-tier authority for this specific department?
    True for root, for Tobu Pengin's Manager (every department), for
    Independent Contributor's Maintainer (every department except Tobu
    Pengin, L.L.C.'s own), or for someone holding an is_manager_role=True
    title in this exact department."""
    if not group:
        return False
    if is_root(user) or is_tobu_pengin_manager(user):
        return True
    if is_independent_contributor_maintainer(user) and group.name != TOBU_PENGIN_DEPARTMENT_NAME:
        return True
    if not user or not user.is_authenticated:
        return False
    return TeamUserRole.objects.filter(
        user=user, role__group=group, role__is_manager_role=True
    ).exists()


def get_managed_groups(user):
    """Every department this user has Manager-tier authority over."""
    if is_root(user) or is_tobu_pengin_manager(user):
        return Group.objects.all()
    if is_independent_contributor_maintainer(user):
        return Group.objects.exclude(name=TOBU_PENGIN_DEPARTMENT_NAME)
    if not user or not user.is_authenticated:
        return Group.objects.none()
    role_ids = TeamUserRole.objects.filter(
        user=user, role__is_manager_role=True
    ).values_list('role__group_id', flat=True)
    return Group.objects.filter(id__in=role_ids)


def is_sitewide_forum_moderator(user):
    """Root, or holds a forum-moderator title in either site-wide
    department (Tobu Pengin, L.L.C. or Independent Contributor -
    Volunteer) - both moderate every forum thread on the site equally.
    Unlike is_manager_of_group's Tobu-Pengin-vs-Independent-Contributor
    asymmetry, forum moderation scope has no such exception - it's the
    roster-management authority that Independent Contributor never gets
    over Tobu Pengin, not moderation."""
    if is_root(user):
        return True
    if not user or not user.is_authenticated:
        return False
    return TeamUserRole.objects.filter(
        user=user, role__is_forum_moderator_role=True,
        role__group__name__in=[TOBU_PENGIN_DEPARTMENT_NAME, INDEPENDENT_CONTRIBUTOR_DEPARTMENT_NAME],
    ).exists()


def can_moderate_forum(user, thread):
    """Can moderate this forum thread (CRUD posts/comments, ban users):
    root, a site-wide forum moderator, or holds the is_forum_moderator_role
    title of the specific department this thread is scoped to
    (Thread.moderating_department - see forums/models.py)."""
    if is_sitewide_forum_moderator(user):
        return True
    department = getattr(thread, 'moderating_department', None) if thread else None
    if not department or not user or not user.is_authenticated:
        return False
    return TeamUserRole.objects.filter(
        user=user, role__group=department, role__is_forum_moderator_role=True
    ).exists()


def can_manage_blog(user):
    """Root, or holds a Blogger title (TeamRole.is_blog_author_role) in
    any department - today that's only Tobu Pengin, L.L.C. and
    Independent Contributor - Volunteer's own Blogger titles, per
    Stuart's call that the Blogger title itself is the permission gate
    for blog CRUD, but this deliberately checks the flag rather than
    hardcoding those two department names - a Blogger title added to any
    future department would grant the same authority with no code
    change, unlike the two site-wide departments above which really are
    fixed, named entities."""
    if is_root(user):
        return True
    if not user or not user.is_authenticated:
        return False
    return TeamUserRole.objects.filter(user=user, role__is_blog_author_role=True).exists()


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
    """What to show for this user's title - "admin" always wins for a
    superuser regardless of what's actually stored ("admin" isn't a real
    TeamRole). Otherwise their real title in `department` if given, or
    their first title anywhere, or "user" if they hold none.

    Deliberately never says "Employee" anywhere in this function: staff
    here are volunteers, not employees, and a validated non-staff user
    with no TeamRole is just a regular "user" - "Employee" would be an
    inaccurate (and legally risky) description of either."""
    if is_root(user):
        return "admin"
    assignments = TeamUserRole.objects.filter(user=user)
    if department is not None:
        assignments = assignments.filter(role__group=department)
    first = assignments.select_related('role').first()
    return first.role.name if first else "user"
