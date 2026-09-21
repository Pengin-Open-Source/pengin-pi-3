# main/views/team.py
# Manager self-service delegation - unlike main/views/roles.py (which
# creates/edits/deletes the departments and titles THEMSELVES, gated to
# Executive-tier) or main/views/staff.py's full console (now restricted
# to Executive-tier too), this lets an ordinary department Manager
# add/remove members and assign titles WITHIN their own department(s),
# no approval workflow - Stuart's call: "just allow them to add and
# remove members and assign permissions for their own groups."
#
# Deliberately exposes ONLY TeamUserRole membership - no account-level
# fields (email/is_active/is_staff/validated). A Manager can promote a
# peer to their own tier ("equal") or any lesser title in a department
# they manage, but can never touch a department outside
# main.auth.get_managed_groups(user), and can't create a brand-new
# system user (that stays in the full console) - only attach an
# EXISTING user, found by email, to their team.
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View

from main.auth import (
    get_managed_groups, is_executive_manager, TeamRole, TeamUserRole,
    sync_team_role_groups, cascade_is_staff,
)
from main.models.users import User


class MyTeamView(LoginRequiredMixin, View):
    def get(self, request):
        managed_groups = get_managed_groups(request.user).order_by('name')
        if not managed_groups.exists():
            messages.info(request, "You don't manage any department.")
            # staff_user_list is Executive-tier-only now - redirecting a
            # non-Executive staff member there would just 403 them.
            return redirect('staff_user_list' if is_executive_manager(request.user) else 'profile')

        departments = []
        for group in managed_groups:
            members = (
                TeamUserRole.objects.filter(role__group=group)
                .select_related('user', 'role').order_by('user__email')
            )
            titles = TeamRole.objects.filter(group=group).order_by('name')
            departments.append({'group': group, 'members': members, 'titles': titles})

        return render(request, 'staff/my_team.html', {
            'departments': departments,
            'primary_title': 'My Team',
        })

    def post(self, request):
        managed_groups = get_managed_groups(request.user)
        group = managed_groups.filter(id=request.POST.get('group_id')).first()
        if not group:
            messages.error(request, "You don't manage that department.")
            return redirect('my_team')

        role = TeamRole.objects.filter(id=request.POST.get('role_id'), group=group).first()
        if not role:
            messages.error(request, "Choose a valid title for that department.")
            return redirect('my_team')

        email = request.POST.get('email', '').strip().lower()
        target = User.objects.filter(email__iexact=email).first()
        if not target:
            messages.error(request, f"No existing user found with email {email}.")
            return redirect('my_team')

        previous_role_ids = set(TeamUserRole.objects.filter(user=target).values_list('role_id', flat=True))
        _, created = TeamUserRole.objects.get_or_create(user=target, role=role)
        if not created:
            messages.info(request, f"{target.email} already holds {role.name} in {group.name}.")
        else:
            current_role_ids = previous_role_ids | {role.id}
            sync_team_role_groups(target, previous_role_ids, current_role_ids)
            cascade_is_staff(target)
            messages.success(request, f"Added {target.email} as {role.name} in {group.name}.")
        return redirect('my_team')


class MyTeamRemoveView(LoginRequiredMixin, View):
    def post(self, request, pk):
        assignment = get_object_or_404(TeamUserRole, pk=pk)
        managed_groups = get_managed_groups(request.user)
        if not managed_groups.filter(id=assignment.role.group_id).exists():
            messages.error(request, "You don't manage that department.")
            return redirect('my_team')

        target = assignment.user
        group = assignment.role.group
        previous_role_ids = set(TeamUserRole.objects.filter(user=target).values_list('role_id', flat=True))
        assignment.delete()
        current_role_ids = previous_role_ids - {assignment.role_id}
        sync_team_role_groups(target, previous_role_ids, current_role_ids)
        messages.success(request, f"Removed {target.email} from {group.name}.")
        return redirect('my_team')
