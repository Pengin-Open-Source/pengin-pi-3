# events/urls.py
from django.urls import path
from .views import (
    CalendarMonth,
    CreateEvent,
    DetailEvent,
    EditEvent,
    DeleteEvent,
    CalendarSettings,
    EventParticipantsDetailView,
    EventICSExportView,
    ReserveEventSlotView,
    MyReservationsView,
    CancelReservationView,
    FindPersonEventView,
)

app_name = 'events'

urlpatterns = [
    path('calendar/', CalendarMonth.as_view(), name='calendar'),
    path('calendar/<int:year>/<int:month>/', CalendarMonth.as_view(), name='calendar-month'),
    path('calendar/create/', CreateEvent.as_view(), name='create_event'),
    path('calendar/settings/', CalendarSettings.as_view(), name='calendar-settings'),
    path('calendar/my-reservations/', MyReservationsView.as_view(), name='my_reservations'),
    path('calendar/find/', FindPersonEventView.as_view(), name='find_person'),
    path('calendar/reservations/<uuid:pk>/cancel/', CancelReservationView.as_view(), name='cancel_reservation'),
    path('calendar/<uuid:pk>/', DetailEvent.as_view(), name='event_detail'),
    path('calendar/<uuid:pk>/participants/', EventParticipantsDetailView.as_view(), name='display_event_participants'),
    path('calendar/<uuid:pk>/copy/', CreateEvent.as_view(), name='copy_event'),
    path('calendar/<uuid:pk>/edit/', EditEvent.as_view(), name='event_edit'),
    path('calendar/<uuid:pk>/delete/', DeleteEvent.as_view(), name='event_delete'),
    path('calendar/<uuid:pk>/ics/', EventICSExportView.as_view(), name='event_ics'),
    path('calendar/<uuid:pk>/reserve/', ReserveEventSlotView.as_view(), name='reserve_slot'),
]
