# views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from util.mail import send_mail
from django.utils.decorators import method_decorator
from django.views import View
from .forms import LoginForm, SignUpForm, PasswordResetForm, SetPasswordForm
from .models import User, Slug
from datetime import datetime, timedelta
import uuid
from django_ratelimit.decorators import ratelimit
import os
from django.views import View
from django.shortcuts import render
from django.http import Http404
from django.template import Template, Context
from .models import Slug
from django.shortcuts import render
from django_redis import get_redis_connection
import json
from django.http import HttpResponse
from django.template.loader import get_template
from django.shortcuts import get_object_or_404


def generate_uuid():
    return str(uuid.uuid4())


class LoginView(View):
    def get(self, request):
        form = LoginForm()
        return render(request, 'authentication/login.html', {'form': form, 'primary_title': 'Login'})

    # @ratelimit(key='ip', rate='3/minute', block=True)
    def post(self, request):
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home_view')
        messages.error(
            request, 'Please check your login details and try again.')
        return redirect('login')


class SignupView(View):
    def get(self, request):
        form = SignUpForm()
        return render(request, 'authentication/signup.html', {'form': form, 'primary_title': 'Sign Up', 'site_key': os.getenv("SITE_KEY")})

    # @ratelimit(key='ip', rate='3/minute', block=True)
    def post(self, request):
        # Access request object through self.request
        form = SignUpForm(self.request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.validation_date = datetime.utcnow()
            user.save()
            send_mail(user.email, user.validation_id, "user_validation")
            return redirect('login')
        messages.error(
            self.request, 'Email address already exists or invalid email.')
        return redirect('signup')


class LogoutView(View):
    @method_decorator(login_required)
    def get(self, request):
        logout(request)
        return redirect('home_view')
   
class PasswordResetRequestView(View):
    def get(self, request):
        form = PasswordResetForm()
        return render(request, 'authentication/generate_prt_form.html', {'form': form, 'primary_title': 'Forgot Password', 'site_key': os.getenv("SITE_KEY")})

    # @ratelimit(key='ip', rate='3/minute', block=True)
    def post(self, request):
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.filter(email=email).first()
            if user:
                if user.validated:
                    user.prt = generate_uuid()
                    user.prt_reset_date = datetime.utcnow()
                    user.save()
                    send_mail(user.email, user.prt, "password_reset")
                    return redirect('login')
                messages.error(request, 'This account is not validated.')
            else:
                messages.error(request, 'Email does not exist.')
        return redirect('generate_prt')


class PasswordResetView(View):
    def get(self, request, token):
        user = User.objects.filter(prt=token).first()
        if user:
            form = SetPasswordForm()
            return render(request, 'authentication/reset_password_form.html', {'form': form, 'email': user.email, 'token': token, 'site_key': os.getenv("SITE_KEY"), 'primary_title': 'Reset Password'})
        return redirect('generate_prt')

    # @ratelimit(key='ip', rate='3/minute', block=True)
    def post(self, request, token):
        form = SetPasswordForm(request.POST)
        if form.is_valid():
            email = request.POST.get('email')
            new_password = form.cleaned_data['new_password']
            confirm_new_password = form.cleaned_data['confirm_new_password']
            user = User.objects.filter(email=email).first()
            if user and new_password == confirm_new_password:
                if datetime.utcnow() > user.prt_reset_date + timedelta(minutes=60):
                    messages.error(request, 'Token expired.')
                else:
                    user.prt_consumption_date = datetime.utcnow()
                    user.set_password(new_password)
                    user.save()
                    return redirect('login')
            else:
                messages.error(request, 'Passwords do not match.')
        return redirect('reset_password', token=token)


class SlugView(SuperTemplateView):
    """
    Serve a Slug by rendering the static template first, then applying the
    render_template (dynamic template) on top of it.
    """

    def get(self, request, slug_path=""):
        # Resolve nested slugs
        slug_names = slug_path.strip("/").split("/")
        current_slug = None
        for name in slug_names:
            current_slug = get_object_or_404(Slug, name=name, parent=current_slug)

        # Admin flag
        is_admin = request.user.is_staff

        # Prepare context for both static and dynamic templates
        context_data = {
            "title": current_slug.name,
            "meta_tags": current_slug.meta_tags,
            "meta_description": current_slug.meta_description,
            "date": current_slug.date,
            "creator": current_slug.author,
            "is_admin": is_admin,
        }

        # First, render static template if present
        rendered = ""
        if current_slug.template_name:
            static_template = get_template(current_slug.template_name)
            rendered = static_template.render(context_data, request)

        # Then, render dynamic template if present
        if current_slug.render_template:
            dynamic_context = context_data.copy()
            try:
                # If render_template is JSON with named blocks
                dynamic_blocks = json.loads(current_slug.render_template)
                dynamic_context.update(dynamic_blocks)
            except json.JSONDecodeError:
                # fallback: treat as single 'main' block
                dynamic_context["main"] = current_slug.render_template

            # Use the already-rendered static template as the base
            dynamic_template = Template(rendered or "{{ main|safe }}")
            rendered = dynamic_template.render(Context(dynamic_context, autoescape=True))

        return HttpResponse(rendered)
    
    
class SlugEditView(View):
    def get (self, request):
        pass
    
    def post(self, request, token):
        pass
    
    
class SlugCreateView(View):
    def get (self, request):
        pass
    
    def post(self, request, token):
        pass
    
    

class RedisLoggingMixin:
    """
    Mixin to log requests to Redis automatically.
    """
    redis_prefix = "request_log"  # Redis key prefix
    redis_expire = 3600            # Keep logs for 1 hour by default

    def log_request(self, request):
        redis_conn = get_redis_connection("default")
        log_entry = {
            "user_id": getattr(request.user, "id", None),
            "username": getattr(request.user, "email", "Anonymous"),
            "method": request.method,
            "path": request.path,
            "ip": self.get_client_ip(request),
        }
        # Use timestamp as part of key
        import time
        key = f"{self.redis_prefix}:{int(time.time()*1000)}"
        redis_conn.set(key, json.dumps(log_entry), ex=self.redis_expire)

    @staticmethod
    def get_client_ip(request):
        # Handles X-Forwarded-For for proxied setups
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


class SuperTemplateView(RedisLoggingMixin, View):
    """
    Abstract view that logs requests and always renders with layout.html.
    """

    template_name = None  # Must be set in subclasses

    def get_context_data(self, **kwargs):
        """
        Override in child classes to add context.
        """
        return kwargs

    def render_to_response(self, request, context=None):
        """
        Wraps the context with layout.html
        """
        if context is None:
            context = {}
        context["super_template_content"] = self.template_name
        return render(request, "layout.html", context)

    def dispatch(self, request, *args, **kwargs):
        # Log request first
        self.log_request(request)
        return super().dispatch(request, *args, **kwargs)
