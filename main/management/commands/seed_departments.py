# main/management/commands/seed_departments.py
# Example manage.py command exercising main/auth/ - seeds a starter set of
# departments (Group) and standard titles (TeamRole). This is placeholder/
# example content: rename or replace the DEPARTMENTS/STANDARD_TITLES lists
# for your own project, or write your own command modeled on this one.
#
# Usage: python manage.py seed_departments
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from main.auth.models import TeamRole

DEPARTMENTS = ["Sales", "Support", "Engineering", "Executives"]
STANDARD_TITLES = ["Employee", "Manager"]


class Command(BaseCommand):
    help = "Seeds example departments (Group) and standard titles (TeamRole) for main/auth/."

    def handle(self, *args, **options):
        for name in DEPARTMENTS:
            group, created = Group.objects.get_or_create(name=name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created department: {name}"))
            else:
                self.stdout.write(f"Department already exists: {name}")

            for title in STANDARD_TITLES:
                role, role_created = TeamRole.objects.get_or_create(
                    group=group, name=title, defaults={'is_manager_role': title == 'Manager'})
                if role_created:
                    self.stdout.write(self.style.SUCCESS(f"  Created title: {title} ({name})"))

        self.stdout.write(self.style.SUCCESS("Done."))
