# main/auth/mixins.py - class-based view auth guards.
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class LoginAndValidationRequiredMixin(LoginRequiredMixin):
    """Requires the user be logged in AND have a validated (verified) account."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not getattr(request.user, "validated", False):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Requires the user be logged in AND be staff (is_staff=True) - for any
    staff-only view."""

    def test_func(self):
        return self.request.user.is_staff
