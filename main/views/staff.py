# main/views/staff.py
# Core staff console: system-user management (create/edit/delete a User,
# assign team roles, trigger activation/reset emails). Promoted here from
# tools/views/users.py + tools/views/api.py - this is core RBAC
# administration built entirely on main.auth (StaffRequiredMixin,
# TeamUserRole, sync_team_role_groups, cascade_is_staff), with zero
# dependency on any example app, so every pp3 site gets it automatically
# rather than needing to fork a separate "tools" branch for it.
import secrets
import uuid
from datetime import timedelta

from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from django.utils import timezone

from django.contrib.auth.models import Group

from main.auth import StaffRequiredMixin, TeamUserRole, TeamRole, sync_team_role_groups, cascade_is_staff
from main.auth.forms import StaffUserForm, TeamRoleAssignmentFormSet
from main.models.users import User
from util.mail import send_mail

# No 0/O or 1/I - keeps a hand-typed OTP unambiguous.
OTP_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_otp(length=8):
    return ''.join(secrets.choice(OTP_ALPHABET) for _ in range(length))


def _send_activation_email(user):
    """Accounts staff create here start with set_unusable_password(), so
    they can't log in to use the normal validation-link flow. Send them a
    one-time password instead, which lets them set a password and validate
    in a single step (see main.views.auth.ActivateAccountView). A user who
    already has a real password - which only happens for self-signup,
    never a staff-created account - keeps getting the plain validation
    link, unchanged."""
    if user.has_usable_password():
        send_mail(user.email, str(user.validation_id), "user_validation")
        return

    otp = _generate_otp()
    user.otp_code = otp
    user.otp_expires_at = timezone.now() + timedelta(hours=24)
    user.save()
    send_mail(user.email, str(user.validation_id), "staff_account_otp", OTP=otp)


class StaffUserListView(StaffRequiredMixin, View):
    def get(self, request):
        query = request.GET.get('q', '').strip()
        sort_by = request.GET.get('sort', 'name')

        roles_prefetch = Prefetch(
            'team_role_assignments',
            queryset=TeamUserRole.objects.select_related('role', 'role__group'))

        users_qs = User.objects.prefetch_related(roles_prefetch)

        if query:
            users_qs = users_qs.filter(
                Q(email__icontains=query) |
                Q(name__icontains=query) |
                Q(team_role_assignments__role__name__icontains=query) |
                Q(team_role_assignments__role__group__name__icontains=query)
            ).distinct()

        valid_sorts = {
            'name': 'name',
            '-name': '-name',
            'email': 'email',
            '-email': '-email',
            'validated': '-validated',
            'staff': '-is_staff',
        }
        users_qs = users_qs.order_by(valid_sorts.get(sort_by, 'name'))

        paginator = Paginator(users_qs, 100)
        page_obj = paginator.get_page(request.GET.get('page'))

        return render(request, 'staff/user_list.html', {
            'page_obj': page_obj,
            'query': query,
            'sort_by': sort_by,
            'total_users': paginator.count,
            'pagination_extra_query': f'&sort={sort_by}',
            'primary_title': 'Staff Tool - System Users',
        })


class StaffUserCreateView(StaffRequiredMixin, View):
    def get(self, request):
        form = StaffUserForm()
        role_formset = TeamRoleAssignmentFormSet(instance=User())
        return render(request, 'staff/user_create.html', {
            'form': form, 'role_formset': role_formset, 'all_teams': Group.objects.order_by('name'),
            'primary_title': 'Create System User',
        })

    def post(self, request):
        form = StaffUserForm(request.POST)

        if form.is_valid():
            new_user = form.save(commit=False)
            new_user.set_unusable_password()
            new_user.validation_date = timezone.now()
            new_user.validation_id = uuid.uuid4()
            new_user.save()

            role_formset = TeamRoleAssignmentFormSet(request.POST, instance=new_user)
            if role_formset.is_valid():
                role_formset.save()
                current_role_ids = set(TeamUserRole.objects.filter(user=new_user).values_list('role_id', flat=True))
                sync_team_role_groups(new_user, previous_role_ids=set(), current_role_ids=current_role_ids)
                cascade_is_staff(new_user)

                try:
                    _send_activation_email(new_user)
                    messages.success(request, f"User {new_user.email} created and activation email sent.")
                except Exception as e:
                    messages.warning(request, f"User {new_user.email} created, but activation email failed: {str(e)}")

                return redirect('staff_user_edit', pk=new_user.id)
            else:
                new_user.delete()
                messages.error(request, "Error processing team role assignments.")
        else:
            role_formset = TeamRoleAssignmentFormSet(request.POST, instance=User())
            messages.error(request, "Please correct the errors below.")

        return render(request, 'staff/user_create.html', {
            'form': form, 'role_formset': role_formset, 'all_teams': Group.objects.order_by('name'),
            'primary_title': 'Create System User',
        })


