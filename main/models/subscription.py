# main/models/subscription.py
#
# Generic "notify me about changes to X" subscription framework - not tied
# to any one app. A Subscription points at any model instance via
# content_type/object_id (same GenericForeignKey pattern Slug already
# uses), so blogs, forums, or any future app branch can let visitors watch
# a specific object without core knowing anything about that app's models.
#
# Deliberately supports both an authenticated-account subscription (user
# set) and an anonymous email-only one (user null, email set, must be
# confirmed via a signed link before any notification goes out - see
# main/views/subscription.py) side by side in the same model. Whether a
# given deployed site actually *offers* the anonymous path is a
# settings-level policy choice (SUBSCRIPTIONS_REQUIRE_ACCOUNT), not
# something enforced here - core stays maximally capable, each site's own
# main/settings.py narrows it down.
import uuid
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from .mixins import HistoryMixin, AbstractHistory


class Subscription(HistoryMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subscriptions",
        help_text="Set for an account subscription; left null for an anonymous "
                  "email-only one."
    )
    # Always populated, even for an account subscription (copied from
    # user.email at creation) - so notify_subscribers() never has to
    # special-case where the send-to address comes from.
    email = models.EmailField()

    unsubscribe_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # Null until confirmed. An account subscription is confirmed at
    # creation time (an authenticated session already establishes who's
    # asking); an anonymous one stays null until the subscriber clicks the
    # confirm-by-email link. notify_subscribers() must never send to a row
    # where this is still null.
    confirmed_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"
        constraints = [
            # Postgres treats NULL as distinct for uniqueness purposes, so
            # these two conditional constraints correctly allow an
            # unlimited number of NULL-user (anonymous) rows per object
            # while still preventing a duplicate subscription within each
            # path - an account can't double-subscribe to the same object,
            # and neither can the same anonymous email address.
            models.UniqueConstraint(
                fields=["content_type", "object_id", "user"],
                condition=models.Q(user__isnull=False),
                name="unique_account_subscription",
            ),
            models.UniqueConstraint(
                fields=["content_type", "object_id", "email"],
                condition=models.Q(user__isnull=True),
                name="unique_anonymous_subscription",
            ),
        ]

    def __str__(self):
        who = self.user.email if self.user_id else self.email
        return f"{who} -> {self.content_type} #{self.object_id}"

    @property
    def is_confirmed(self):
        return self.confirmed_at is not None


def notify_subscribers(instance, url):
    """Emails every confirmed, active Subscription watching `instance` -
    the one piece of glue an app calls after saving a change to something
    subscribable (e.g. a new BlogPost revision, a ForumThread reply).
    `url` is the absolute link to show recipients: Subscription is generic
    over content_type/object_id and has no get_absolute_url() story of its
    own, so the caller (which knows its own model) provides it rather than
    this function guessing at one.

    Skips anything not yet confirmed (an anonymous subscriber who never
    clicked the confirm link) or soft-unsubscribed (is_active=False) -
    see main/views/subscription.py for both of those transitions."""
    import os
    from util.mail import send_mail

    content_type = ContentType.objects.get_for_model(instance)
    subscriptions = Subscription.objects.filter(
        content_type=content_type, object_id=instance.pk,
        is_active=True, confirmed_at__isnull=False,
    )
    label = str(instance)
    site_url = os.getenv("URL")
    for subscription in subscriptions:
        unsubscribe_url = f"https://{site_url}/subscriptions/unsubscribe/{subscription.unsubscribe_token}/"
        send_mail(
            subscription.email, TYPE="subscription_notify",
            OBJECT_URL=url, OBJECT_LABEL=label, UNSUBSCRIBE_URL=unsubscribe_url,
        )


class SubscriptionHistory(AbstractHistory):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    object = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="history"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+"
    )

    class Meta(AbstractHistory.Meta):
        verbose_name_plural = "Subscription Histories"

    def __str__(self):
        return f"Subscription {self.object_id} @ {self.changed_at}"
