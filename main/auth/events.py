# main/auth/events.py
# Event access-control lives here, not in the events app, for the same
# reason TeamRole/TeamUserRole live in main/auth/models.py: "who can see or
# change this event" is permission/RBAC logic (department-manager and
# root/Executive checks via TeamUserRole, Group-based visibility), and the
# events app is meant to be a thin calendar-UI layer on top of main/util,
# not the owner of its own access rules. Ported from tobuwebprod's
# events/permissions.py (RBAC checks) and events/calendar.py (the
# staff-visibility scoping that's really "who sees which events", i.e. the
# same category of logic as everything else here).
from datetime import datetime, timedelta

from django.contrib.auth.models import Group
from django.contrib.auth.mixins import AccessMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from .models import TeamUserRole
from .permissions import is_root, is_executive_manager, get_managed_groups
from main.models.event import Event


def can_create_or_see_all_event_details(current_user, event_id=None):
    """Allows duplicating an event, creating a new one, and seeing all
    details of an existing one (a public event otherwise hides its
    participant list from unauthorized users)."""
    if not current_user.is_authenticated:
        return False

    if event_id is None:
        return True

    event = get_object_or_404(Event, id=event_id)
    user_groups = current_user.groups.all()

    matching_role = event.roles.filter(id__in=user_groups).exists()
    participant_ids = event.participants.values_list('participant_id', flat=True)

    return (
        current_user.is_staff
        or matching_role
        or current_user.id in participant_ids
        or current_user in [event.author, event.organizer]
    )


def can_see_public_event(event):
    """Anyone (including anonymous visitors) can see a public event that
    starts or ends within a year of now."""
    return _visible_within_a_year(event, event.visibility == Event.VISIBILITY_PUBLIC)


def can_see_validated_public_event(user, event):
    """Any validated, active account can see a validated-public event that
    starts or ends within a year of now."""
    if not (user and user.is_authenticated and user.validated and user.is_active):
        return False
    return _visible_within_a_year(event, event.visibility == Event.VISIBILITY_VALIDATED_PUBLIC)


def _visible_within_a_year(event, is_right_tier):
    if not is_right_tier:
        return False

    right_now = timezone.now()
    start_datetime = event.start_datetime
    end_datetime = event.end_datetime

    if not time_difference_over_a_year(right_now, start_datetime):
        return True
    if not time_difference_over_a_year(right_now, end_datetime):
        return True
    if start_datetime < right_now < end_datetime:
        return True

    return False


def getYearAwayValues():
    right_now = timezone.now()
    one_year_from_now = right_now + relativedelta(years=1)
    one_year_ago = right_now - relativedelta(years=1)

    return {
        "past_year": one_year_ago.year,
        "past_month": one_year_ago.month,
        "future_year": one_year_from_now.year,
        "future_month": one_year_from_now.month,
    }


def is_any_public_event_available():
    """Are there any public events within a year of now? Determines whether
    an anonymous visitor can access the calendar at all."""
    right_now = timezone.now()
    one_year_from_now = right_now + relativedelta(years=1)
    one_year_ago = right_now - relativedelta(years=1)

    time_conditions = (
        Q(start_datetime__gte=one_year_ago, start_datetime__lte=one_year_from_now)
        | Q(end_datetime__gte=one_year_ago, end_datetime__lte=one_year_from_now)
        | Q(start_datetime__lte=one_year_ago, end_datetime__gte=one_year_from_now)
    )

    return Event.objects.filter(Q(visibility=Event.VISIBILITY_PUBLIC) & time_conditions).exists()


def is_month_too_far_away(selected_year, selected_month):
    """Is the selected calendar month too far away to show an anonymous visitor?"""
    year_away = getYearAwayValues()
    future_year = year_away["future_year"]
    past_year = year_away["past_year"]
    future_month = year_away["future_month"]
    past_month = year_away["past_month"]

    selected_year = int(selected_year)
    selected_month = int(selected_month)

    if selected_year > future_year or selected_year < past_year:
        return True
    if selected_year == future_year and selected_month > future_month:
        return True
    if selected_year == past_year and selected_month < past_month:
        return True

    return False


def can_change_event(request, event_id):
    """The author or organizer can always edit an event. Root and Executives
    can always edit any event (a different, legitimate override tier from
    plain is_staff - see main/auth/permissions.py). Otherwise, if the event
    has roles (departments) assigned, editing requires being a real
    Manager-tier title in at least one of those departments - deliberately
    NOT a plain is_staff bypass; a plain staff member must not be able to
    edit another department's calendar just for being staff. An event with
    no roles assigned (general/company-wide) has no department to scope a
    manager to, so it falls back to is_staff."""
    event = get_object_or_404(Event, id=event_id)
    user = request.user
    if user in [event.author, event.organizer]:
        return True
    if is_root(user) or is_executive_manager(user):
        return True
    if event.roles.exists():
        if not (user and user.is_authenticated):
            return False
        return TeamUserRole.objects.filter(
            user=user, role__group__in=event.roles.all(), role__is_manager_role=True
        ).exists()
    return bool(user and user.is_authenticated and user.is_staff)


def can_reserve_public_slot(user, event):
    """Any validated, active account may book a public-reservable event."""
    if not event.is_public_reservable_time:
        return False
    return bool(user and user.is_authenticated and user.validated and user.is_active)


