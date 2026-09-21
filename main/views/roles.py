# main/views/roles.py
# RBAC structure management: departments (auth.Group) and titles
# (TeamRole) - the org-chart definitions that main/views/staff.py's user
# manager lets someone ASSIGN to a user, but never lets anyone create,
# rename, or delete. Promoted alongside staff.py as the other half of the
# core RBAC console: staff.py manages WHO holds a title, this manages
# WHAT titles exist.
#
# Two permission tiers, both from main.auth.permissions:
#   - Departments are the top of the org chart, so only Executive-tier
#     staff (is_executive_manager - root, Tobu Pengin's Manager, or
#     Independent Contributor's Maintainer) can create, rename, or delete
#     one.
#   - Titles are scoped to one department, so anyone with Manager-tier
#     authority over THAT specific department (is_manager_of_group - root,
#     Executive-tier, or that department's own manager title) can create,
#     rename, or delete a title within it.
# Any staff member can view the page itself (StaffRequiredMixin, same as
# the user manager) - only the mutating actions are gated further, with a
# friendly message rather than a hard 403 if someone without authority
# submits one directly.
from django.contrib import messages
from django.contrib.auth.models import Group
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View

from main.auth import StaffRequiredMixin, TeamRole, is_executive_manager, is_manager_of_group
from main.auth.forms import DepartmentForm, TeamRoleForm


class StaffRoleListView(StaffRequiredMixin, View):
    def get(self, request):
        departments = list(Group.objects.prefetch_related('team_roles__assigned_users').order_by('name'))
        # Annotated per-department rather than computed in the template:
        # is_manager_of_group() is a real query, and Django templates can't
        # call a function with an argument from the loop variable.
        for department in departments:
            department.user_can_manage = is_manager_of_group(request.user, department)

        return render(request, 'staff/role_list.html', {
            'departments': departments,
            'can_manage_departments': is_executive_manager(request.user),
            'primary_title': 'Staff Tool - Roles & Departments',
        })


class StaffDepartmentCreateView(StaffRequiredMixin, View):
    def get(self, request):
        if not is_executive_manager(request.user):
            messages.error(request, "Only Executive-tier staff can create departments.")
            return redirect('staff_role_list')
        return render(request, 'staff/department_form.html', {
            'form': DepartmentForm(), 'primary_title': 'New Department',
        })

    def post(self, request):
        if not is_executive_manager(request.user):
            messages.error(request, "Only Executive-tier staff can create departments.")
            return redirect('staff_role_list')
        form = DepartmentForm(request.POST)
        if form.is_valid():
            department = form.save()
            messages.success(request, f"Created department {department.name}.")
            return redirect('staff_role_list')
        return render(request, 'staff/department_form.html', {
            'form': form, 'primary_title': 'New Department',
        })


class StaffDepartmentEditView(StaffRequiredMixin, View):
    def get(self, request, pk):
        if not is_executive_manager(request.user):
            messages.error(request, "Only Executive-tier staff can rename departments.")
            return redirect('staff_role_list')
        department = get_object_or_404(Group, pk=pk)
        return render(request, 'staff/department_form.html', {
            'form': DepartmentForm(instance=department), 'department': department,
            'primary_title': f'Edit Department: {department.name}',
        })

    def post(self, request, pk):
        if not is_executive_manager(request.user):
            messages.error(request, "Only Executive-tier staff can rename departments.")
            return redirect('staff_role_list')
        department = get_object_or_404(Group, pk=pk)
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated department {department.name}.")
            return redirect('staff_role_list')
        return render(request, 'staff/department_form.html', {
            'form': form, 'department': department, 'primary_title': f'Edit Department: {department.name}',
        })


class StaffDepartmentDeleteView(StaffRequiredMixin, View):
    def post(self, request, pk):
        if not is_executive_manager(request.user):
            messages.error(request, "Only Executive-tier staff can delete departments.")
            return redirect('staff_role_list')
        department = get_object_or_404(Group, pk=pk)
        name = department.name
        try:
            department.delete()
            messages.success(request, f"Deleted department {name}.")
        except Exception as e:
            messages.error(request, f"Couldn't delete {name}: {e}")
        return redirect('staff_role_list')


class StaffRoleCreateView(StaffRequiredMixin, View):
    def get(self, request, group_id):
        department = get_object_or_404(Group, pk=group_id)
        if not is_manager_of_group(request.user, department):
            messages.error(request, f"You don't have Manager-tier authority over {department.name}.")
            return redirect('staff_role_list')
        return render(request, 'staff/role_form.html', {
            'form': TeamRoleForm(), 'department': department, 'primary_title': f'New Title in {department.name}',
        })

    def post(self, request, group_id):
        department = get_object_or_404(Group, pk=group_id)
        if not is_manager_of_group(request.user, department):
            messages.error(request, f"You don't have Manager-tier authority over {department.name}.")
            return redirect('staff_role_list')
        form = TeamRoleForm(request.POST)
        if form.is_valid():
            role = form.save(commit=False)
            role.group = department
            role.save()
            messages.success(request, f"Created title {role.name} in {department.name}.")
            return redirect('staff_role_list')
        return render(request, 'staff/role_form.html', {
            'form': form, 'department': department, 'primary_title': f'New Title in {department.name}',
        })


class StaffRoleEditView(StaffRequiredMixin, View):
    def get(self, request, pk):
        role = get_object_or_404(TeamRole, pk=pk)
        if not is_manager_of_group(request.user, role.group):
            messages.error(request, f"You don't have Manager-tier authority over {role.group.name}.")
            return redirect('staff_role_list')
        return render(request, 'staff/role_form.html', {
            'form': TeamRoleForm(instance=role), 'department': role.group, 'role': role,
            'primary_title': f'Edit Title: {role.name}',
        })

    def post(self, request, pk):
        role = get_object_or_404(TeamRole, pk=pk)
        if not is_manager_of_group(request.user, role.group):
            messages.error(request, f"You don't have Manager-tier authority over {role.group.name}.")
            return redirect('staff_role_list')
        form = TeamRoleForm(request.POST, instance=role)
        if form.is_valid():
            # Always an edit here - get_object_or_404 only ever returns an
            # already-existing row, never a fresh one, so no _state.adding
            # guard is needed (see NOTE_HISTORY_FK_BUG.md).
            role.save_history(user=request.user)
            form.save()
            messages.success(request, f"Updated title {role.name}.")
            return redirect('staff_role_list')
        return render(request, 'staff/role_form.html', {
            'form': form, 'department': role.group, 'role': role, 'primary_title': f'Edit Title: {role.name}',
        })


class StaffRoleDeleteView(StaffRequiredMixin, View):
    def post(self, request, pk):
        role = get_object_or_404(TeamRole, pk=pk)
        if not is_manager_of_group(request.user, role.group):
            messages.error(request, f"You don't have Manager-tier authority over {role.group.name}.")
            return redirect('staff_role_list')
        name, group_name = role.name, role.group.name
        try:
            role.delete()
            messages.success(request, f"Deleted title {name} ({group_name}).")
        except Exception as e:
            messages.error(request, f"Couldn't delete {name}: {e}")
        return redirect('staff_role_list')
