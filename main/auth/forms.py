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
            # Every seeded department has an "Employee" title by
            # convention (see main/management/commands/seed_departments.py),
            # so this is a real default, not a guess.
            role = TeamRole.objects.get(group=team, name='Employee')
            cleaned_data['role'] = role
        if role and team and role.group_id != team.id:
            raise forms.ValidationError("Selected role doesn't belong to the selected team.")

        return cleaned_data


TeamRoleAssignmentFormSet = forms.inlineformset_factory(
    User, TeamUserRole, form=TeamRoleAssignmentForm, fk_name='user', extra=1, can_delete=True)
