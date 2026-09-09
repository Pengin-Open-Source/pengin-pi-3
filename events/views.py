# events/views.py
import json
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, reverse, get_object_or_404, redirect
from django.utils import timezone
from django.views import View

from main.auth import LoginAndValidationRequiredMixin
from main.auth.events import (
    PublicEventsOrLoggedInMixin,
    can_create_or_see_all_event_details,
    can_change_event,
    can_see_public_event,
    can_see_validated_public_event,
    can_reserve_event,
    get_available_slots,
)
from main.models.users import User
from main.models import Event, EventParticipant, EventReservation
from util.dynamic_render import render_dynamic_content
from .calendar import EventCalendar
from .forms import EventForm, CalendarSettingsForm

myCal = EventCalendar()


class CalendarMonth(PublicEventsOrLoggedInMixin, View):
    template_name = "calendar/calendar_month.html"

    def get(self, request, year=None, month=None):
        user_time_zone_str = request.COOKIES.get('time_zone') or request.session.get('time_zone_string') or 'UTC'
        myCal.set_time_zone(user_time_zone_str)

        present_local_time = timezone.now().astimezone(ZoneInfo(user_time_zone_str))
        present_year, present_month = present_local_time.year, present_local_time.month

        if year is None or month is None:
            year, month = present_year, present_month
        year, month = int(year), int(month)

        if not myCal.user_settings:
            myCal.setfirstweekday(6)

        group_id = request.GET.get('group')
        search_query = request.GET.get('q')
        calendar_html = myCal.formatmonth(
            year, month, current_user=request.user,
            group_id=group_id, search_query=search_query,
        )

        if month == 1:
            previous_month = {"year": year - 1, "month": 12}
        else:
            previous_month = {"year": year, "month": month - 1}
        if month == 12:
            next_month = {"year": year + 1, "month": 1}
        else:
            next_month = {"year": year, "month": month + 1}

        filter_qs = ""
        if request.user.is_staff and (group_id or search_query):
            params = {}
            if group_id:
                params['group'] = group_id
            if search_query:
                params['q'] = search_query
            filter_qs = "?" + urlencode(params)

        return render(request, self.template_name, {
            "primary_title": "Calendar",
            "calendar_html": calendar_html,
            "group_id": group_id,
            "search_query": search_query,
            "url_previous_month": reverse("events:calendar-month", kwargs=previous_month) + filter_qs,
            "url_present_month": reverse("events:calendar-month", kwargs={"year": present_year, "month": present_month}) + filter_qs,
            "url_next_month": reverse("events:calendar-month", kwargs=next_month) + filter_qs,
        })


