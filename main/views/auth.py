import os
import uuid
from datetime import timedelta
from django.shortcuts import redirect, render
from django.views import View
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.urls import reverse

from main.models.users import User
from main.forms.auth import (
    LoginForm, SignUpForm, PasswordResetForm, 
    SetPasswordForm, EditPasswordForm
)
from util.security.ratelimit import RateLimitedPostMixin, RateLimitedGetMixin
from util.security.recaptcha import RecaptchaRequiredMixin
from util.mail import send_mail


def generate_uuid():
    return str(uuid.uuid4())


class ValidateView(View):
    def get(self, request, token):
        target_user = User.objects.filter(validation_id=token).first()

        if not target_user:
            messages.error(request, "This validation link is invalid or has already been used.")
            return redirect('login')

        if not request.user.is_authenticated:
            messages.info(request, f"Please log in as {target_user.email} to validate your account.")
            login_url = reverse('login')
            next_path = request.path
            return redirect(f"{login_url}?next={next_path}")

        if request.user != target_user:
            messages.error(
                request,
                f"You are logged in as {request.user.email}, but this validation "
                f"link belongs to {target_user.email}. Please log in with the correct account."
            )
            return redirect('profile')

        target_user.save_history(user=target_user)
        target_user.validated = True
        target_user.validation_id = uuid.uuid4()
        target_user.save()

        messages.success(request, "Your account has been successfully validated!")
        return redirect('profile')


class SendEmailView(LoginRequiredMixin, View):
    def get(self, request):
        now = timezone.now()
        user = request.user
        delta = user.validation_date + timedelta(minutes=5)
        
        if not user.validated and now > delta:
            user.validation_date = now
            user.validation_id = uuid.uuid4()
            user.save()
            
            send_mail(user.email, str(user.validation_id), "user_validation")
            messages.info(request, "Validation email sent! Please check your inbox.")
        else:
            messages.warning(request, "Please wait at least 5 minutes before requesting another email.")
            
        return redirect('profile')


class LoginView(RateLimitedPostMixin, RateLimitedGetMixin, RecaptchaRequiredMixin, View):
    ratelimit_rate = '5/m'

    def get(self, request):
        form = LoginForm()
        return render(
            request,
            'authentication/login.html',
            {
                'form': form, 
                'primary_title': 'Login', 
                'site_key': os.getenv("RECAPTCHA_SITE_KEY")
            }
        )

    def post(self, request):
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            next_url = request.POST.get('next') or request.GET.get('next')
            return redirect(next_url or 'home_view')

        messages.error(request, 'Please check your login details and try again.')
        return render(request, 'authentication/login.html', {
            'form': form, 
            'primary_title': 'Login',
            'site_key': os.getenv("RECAPTCHA_SITE_KEY")
        })


class SignupView(RateLimitedPostMixin, RateLimitedGetMixin, RecaptchaRequiredMixin, View):
    ratelimit_rate = '2/m'

    def get(self, request):
        form = SignUpForm()
        return render(
            request, 
            'authentication/signup.html', 
            {
                'form': form, 
                'primary_title': 'Sign Up', 
                'site_key': os.getenv("RECAPTCHA_SITE_KEY")
            }
        )

    def post(self, request):
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            raw_password = form.cleaned_data.get('password')
            if raw_password:
                user.set_password(raw_password)
            
            user.validation_date = timezone.now()
            user.validation_id = uuid.uuid4()
            user.save()
            user.save_history(user=user)

            send_mail(user.email, str(user.validation_id), "user_validation")
            messages.success(request, 'Account created! Please check your email to validate your account.')
            return redirect('login')
            
        messages.error(request, 'Email address already exists or invalid details.')
        return redirect('signup')


class LogoutView(RateLimitedGetMixin, View):
    @method_decorator(login_required)
    def get(self, request):
        logout(request)
        return redirect('home_view')


class EditPasswordView(LoginRequiredMixin, RateLimitedGetMixin, View):
    def get(self, request):
        form = EditPasswordForm()
        return render(request, 'authentication/edit_password.html', {
            'form': form,
            'primary_title': 'Change Password'
        })

    def post(self, request):
        form = EditPasswordForm(request.POST)
        if form.is_valid():
            old_password = form.cleaned_data.get('curr_password')
            new_password = form.cleaned_data.get('new_password')
            confirm_new_password = form.cleaned_data.get('confirm_new_password')

            if new_password != confirm_new_password:
                messages.error(request, 'New passwords do not match.')
            elif not request.user.check_password(old_password):
                messages.error(request, 'Current password is incorrect.')
            else:
                request.user.save_history(user=request.user)
                request.user.set_password(new_password)
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Your password was successfully updated!')
                return redirect('profile')

        return render(request, 'authentication/edit_password.html', {
            'form': form,
            'primary_title': 'Change Password'
        })


class PasswordResetRequestView(RateLimitedPostMixin, RateLimitedGetMixin, RecaptchaRequiredMixin, View):
    ratelimit_rate = '3/h'

    def get(self, request):
        form = PasswordResetForm()
        return render(
            request, 
            'authentication/forgot_password.html', 
            {
                'form': form, 
                'primary_title': 'Forgot Password', 
                'site_key': os.getenv("RECAPTCHA_SITE_KEY")
            }
        )

    def post(self, request):
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.filter(email=email).first()
            if user:
                if user.validated:
                    user.prt = uuid.uuid4()
                    user.prt_reset_date = timezone.now()
                    user.save()

                    send_mail(user.email, str(user.prt), "password_reset")
                    messages.success(request, 'Password reset instructions have been sent to your email.')
                    return redirect('login')
                else:
                    messages.error(request, 'This account is not validated.')
            else:
                messages.error(request, 'Email does not exist.')
        return redirect('generate_prt')


class PasswordResetView(RateLimitedPostMixin, RateLimitedGetMixin, RecaptchaRequiredMixin, View):
    ratelimit_rate = '3/h'

    def get(self, request, token):
        user = User.objects.filter(prt=token).first()
        if user:
            form = SetPasswordForm()
            return render(
                request, 
                'authentication/reset_password_form.html', 
                {
                    'form': form, 
                    'email': user.email, 
                    'token': token, 
                    'site_key': os.getenv("RECAPTCHA_SITE_KEY"), 
                    'primary_title': 'Reset Password'
                }
            )
        messages.error(request, 'Invalid or expired password reset link.')
        return redirect('generate_prt')

    def post(self, request, token):
        form = SetPasswordForm(request.POST)
        if form.is_valid():
            email = request.POST.get('email')
            new_password = form.cleaned_data['new_password']
            confirm_new_password = form.cleaned_data['confirm_new_password']
            user = User.objects.filter(email=email).first()
            if user and new_password == confirm_new_password:
                if user.prt_reset_date and timezone.now() > user.prt_reset_date + timedelta(minutes=60):
                    messages.error(request, 'Password reset token has expired.')
                else:
                    user.save_history(user=user)
                    user.prt_consumption_date = timezone.now()
                    user.prt = uuid.uuid4()
                    user.set_password(new_password)
                    user.save()
                    messages.success(request, 'Your password has been reset successfully. Please log in.')
                    return redirect('login')
            else:
                messages.error(request, 'Passwords do not match.')
        return redirect('reset_password', token=token)