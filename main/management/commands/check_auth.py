# main/management/commands/check_auth.py
# Diagnostic/test command for main/auth/ - reports everything the
# permissions framework knows about a given user. Useful both as a real
# debugging tool and as a template for writing further auth test commands.
#
# Usage: python manage.py check_auth someone@example.com
from django.core.management.base import BaseCommand, CommandError

from main.auth.models import TeamUserRole
from main.auth.permissions import (
    is_root,
    is_executive_manager,
    get_managed_groups,
    get_all_groups_for_user_with_extended_rbac,
    display_title_for_user,
)
from main.models.users import User


class Command(BaseCommand):
    help = "Reports what main/auth/'s permissions framework knows about a user, by email."

    def add_arguments(self, parser):
        parser.add_argument('email', type=str)

    def handle(self, *args, **options):
        email = options['email']
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(f"No user with email {email!r}")

        self.stdout.write(f"User: {user.name or user.email} <{user.email}>")
        self.stdout.write(f"  is_staff: {user.is_staff}")
        self.stdout.write(f"  is_superuser (root): {user.is_superuser}")
        self.stdout.write(f"  is_root(): {is_root(user)}")
        self.stdout.write(f"  is_executive_manager(): {is_executive_manager(user)}")
        self.stdout.write(f"  display_title_for_user(): {display_title_for_user(user)}")

        team_roles = TeamUserRole.objects.filter(user=user).select_related('role', 'role__group')
        if team_roles:
            self.stdout.write("  Team roles:")
            for tur in team_roles:
                self.stdout.write(f"    - {tur.role.name} @ {tur.role.group.name} (manager tier: {tur.role.is_manager_role})")
        else:
            self.stdout.write("  Team roles: none")

        managed = list(get_managed_groups(user).values_list('name', flat=True))
        self.stdout.write(f"  Manages departments: {managed or 'none'}")

        member_of = list(get_all_groups_for_user_with_extended_rbac(user).values_list('name', flat=True))
        self.stdout.write(f"  Member of departments (any capacity): {member_of or 'none'}")