class DetailEvent(PublicEventsOrLoggedInMixin, UserPassesTestMixin, View):
    template_name = "calendar/event_detail.html"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.can_see_all_details = False

    def test_func(self):
        event = get_object_or_404(Event, id=self.kwargs.get("pk"))
        if self.request.user.is_authenticated and self.request.user.validated:
            self.can_see_all_details = can_create_or_see_all_event_details(self.request.user, event.id)
        return (
            can_see_public_event(event)
            or can_see_validated_public_event(self.request.user, event)
            or self.can_see_all_details
        )

    def get(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        page_number = request.GET.get('page', 1)

        role_paginator = Paginator(event.roles.order_by('name'), 10)
        role_page_obj = role_paginator.get_page(page_number)

        occurrence_str = request.GET.get('occurrence')
        occurrence_date = event.start_date()
        if event.is_recurring and occurrence_str:
            try:
                occurrence_date = datetime.strptime(occurrence_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        context = {
            "primary_title": event.title,
            "event": event,
            "can_change": can_change_event(request, pk),
            "can_see_all_details": self.can_see_all_details,
            "can_reserve": can_reserve_event(request.user, event),
            "occurrence_date": occurrence_date,
            "role_page_obj": role_page_obj,
            "event_roles": role_page_obj.object_list,
        }

        if not event.template_name and not event.render_template:
            return render(request, self.template_name, context)

        # Slug-style dynamic page: if the event has a template_name and/or
        # render_template set, render that instead of the standard detail
        # page (see util.dynamic_render.render_dynamic_content - shared
        # with main.views.slug.SlugView, since Event has the same field
        # shape). schema_data from event.json is merged into context first,
        # same as SlugView does with a Slug's json field.
        raw_json = event.json
        if isinstance(raw_json, str) and raw_json.strip():
            try:
                schema_data = json.loads(raw_json)
            except json.JSONDecodeError:
                schema_data = {}
        elif isinstance(raw_json, dict):
            schema_data = raw_json
        else:
            schema_data = {}
        context.update(schema_data)

        response = render_dynamic_content(request, event.template_name, event.render_template, context)
        return response if response is not None else HttpResponse("")


class EventParticipantsDetailView(LoginAndValidationRequiredMixin, UserPassesTestMixin, View):
    template_name = "calendar/event_participants.html"

    def test_func(self):
        return can_create_or_see_all_event_details(self.request.user, self.kwargs.get("pk"))

    def get(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        page_number = request.GET.get('page', 1)

        participant_ids = event.participants.values_list('participant_id', flat=True)
        users = User.objects.filter(id__in=participant_ids).order_by('name')
        page_obj = Paginator(users, 10).get_page(page_number)

        return render(request, self.template_name, {
            "primary_title": "Participants in " + event.title,
            "event": event,
            "can_change": can_change_event(request, pk),
            "event_participants": page_obj.object_list,
            "page_obj": page_obj,
        })


class CreateEvent(LoginAndValidationRequiredMixin, UserPassesTestMixin, View):
    template_name = "calendar/event_form.html"

    def test_func(self):
        return can_create_or_see_all_event_details(self.request.user, self.kwargs.get("pk"))

    def get_initial(self):
        event = get_object_or_404(Event, id=self.kwargs["pk"])
        return {
            "title": event.title,
            "description": event.description,
            "location": event.location,
            "visibility": event.visibility,
            "is_public_reservable_time": event.is_public_reservable_time,
            "is_internal_reservable_time": event.is_internal_reservable_time,
            "slot_duration_minutes": event.slot_duration_minutes,
            "is_recurring": event.is_recurring,
            "recur_until": event.recur_until,
            "organizer": event.organizer,
            "participants": event.participants.values_list('participant_id', flat=True),
            "roles": event.roles.values_list('id', flat=True),
            "start_datetime": event.start_datetime,
            "end_datetime": event.end_datetime,
        }

    def get(self, request, *args, **kwargs):
        if "pk" in self.kwargs:
            form = EventForm(initial=self.get_initial())
            primary_title = "Duplicate Event: " + self.get_initial()["title"]
        else:
            form = EventForm()
            primary_title = "Create Event"

        return render(request, self.template_name, {
            "primary_title": primary_title,
            "action": "create",
            "form": form,
        })

    def post(self, request, **kwargs):
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.author = request.user
            event.organizer = form.cleaned_data['organizer']
            event.save()
            form.save_m2m()

            for attendee in form.participants_to_add:
                EventParticipant.objects.create(event=event, participant=attendee, added_by=request.user)

            event.save_history(user=request.user)
            return redirect("events:calendar")

        return render(request, self.template_name, {
            "primary_title": "Create Event",
            "action": "create",
            "form": form,
        })


class EditEvent(LoginAndValidationRequiredMixin, UserPassesTestMixin, View):
    template_name = "calendar/event_form.html"

    def test_func(self):
        return can_change_event(self.request, self.kwargs.get("pk"))

    def get_context_data(self):
        event = get_object_or_404(Event, id=self.kwargs["pk"])
        return {
            "primary_title": "Edit Event",
            "action": "update",
            "form": EventForm(instance=event),
            "event": event,
        }

    def get(self, request, pk):
        return render(request, self.template_name, self.get_context_data())

    def post(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            event.save_history(user=request.user)

            with transaction.atomic():
                event = form.save(commit=False)
                event.last_edited_by = request.user
                event.date = timezone.now()
                event.save()
                form.save_m2m()

                for attendee in form.participants_to_add:
                    EventParticipant.objects.create(event=event, participant=attendee, added_by=request.user)
                EventParticipant.objects.filter(
                    event=event, participant__in=form.participants_to_remove).delete()

            return redirect("events:event_detail", pk=event.id)

        context = self.get_context_data()
        context["form"] = form
        return render(request, self.template_name, context)


class DeleteEvent(LoginAndValidationRequiredMixin, UserPassesTestMixin, View):
    template_name = "calendar/event_confirm_delete.html"

    def test_func(self):
        return can_change_event(self.request, self.kwargs.get("pk"))

    def get(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        return render(request, self.template_name, {
            "primary_title": f"Delete Event: {event.title}",
            "event": event,
        })

    def post(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        event.save_history(user=request.user)
        event.delete()
        return redirect('events:calendar')


class CalendarSettings(LoginAndValidationRequiredMixin, View):
    template_name = "calendar/calendar_settings.html"

    def get(self, request):
        form = CalendarSettingsForm(initial={'first_day_of_week': myCal.firstweekday})
        return render(request, self.template_name, {
            "form": form,
            "primary_title": "Calendar Settings",
        })

    def post(self, request):
        form = CalendarSettingsForm(request.POST)
        if form.is_valid():
            myCal.setfirstweekday(int(form.cleaned_data['first_day_of_week']))
            myCal.user_settings = True
            return redirect('events:calendar')

        return render(request, self.template_name, {
            "form": form,
            "primary_title": "Calendar Settings",
        })


class EventICSExportView(PublicEventsOrLoggedInMixin, UserPassesTestMixin, View):
    """Generates a standard .ics download for Apple/Outlook/Google Calendar.
    Uses the same visibility rules as DetailEvent - anonymous visitors can
    download a public event's .ics without logging in."""

    def test_func(self):
        event = get_object_or_404(Event, id=self.kwargs.get("pk"))
        if can_see_public_event(event) or can_see_validated_public_event(self.request.user, event):
            return True
        if self.request.user.is_authenticated and self.request.user.validated:
            return can_create_or_see_all_event_details(self.request.user, event.id)
        return False

    def get(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        response = HttpResponse(event.to_ics(), content_type='text/calendar; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="event_{event.id}.ics"'
        return response


class ReserveEventSlotView(LoginAndValidationRequiredMixin, UserPassesTestMixin, View):
    """Lists available slots for one occurrence of a reservable event and
    books one. ?occurrence=YYYY-MM-DD picks which week's occurrence (for a
    recurring event); defaults to the event's own start date."""
    template_name = "calendar/reserve_slot.html"

    def test_func(self):
        event = get_object_or_404(Event, id=self.kwargs.get("pk"))
        return can_reserve_event(self.request.user, event)

    def get_occurrence_date(self, request, event):
        occurrence_str = request.GET.get('occurrence') or request.POST.get('occurrence')
        if occurrence_str:
            try:
                return datetime.strptime(occurrence_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        return event.start_date()

    def get(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        occurrence_date = self.get_occurrence_date(request, event)
        raw_slots = get_available_slots(event, occurrence_date)

        # Shape for the shared templates/widgets/slot-picker.html (a
        # {label, value, available} row per slot); form_action carries the
        # occurrence date in the query string so the POST handler below can
        # recover it via request.GET even though the widget's own hidden
        # field only carries the chosen slot's start time.
        slots = [{
            'label': slot['start'].strftime('%-I:%M %p'),
            'value': slot['start'].isoformat(),
            'available': not slot['reserved'],
        } for slot in raw_slots]
        form_action = f"?occurrence={occurrence_date.isoformat()}"

        return render(request, self.template_name, {
            "primary_title": f"Reserve a Time: {event.title}",
            "event": event,
            "occurrence_date": occurrence_date,
            "slots": slots,
            "form_action": form_action,
        })

    def post(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        occurrence_date = self.get_occurrence_date(request, event)
        slot_start_str = request.POST.get('slot')

        try:
            slot_start = datetime.fromisoformat(slot_start_str)
        except (TypeError, ValueError):
            messages.error(request, "Invalid time slot selected.")
            return redirect('events:reserve_slot', pk=event.id)

        available = {s['start']: s for s in get_available_slots(event, occurrence_date)}
        chosen = available.get(slot_start)
        if not chosen or chosen['reserved']:
            messages.error(request, "That slot is no longer available. Please pick another.")
            return redirect(f"{reverse('events:reserve_slot', kwargs={'pk': event.id})}?occurrence={occurrence_date}")

        EventReservation.objects.create(
            event=event,
            occurrence_date=occurrence_date,
            slot_start=chosen['start'],
            slot_end=chosen['end'],
            reserved_by=request.user,
        )
        messages.success(request, "Your time slot is reserved.")
        return redirect('events:my_reservations')


class MyReservationsView(LoginAndValidationRequiredMixin, View):
    template_name = "calendar/my_reservations.html"

    def get(self, request):
        reservations = EventReservation.objects.filter(
            reserved_by=request.user, slot_start__gte=timezone.now()
        ).select_related('event').order_by('slot_start')
        return render(request, self.template_name, {
            "primary_title": "My Reservations",
            "reservations": reservations,
        })


class FindPersonEventView(LoginAndValidationRequiredMixin, View):
    """Narrow, opt-in search: an exact (iexact) name-or-email match against
    the organizer of a public-reservable event. Never a browsable staff/
    person directory - a query that matches no public-reservable event's
    organizer returns nothing, and this never exposes internal-only events
    or groups. Requires a validated, active login (enforced by the mixin);
    a query matching exactly one event redirects straight to booking it."""
    template_name = "calendar/find_person.html"

    def get(self, request):
        query = request.GET.get('q', '').strip()
        matches = []
        if query:
            matches = list(Event.objects.filter(
                is_public_reservable_time=True
            ).filter(
                Q(organizer__name__iexact=query) | Q(organizer__email__iexact=query)
            ).select_related('organizer'))

        if len(matches) == 1:
            return redirect('events:reserve_slot', pk=matches[0].id)

        return render(request, self.template_name, {
            "primary_title": "Find a Person",
            "query": query,
            "matches": matches,
        })


class CancelReservationView(LoginAndValidationRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        reservation = get_object_or_404(EventReservation, id=self.kwargs.get("pk"))
        return self.request.user == reservation.reserved_by or self.request.user.is_staff

    def post(self, request, pk):
        reservation = get_object_or_404(EventReservation, id=pk)
        reservation.delete()
        messages.success(request, "Reservation cancelled.")
        return redirect('events:my_reservations')
