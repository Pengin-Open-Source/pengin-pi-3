# main/auth/ - the project's central RBAC framework. Every other module's
# permission/group/user logic lives here, not scattered across apps or
# util/ (util is generic infrastructure - it stays auth-free by
# convention; see main/auth/decorators.py and main/auth/principals.py for
# what moved here from util/security/).
#
# Layout:
#   models.py             - TeamRole/TeamUserRole (Group = department, TeamRole = title)
#   permissions.py         - is_root/is_executive_manager/is_manager_of_group/etc.
#   mixins.py               - class-based view guards (LoginAndValidationRequiredMixin, StaffRequiredMixin)
#   decorators.py           - function-based view guards (is_admin_required, group_required, ...)
#   principals.py            - small Need/RoleNeed/ItemNeed ACL toolkit
#   context_processors.py    - template context (auth_context)
#   admin.py                  - Django admin registrations
#
# Registered under the 'main' app (see main/models/__init__.py) - there is
# no separate 'auth' Django app, and no separate migrations directory;
# TeamRole/TeamUserRole migrations live in main/migrations/ alongside
# Slug/User.
from .models import TeamRole, TeamRoleHistory, TeamUserRole, TeamUserRoleHistory
from .permissions import (
    is_root,
    is_executive_manager,
    is_manager_of_group,
    get_managed_groups,
    can_access_group,
    get_all_groups_for_user_with_extended_rbac,
    get_users_with_extended_rbac_to_group,
    display_title_for_user,
)
from .mixins import LoginAndValidationRequiredMixin, StaffRequiredMixin
from .decorators import group_required, is_admin_provider, is_admin_required, user_group_provider
from .principals import Need, UserNeed, RoleNeed, TypeNeed, ActionNeed, ItemNeed, PermissionDenied

__all__ = [
    'TeamRole', 'TeamRoleHistory', 'TeamUserRole', 'TeamUserRoleHistory',
    'is_root', 'is_executive_manager', 'is_manager_of_group', 'get_managed_groups',
    'can_access_group', 'get_all_groups_for_user_with_extended_rbac',
    'get_users_with_extended_rbac_to_group', 'display_title_for_user',
    'LoginAndValidationRequiredMixin', 'StaffRequiredMixin',
    'group_required', 'is_admin_provider', 'is_admin_required', 'user_group_provider',
    'Need', 'UserNeed', 'RoleNeed', 'TypeNeed', 'ActionNeed', 'ItemNeed', 'PermissionDenied',
]
