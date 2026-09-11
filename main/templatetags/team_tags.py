# main/templatetags/team_tags.py
# Promoted here from tools/templatetags/team_tags.py alongside the rest of
# the staff console (main/views/staff.py) - a user's display title is core
# RBAC presentation, not tools-specific.
from django import template

from main.auth import display_title_for_user

register = template.Library()


@register.filter
def team_title(user):
    """Renders a user's display title (e.g. 'Engineering - Employee') for
    the staff user list table."""
    return display_title_for_user(user)
