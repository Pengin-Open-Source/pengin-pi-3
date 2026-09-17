# events/calendar.py
# The HTML month-grid renderer - this is UI/presentation logic tied to this
# app's own URL namespace (events:event_detail), so unlike the model and
# permission logic it depends on, it stays here rather than in main. The
# recurrence-occurrence math and the "who sees which events" scoping it
# calls both moved to main/main.auth (see main/models/event.py and
# main/auth/events.py) since other things may want them without this app.
from datetime import date
import calendar

from django.db.models import Q
from django.shortcuts import reverse

from main.auth.events import scope_events_for_staff, filter_events
from main.models import Event, expand_recurring_occurrences, get_local_time_beginning_of_month_in_utc


class EventCalendar(calendar.HTMLCalendar):
    cssclass_month = "table table-bordered calendar-month mb-0"
    cssclasses = ["text-center small text-uppercase text-muted"] * 7

    def __init__(self):
        self.month_events = {}
        self.year = None
        self.month = None
        self.user_time_zone = None
        super().__init__()

    def get_event_html(self, events):
        if not events:
            return ""
        items = ""
        for event in events:
            event_url = reverse("events:event_detail", kwargs={"pk": event.id})
            occurrence_date = getattr(event, "occurrence_date", None)
            if event.is_recurring and occurrence_date is not None:
                event_url = f"{event_url}?occurrence={occurrence_date.isoformat()}"
            if event.visibility == Event.VISIBILITY_PUBLIC:
                badge_class = "bg-info text-dark"
            elif event.visibility == Event.VISIBILITY_VALIDATED_PUBLIC:
                badge_class = "bg-success"
            else:
                badge_class = "bg-primary"
            items += (
                f"<a href='{event_url}' class='d-block text-truncate small text-decoration-none mb-1'>"
                f"<span class='badge {badge_class}'>{event.start_time()}</span> "
                f"<span class='text-body'>{event.title}</span>"
                f"</a>"
            )
        return f"<div class='calendar-day-events mt-1'>{items}</div>"

    def set_time_zone(self, zone):
        self.user_time_zone = zone

    def formatday(self, day, weekday):
        try:
            events_from_day = self.month_events[self.year][self.month].get(day)
        except KeyError:
            events_from_day = ""
        return self.day_cell(weekday, day, events=events_from_day)

    def day_cell(self, weekday, day, events=""):
        if day == 0:
            return "<td class='bg-light border'>&nbsp;</td>"

        supp_classes = "align-top p-1"
        if date(self.year, self.month, day) == date.today():
            supp_classes += " bg-primary-subtle"
        events_html = self.get_event_html(events)
        return (
            f"<td class='{supp_classes}' style='height: 6rem; width: 14.28%;'>"
            f"<div class='fw-semibold small'>{day}</div>"
            f"{events_html}</td>"
        )

    def formatmonth(self, year, month, *args, **kwargs):
        self.year = year
        self.month = month
        self.month_events = {}
        current_user = kwargs.pop("current_user")
        group_id = kwargs.pop("group_id", None)
        search_query = kwargs.pop("search_query", None)

        # Events are stored in UTC but shown in the viewer's local timezone,
        # so get the local beginning/end-of-month boundaries in UTC first.
        month_start = get_local_time_beginning_of_month_in_utc(year, month, self.user_time_zone)
        if month < 12:
            next_month, next_month_year = month + 1, year
        else:
            next_month, next_month_year = 1, year + 1
        month_end = get_local_time_beginning_of_month_in_utc(next_month_year, next_month, self.user_time_zone)

        time_conditions = (
            Q(start_datetime__gte=month_start, start_datetime__lt=month_end)
            | Q(end_datetime__gte=month_start, end_datetime__lt=month_end)
            | Q(start_datetime__lt=month_start, end_datetime__gte=month_end)
        )
        events_this_month = list(Event.objects.filter(is_recurring=False).filter(time_conditions))

        # Recurring events are one Event row for the whole weekly series -
        # never materialized per-week - so their occurrences within this
        # month are computed here rather than matched by time_conditions.
        recurring_events = Event.objects.filter(is_recurring=True, start_datetime__lt=month_end).filter(
            Q(recur_until__isnull=True) | Q(recur_until__gte=month_start.date())
        )
        recurring_occurrences = []
        for event in recurring_events:
            recurring_occurrences.extend(
                expand_recurring_occurrences(event, month_start, month_end)
            )

        events_this_month.extend(recurring_occurrences)

        if current_user.is_staff:
            events_in_month = scope_events_for_staff(
                events_this_month, current_user, group_id=group_id, search_query=search_query)
            events_in_month.sort(key=lambda event: event.start_datetime)
        else:
            events_in_month = filter_events(events_this_month, year, month, current_user)
            events_in_month.sort(key=lambda event: event.start_datetime)

        for event in events_in_month:
            event.start_datetime = event.start_datetime.astimezone(self.user_time_zone)
            event.end_datetime = event.end_datetime.astimezone(self.user_time_zone)

        for day in self.itermonthdays(year, month):
            if day > 0:
                day_date = date(year, month, day)
                day_events = (
                    self.month_events.setdefault(year, {}).setdefault(month, {}).setdefault(day, [])
                )
                for event in events_in_month:
                    if event.start_date() <= day_date <= event.end_date() and event not in day_events:
                        day_events.append(event)

        return super().formatmonth(year, month, *args, **kwargs)
