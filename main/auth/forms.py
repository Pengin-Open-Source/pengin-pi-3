# main/auth/forms.py
# The canonical UI form for assigning a TeamRole to a User - promoted here
# from tools/forms.py because it's the standard way of editing main.auth's
# own TeamUserRole join table, not something specific to a "tools" staff
# console. Any future admin surface (or a rebuilt tools app) that needs to
# let someone assign departmental roles to a user reuses this instead of
# re-deriving its own version.
from django import forms
from django.contrib.auth.models import Group

from main.models.users import User
from .models import TeamRole, TeamUserRole


class TeamRoleAssignmentForm(forms.ModelForm):
    """One row of a role-assignment formset: pick a team (auth.Group), then
    a TeamRole scoped to that team."""
    team = forms.ModelChoiceField(
        queryset=Group.objects.all(), required=False,
        widget=forms.Select(attrs={'class': 'form-select team-select'}),
        empty_label="-- Select Team --")

    class Meta:
        model = TeamUserRole
        fields = ['team', 'role']
        widgets = {'role': forms.Select(attrs={'class': 'form-select role-select'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].required = False

        assigned_role = None
        if self.instance and self.instance.pk:
            assigned_role = getattr(self.instance, 'role', None)

        if assigned_role:
            self.fields['team'].initial = assigned_role.group
            self.fields['role'].queryset = TeamRole.objects.filter(group=assigned_role.group)
        else:
            self.fields['role'].queryset = TeamRole.objects.none()

        team_id = None
        if self.is_bound:
            team_id = self.data.get(self.add_prefix('team'))
        if team_id:
            try:
                self.fields['role'].queryset = TeamRole.objects.filter(group_id=team_id)
            except (ValueError, TypeError):
                pass

    def clean(self):
        cleaned_data = super().clean()
        team = cleaned_data.get('team')
        role = cleaned_data.get('role')

        if team and not role:
            # Every seeded department has a "Volunteer" title by
            # convention (see main/management/commands/seed_departments.py),
            # so this is a real default, not a guess. Staff here are
            # volunteers, not employees - see main/auth/permissions.py's
            # display_title_for_user() docstring.
            role = TeamRole.objects.get(group=team, name='Volunteer')
            cleaned_data['role'] = role
        if role and team and role.group_id != team.id:
            raise forms.ValidationError("Selected role doesn't belong to the selected team.")

        return cleaned_data


TeamRoleAssignmentFormSet = forms.inlineformset_factory(
    User, TeamUserRole, form=TeamRoleAssignmentForm, fk_name='user', extra=1, can_delete=True)


class StaffUserForm(forms.ModelForm):
    """"Edit a user's admin flags" UI for the core staff console
    (main/views/staff.py) - promoted here from tools/forms.py alongside
    TeamRoleAssignmentForm/FormSet, for the same reason: managing system
    users is core RBAC administration, not something specific to a
    "tools" app that a site might not install."""
    class Meta:
        model = User
        fields = ['email', 'name', 'validated', 'is_staff', 'is_active']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'validated': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DepartmentForm(forms.ModelForm):
    """Create/rename a department (auth.Group) - the top level of the org
    chart TeamRole titles are scoped under. Used by main/views/roles.py,
    gated there to Executive-tier staff only (main.auth.is_executive_manager)
    since a department is structural, not day-to-day membership."""
    class Meta:
        model = Group
        fields = ['name']
        widgets = {'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Engineering'})}


class TeamRoleForm(forms.ModelForm):
    """Create/rename a title (TeamRole) within one department - the
    `group` itself is set by the view from the URL, not exposed as a
    field here, since a title's department never changes after creation
    (renaming it into a different department would silently reassign
    everyone who holds it). Used by main/views/roles.py, gated there to
    Manager-tier staff for that specific department
    (main.auth.is_manager_of_group)."""
    class Meta:
        model = TeamRole
        fields = ['name', 'description', 'is_manager_role', 'is_forum_moderator_role', 'is_blog_author_role']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "e.g. Volunteer"}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_manager_role': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_forum_moderator_role': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_blog_author_role': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
