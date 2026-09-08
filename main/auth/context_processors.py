# main/auth/context_processors.py
# Home for auth/user-related template context. Register additions here in
# main/settings.py's TEMPLATES['OPTIONS']['context_processors'].
from .models import TeamUserRole
from .permissions import is_root, display_title_for_user


def auth_context(request):
    """Exposes the current user's department/title memberships to every
    template, so nav/profile UI can render role-aware content without each
    view having to compute it separately."""
    if not request.user.is_authenticated:
        return {'user_team_roles': [], 'user_display_title': None}

    team_roles = list(
        TeamUserRole.objects.filter(user=request.user).select_related('role', 'role__group')
    )
    return {
        'user_team_roles': team_roles,
        'user_display_title': "Administrator" if is_root(request.user) else display_title_for_user(request.user),
    }