class StaffUserSendValidationEmailView(StaffRequiredMixin, View):
    def post(self, request, pk):
        sys_user = get_object_or_404(User, pk=pk)

        if sys_user.validated:
            messages.info(request, f"Account {sys_user.email} is already validated.")
            return redirect('staff_user_edit', pk=sys_user.id)

        sys_user.validation_date = timezone.now()
        sys_user.validation_id = uuid.uuid4()
        sys_user.save()

        try:
            _send_activation_email(sys_user)
            messages.success(request, f"Activation email sent to {sys_user.email}.")
        except Exception as e:
            messages.error(request, f"Failed to send activation email: {str(e)}")

        return redirect('staff_user_edit', pk=sys_user.id)


class StaffUserEditView(StaffRequiredMixin, View):
    def get(self, request, pk):
        sys_user = get_object_or_404(User, pk=pk)
        form = StaffUserForm(instance=sys_user)
        role_formset = TeamRoleAssignmentFormSet(instance=sys_user)

        return render(request, 'staff/user_edit.html', {
            'sys_user': sys_user, 'form': form, 'role_formset': role_formset,
            'all_teams': Group.objects.order_by('name'), 'primary_title': f'Edit User: {sys_user.email}',
        })

    def post(self, request, pk):
        sys_user = get_object_or_404(User, pk=pk)
        form = StaffUserForm(request.POST, instance=sys_user)
        role_formset = TeamRoleAssignmentFormSet(request.POST, instance=sys_user)

        if form.is_valid() and role_formset.is_valid():
            previous_role_ids = set(TeamUserRole.objects.filter(user=sys_user).values_list('role_id', flat=True))
            sys_user.save_history(user=request.user)
            form.save()
            role_formset.save()
            current_role_ids = set(TeamUserRole.objects.filter(user=sys_user).values_list('role_id', flat=True))
            sync_team_role_groups(sys_user, previous_role_ids, current_role_ids)
            cascade_is_staff(sys_user)
            messages.success(request, f"Updated profile & roles for {sys_user.email}.")
            return redirect('staff_user_edit', pk=sys_user.id)
        else:
            messages.error(request, "Please correct the errors on the form below.")

        return render(request, 'staff/user_edit.html', {
            'sys_user': sys_user, 'form': form, 'role_formset': role_formset,
            'all_teams': Group.objects.order_by('name'), 'primary_title': f'Edit User: {sys_user.email}',
        })


class StaffUserSendResetPasswordView(StaffRequiredMixin, View):
    def post(self, request, pk):
        sys_user = get_object_or_404(User, pk=pk)
        sys_user.prt = uuid.uuid4()
        sys_user.prt_reset_date = timezone.now()
        sys_user.prt_consumption_date = None
        sys_user.save()

        try:
            send_mail(sys_user.email, str(sys_user.prt), "password_reset")
            messages.success(request, f"Password reset email sent to {sys_user.email}.")
        except Exception as e:
            messages.error(request, f"Failed to send email: {str(e)}")

        return redirect('staff_user_edit', pk=sys_user.id)


class StaffUserDeleteView(StaffRequiredMixin, View):
    def post(self, request, pk):
        sys_user = get_object_or_404(User, pk=pk)

        if sys_user == request.user:
            messages.error(request, "You can't delete your own account.")
            return redirect('staff_user_edit', pk=sys_user.id)

        email = sys_user.email
        try:
            sys_user.delete()
            messages.success(request, f"Deleted user {email}.")
        except Exception as e:
            messages.error(
                request,
                f"Couldn't delete {email}: they're still referenced elsewhere and would need to "
                f"be reassigned first. ({e})"
            )
            return redirect('staff_user_edit', pk=sys_user.id)

        return redirect('staff_user_list')


class StaffTeamRolesApiView(StaffRequiredMixin, View):
    """Backs the team->role cascading dropdown in the role-assignment
    formset (see templates/staff/_user_form_fields.html's fetch() call)."""
    def get(self, request, team_id):
        roles = TeamRole.objects.filter(group_id=team_id).order_by('name').values('id', 'name')
        return JsonResponse({'roles': list(roles)})
