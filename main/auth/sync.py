# main/auth/sync.py
# Bridge between TeamUserRole assignments (what a staff user-manager UI
# actually edits) and the flat auth.Group membership that an app can read
# directly for its own gating (e.g. a forum thread's Group-based visibility)
# without querying TeamRole/TeamUserRole itself. Any app whose permission
# model still reads request.user.groups directly, rather than main.auth's
# TeamUserRole, needs every TeamUserRole assign/unassign to keep the
# underlying Group membership in sync by hand - that's what this does.
from .models import TeamRole, TeamUserRole


def sync_team_role_groups(user, previous_role_ids, current_role_ids):
    """
    Reconciles user.groups against a before/after diff of the TeamRole ids
    they're assigned to (pass the user's TeamUserRole.role_id set from
    immediately before and immediately after a save). Adds the Group for
    any newly-assigned role; removes the Group for a newly-unassigned role
    ONLY if no other current TeamUserRole of theirs still targets that same
    Group - never blindly strips a Group membership another team role
    still justifies.
    """
    previous_groups = set(TeamRole.objects.filter(id__in=previous_role_ids).values_list('group_id', flat=True))
    current_groups = set(TeamRole.objects.filter(id__in=current_role_ids).values_list('group_id', flat=True))

    for group_id in current_groups - previous_groups:
        user.groups.add(group_id)

    removed_groups = previous_groups - current_groups
    if removed_groups:
        still_justified = set(
            TeamUserRole.objects.filter(user=user, role__group_id__in=removed_groups)
            .values_list('role__group_id', flat=True)
        )
        for group_id in removed_groups - still_justified:
            user.groups.remove(group_id)
