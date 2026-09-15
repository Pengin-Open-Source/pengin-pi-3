# main/views/subscription.py
# Generic subscribe/confirm/unsubscribe views for main.models.Subscription
# - addressed by ContentType/object_id (see that model's docstring), so
# any app's model can be subscribed to without these views knowing
# anything about it beyond app_label/model/pk.
from django.conf import settings
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views import View

from main.forms.subscription import SubscribeForm
from main.models.subscription import Subscription
from util.mail import send_mail
from util.security.ratelimit import RateLimitedPostMixin


def _redirect_back(request):
    return redirect(request.META.get('HTTP_REFERER') or '/')


class SubscribeView(RateLimitedPostMixin, View):
    """POST /subscribe/<app_label>/<model>/<uuid:object_id>/ - subscribes
    the current user (if authenticated) or a submitted email address (if
    anonymous and settings.SUBSCRIPTIONS_REQUIRE_ACCOUNT is False) to
    updates on one object. Always redirects back to wherever the request
    came from - this is meant to be a small form embedded on the object's
    own page, not a standalone destination.

    Rate-limited (RateLimitedPostMixin): the anonymous path sends a real
    email to whatever address is submitted, so without a limit this would
    be a free tool for spamming/harassing arbitrary inboxes with
    "confirm your subscription" emails - it doesn't require knowing
    anything about the target beyond their address."""
    ratelimit_rate = '10/m'

    def post(self, request, app_label, model, object_id):
        content_type = get_object_or_404(ContentType, app_label=app_label, model=model)
        obj = get_object_or_404(content_type.model_class(), pk=object_id)

        if request.user.is_authenticated:
            subscription, created = Subscription.objects.get_or_create(
                content_type=content_type, object_id=object_id, user=request.user,
                defaults={'email': request.user.email, 'confirmed_at': timezone.now()},
            )
            messages.success(request, "You're subscribed." if created else "You're already subscribed.")
            return _redirect_back(request)

        if getattr(settings, 'SUBSCRIPTIONS_REQUIRE_ACCOUNT', False):
            messages.error(request, "Please log in to subscribe.")
            return redirect(f"{settings.LOGIN_URL}?next={request.META.get('HTTP_REFERER') or '/'}")

        form = SubscribeForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Enter a valid email address to subscribe.")
            return _redirect_back(request)

        email = form.cleaned_data['email'].strip().lower()
        subscription, created = Subscription.objects.get_or_create(
            content_type=content_type, object_id=object_id, user=None, email=email,
        )
        if created:
            send_mail(email, str(subscription.unsubscribe_token), "subscription_confirm", OBJECT_LABEL=str(obj))
            messages.success(request, "Check your email to confirm your subscription.")
        elif subscription.is_confirmed:
            messages.info(request, "You're already subscribed.")
        else:
            send_mail(email, str(subscription.unsubscribe_token), "subscription_confirm", OBJECT_LABEL=str(obj))
            messages.info(request, "You already requested this - check your email to confirm.")
        return _redirect_back(request)


class ConfirmSubscriptionView(View):
    """GET /subscriptions/confirm/<uuid:token>/ - the link an anonymous
    subscriber clicks from their confirmation email. The token itself
    (an unguessable UUID, unique per row) is the only credential needed -
    no login required, matching how the confirmation email was the only
    proof of address ownership needed in the first place."""

    def get(self, request, token):
        subscription = get_object_or_404(Subscription, unsubscribe_token=token)
        if subscription.confirmed_at is None:
            subscription.confirmed_at = timezone.now()
            subscription.save()
        return render(request, 'subscriptions/confirmed.html', {
            'subscription': subscription, 'primary_title': 'Subscription Confirmed',
        })


class UnsubscribeView(View):
    """GET /subscriptions/unsubscribe/<uuid:token>/ - a one-click
    unsubscribe link (the convention every email client and spam filter
    expects), not a POST-gated confirm step: the token is itself the
    bearer credential, exactly as it is for ConfirmSubscriptionView above.
    Idempotent - visiting an already-unsubscribed link just re-shows the
    same confirmation page instead of erroring."""

    def get(self, request, token):
        subscription = get_object_or_404(Subscription, unsubscribe_token=token)
        if subscription.is_active:
            subscription.save_history(user=subscription.user)
            subscription.is_active = False
            subscription.save()
        return render(request, 'subscriptions/unsubscribed.html', {
            'subscription': subscription, 'primary_title': 'Unsubscribed',
        })