def can_reserve_internal_slot(user, event):
    """Staff, or a member of one of the event's roles groups, may book an
    internal-reservable event."""
    if not event.is_internal_reservable_time:
        return False
    if not (user and user.is_authenticated):
        return False
    if user.is_staff:
        return True
    user_groups = user.groups.all()
    return event.roles.filter(id__in=user_groups).exists()


def can_reserve_event(user, event):
    return can_reserve_public_slot(user, event) or can_reserve_internal_slot(user, event)


def get_available_slots(event, occurrence_date):
    """Splits the event's start/end time-of-day, applied to occurrence_date,
    into slot_duration_minutes chunks. Each dict has start/end (aware
    datetimes), 'past' (bool, whether the slot's start time has already
    elapsed - true for e.g. this morning's slots on today's occurrence),
    and 'reserved' (bool, true if either already booked OR already past -
    both make a slot non-bookable, so every existing caller that only
    checks 'reserved' to decide bookability is covered for free; 'past'
    is broken out separately for callers that want to explain *why* a
    slot isn't offered, e.g. showing "expired" instead of "booked")."""
    duration = timedelta(minutes=event.slot_duration_minutes)
    window_start = datetime.combine(occurrence_date, event.start_datetime.timetz())
    window_end = datetime.combine(occurrence_date, event.end_datetime.timetz())
    now = timezone.now()

    reserved_starts = set(
        event.reservations.filter(occurrence_date=occurrence_date).values_list('slot_start', flat=True)
    )

    slots = []
    slot_start = window_start
    while slot_start + duration <= window_end:
        slot_end = slot_start + duration
        is_past = slot_start <= now
        is_booked = slot_start in reserved_starts
        slots.append({
            'start': slot_start,
            'end': slot_end,
            'past': is_past,
            'reserved': is_booked or is_past,
        })
        slot_start = slot_end
    return slots


def time_difference_over_a_year(date1, date2):
    earlier = min(date1, date2)
    later = max(date1, date2)
    return later > earlier + relativedelta(years=1)


def scope_events_for_staff(events, current_user, group_id=None, search_query=None):
    """Staff see all internal+public events, but the default calendar view
    only shows the viewer's own/managed team(s) plus roleless (general)
    events - not the whole organization's calendar at once. A group=<id> or
    q=<exact name or email> GET param broadens this to a specific team or
    person; with neither, it's the default narrow view."""
    from main.models.users import User

    if group_id:
        group = Group.objects.filter(id=group_id).first()
        visible_group_ids = {group.id} if group else set()
    elif search_query:
        query = search_query.strip()
        matched_group = Group.objects.filter(name__iexact=query).first()
        if matched_group:
            visible_group_ids = {matched_group.id}
        else:
            matched_user = User.objects.filter(
                Q(name__iexact=query) | Q(email__iexact=query)
            ).first()
            if matched_user:
                user_events = [
                    event for event in events
                    if matched_user in (event.author, event.organizer)
                ]
                visible_group_ids = set(matched_user.groups.values_list("id", flat=True))
                return [
                    event for event in events
                    if event in user_events
                    or not event.roles.exists()
                    or event.roles.filter(id__in=visible_group_ids).exists()
                ]
            visible_group_ids = set()
    else:
        managed_group_ids = set(get_managed_groups(current_user).values_list("id", flat=True))
        own_group_ids = set(current_user.groups.values_list("id", flat=True))
        visible_group_ids = managed_group_ids | own_group_ids

    return [
        event for event in events
        if not event.roles.exists() or event.roles.filter(id__in=visible_group_ids).exists()
    ]


def filter_events(events, year, month, current_user=None):
    filtered_events = []
    if is_month_too_far_away(year, month):
        for event in events:
            if can_create_or_see_all_event_details(current_user, event.id):
                filtered_events.append(event)
    else:
        for event in events:
            if (
                can_see_public_event(event)
                or can_see_validated_public_event(current_user, event)
                or can_create_or_see_all_event_details(current_user, event.id)
            ):
                filtered_events.append(event)
    return filtered_events


class PublicEventsOrLoggedInMixin(AccessMixin):
    """Lets an authenticated+validated user through unconditionally.
    An anonymous (or authenticated-but-unvalidated) visitor is limited to
    public events within a year of today - and, for the month-grid view
    specifically, can't browse further than a year away at all."""

    def dispatch(self, request, *args, **kwargs):
        selected_year = self.kwargs.get("year")
        selected_month = self.kwargs.get("month")

        if request.user.is_authenticated and request.user.validated:
            return super().dispatch(request, *args, **kwargs)

        if selected_year and selected_month and is_month_too_far_away(selected_year, selected_month):
            return HttpResponseForbidden("<h1><center>Cannot View Events This Far From Today</center></h1>")

        event_id = self.kwargs.get("event_id") or self.kwargs.get("pk")
        if event_id:
            selected_event = get_object_or_404(Event, id=event_id)
            if can_see_public_event(selected_event):
                return super().dispatch(request, *args, **kwargs)
            return HttpResponseForbidden("<h1><center>Event Not Available</center></h1>")

        if is_any_public_event_available():
            return super().dispatch(request, *args, **kwargs)
        return HttpResponseForbidden("<h1><center>No Public Events Available At This Time</center></h1>")
