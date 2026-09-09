# main/models/event.py
# Event tracking is native pp3 framework infrastructure, not an optional
# per-app bolt-on: the model lives here (registered under 'main', same
# convention as Site/Slug/TeamRole) so any app can depend on it - and on
# main.auth.events' RBAC-integrated permission checks - without needing a
# separate 'events' Django app installed. The events app itself is just the
# calendar UI (views/urls/templates) built on top of this and main.auth.
import copy
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import models
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import Group
from .mixins import HistoryMixin, AbstractHistory


class Event(HistoryMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)

    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    # `date` is bumped on every edit; date_created is immutable.
    date = models.DateTimeField(default=timezone.now)
    date_created = models.DateTimeField(auto_now_add=True)

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="authored_events"
    )
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organized_events"
    )
    last_edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+"
    )

    # Optional role-based restriction: blank means visible to any validated
    # user (or, for public events, to anyone) - see main/auth/events.py.
    roles = models.ManyToManyField(
        Group,
        blank=True,
        related_name="events",
        help_text="Leave blank to make this event visible regardless of role."
    )

    VISIBILITY_INTERNAL = 'internal'
    VISIBILITY_VALIDATED_PUBLIC = 'validated_public'
    VISIBILITY_PUBLIC = 'public'
    VISIBILITY_CHOICES = [
        (VISIBILITY_INTERNAL, 'Internal (staff/team only)'),
        (VISIBILITY_VALIDATED_PUBLIC, 'Validated Public (any validated account)'),
        (VISIBILITY_PUBLIC, 'Public (anyone, incl. anonymous visitors)'),
    ]
    visibility = models.CharField(
        max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_INTERNAL,
        help_text="Who can see this event. Public events appear on the public calendar page.")

    # Optional Slug-style dynamic page (main.models.Slug uses the same
    # template_name/render_template/json shape, resolved by the same
    # util.dynamic_render.render_dynamic_content helper) - if neither
    # template field is set, the standard calendar event detail view is
    # used as-is.
    template_name = models.CharField(max_length=300, blank=True)
    render_template = models.TextField(blank=True)
    json = models.JSONField(default=dict, blank=True)

    # Reservable time slots (see EventReservation below). slot_duration_minutes
    # is the "time_frame" each bookable slot spans within start/end_datetime.
    is_public_reservable_time = models.BooleanField(
        default=False, help_text="Any validated, active user may reserve a time slot on this event.")
    is_internal_reservable_time = models.BooleanField(
        default=False, help_text="Staff, or members of this event's roles, may reserve a time slot.")
    slot_duration_minutes = models.PositiveIntegerField(default=30)

    # Weekly recurrence: occurrences are computed at render time (see
    # expand_recurring_occurrences below), never materialized as separate
    # Event rows.
    is_recurring = models.BooleanField(default=False)
    recur_until = models.DateField(
        null=True, blank=True,
        help_text="Last date this weekly-recurring event still appears on the calendar.")

    class Meta:
        ordering = ['start_datetime']
        verbose_name = "Event"
        verbose_name_plural = "Events"
        indexes = [
            models.Index(fields=['visibility', 'start_datetime'], name='event_visibility_start_idx'),
            models.Index(fields=['start_datetime'], name='event_start_idx'),
            models.Index(fields=['end_datetime'], name='event_end_idx'),
        ]

    def __str__(self):
        return f"{self.title} ({self.start_datetime.strftime('%Y-%m-%d')})"

    def start_date(self):
        return self.start_datetime.date()

    def end_date(self):
        return self.end_datetime.date()

    def start_time(self):
        return self.start_datetime.strftime("%I:%M %p")

    def end_time(self):
        return self.end_datetime.strftime("%I:%M %p")

    def to_ics(self) -> str:
        """Generates a standard iCalendar (.ics) string for calendar downloads."""
        fmt = "%Y%m%dT%H%M%SZ"
        start_utc = self.start_datetime.strftime(fmt)
        end_utc = self.end_datetime.strftime(fmt)
        created_utc = self.date_created.strftime(fmt)
        description = self.description.replace('\n', '\\n')

        return (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "PRODID:-//Pengin Pi 3//Calendar Event//EN\r\n"
            "CALSCALE:GREGORIAN\r\n"
            "METHOD:PUBLISH\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:{self.id}\r\n"
            f"DTSTAMP:{created_utc}\r\n"
            f"DTSTART:{start_utc}\r\n"
            f"DTEND:{end_utc}\r\n"
            f"SUMMARY:{self.title}\r\n"
            f"DESCRIPTION:{description}\r\n"
            f"LOCATION:{self.location}\r\n"
            "STATUS:CONFIRMED\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )


class EventHistory(AbstractHistory):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    object = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="history")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta(AbstractHistory.Meta):
        verbose_name_plural = "Event Histories"

    def __str__(self):
        return f"Event {self.object_id} @ {self.changed_at}"


class EventParticipant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateTimeField(auto_now_add=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='participants')
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='event_participations')
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='event_participants_added')

    class Meta:
        unique_together = [('event', 'participant')]

    def __str__(self):
        return str(self.participant.name)


class EventReservation(models.Model):
    """A booked time slot on a reservable Event. occurrence_date is the
    specific week/date being booked - equal to event.start_date() for a
    non-recurring event, or whichever week's virtual occurrence a recurring
    event's slot was booked against (see expand_recurring_occurrences below).
    Recurring events never get their own Event rows per week, so this field
    is what disambiguates which week's slot is taken."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='reservations')
    occurrence_date = models.DateField()
    slot_start = models.DateTimeField()
    slot_end = models.DateTimeField()
    reserved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='event_reservations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('event', 'occurrence_date', 'slot_start')]
        ordering = ['slot_start']

    def __str__(self):
        return f"{self.event.title} @ {self.slot_start} ({self.reserved_by})"


def expand_recurring_occurrences(event, month_start, month_end):
    """Yields shallow-copied, non-persisted Event instances (one per weekly
    occurrence of `event` that falls within [month_start, month_end)), each
    with start_datetime/end_datetime shifted to that occurrence and tagged
    with .occurrence_date - the calendar's virtual-occurrence mechanism for
    recurring events (see Event.is_recurring/recur_until)."""
    duration = event.end_datetime - event.start_datetime
    recur_until = event.recur_until

    if event.start_datetime >= month_start:
        occurrence_start = event.start_datetime
    else:
        weeks_elapsed = (month_start - event.start_datetime) // timedelta(weeks=1)
        occurrence_start = event.start_datetime + timedelta(weeks=weeks_elapsed)
        if occurrence_start < month_start:
            occurrence_start += timedelta(weeks=1)

    occurrences = []
    while occurrence_start < month_end:
        if recur_until is None or occurrence_start.date() <= recur_until:
            virtual_event = copy.copy(event)
            virtual_event.start_datetime = occurrence_start
            virtual_event.end_datetime = occurrence_start + duration
            virtual_event.occurrence_date = occurrence_start.date()
            occurrences.append(virtual_event)
        occurrence_start += timedelta(weeks=1)
    return occurrences


def get_local_time_beginning_of_month_in_utc(year: int, month: int, user_time_zone: ZoneInfo) -> datetime:
    """Midnight (local time) on the 1st of the given month, converted to UTC."""
    utc_zone = ZoneInfo('UTC')
    naive_dt = datetime(year, month, 1, 0, 0, 0)
    local_midnight_dt = naive_dt.replace(tzinfo=user_time_zone)
    return local_midnight_dt.astimezone(utc_zone)
