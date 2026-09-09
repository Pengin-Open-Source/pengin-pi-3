# events/forms.py
from django import forms

from main.models.users import User
from main.models import Event


class UserModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.name


class UserModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.name


DATETIME_WIDGET = forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})


class EventForm(forms.ModelForm):
    participants = UserModelMultipleChoiceField(
        queryset=User.objects.filter(validated=True), required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}))
    organizer = UserModelChoiceField(
        queryset=User.objects.filter(validated=True),
        widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = Event
        fields = [
            "title", "description", "location", "visibility",
            "start_datetime", "end_datetime", "organizer", "participants", "roles",
            "is_public_reservable_time", "is_internal_reservable_time", "slot_duration_minutes",
            "is_recurring", "recur_until",
        ]
        # template_name/render_template/json (the Slug-style dynamic-page
        # fields) are deliberately left out of this form - they let an
        # editor embed raw Django template code, so they're admin-only
        # (main.admin.EventAdmin) rather than exposed on the general event form.
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event title...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Event details...'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Clubhouse, Zoom...'}),
            'visibility': forms.Select(attrs={'class': 'form-select'}),
            'start_datetime': DATETIME_WIDGET,
            'end_datetime': DATETIME_WIDGET,
            'roles': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'is_public_reservable_time': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_internal_reservable_time': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'slot_duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'step': 5}),
            'is_recurring': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recur_until': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and not self.instance._state.adding:
            current_participant_ids = self.instance.participants.values_list('participant_id', flat=True)
            self.fields['participants'].initial = current_participant_ids

    def clean(self):
        cleaned_data = super().clean()
        selected_participants = cleaned_data.get('participants')
        start_datetime = cleaned_data.get('start_datetime')
        end_datetime = cleaned_data.get('end_datetime')

        if selected_participants is not None:
            if self.instance and not self.instance._state.adding:
                current_participant_ids = self.instance.participants.values_list('participant_id', flat=True)
                current_participants = User.objects.filter(id__in=current_participant_ids)
                self.participants_to_add = selected_participants.exclude(id__in=current_participants)
                self.participants_to_remove = current_participants.exclude(id__in=selected_participants)
            else:
                self.participants_to_add = selected_participants
                self.participants_to_remove = User.objects.none()

        if start_datetime and end_datetime and end_datetime < start_datetime:
            raise forms.ValidationError("Start date/time must be before end date/time!")

        is_recurring = cleaned_data.get('is_recurring')
        recur_until = cleaned_data.get('recur_until')
        if is_recurring and not recur_until:
            raise forms.ValidationError("Recurring events need a 'recur until' date.")
        if is_recurring and recur_until and start_datetime and recur_until < start_datetime.date():
            raise forms.ValidationError("'Recur until' must be on or after the event's start date.")

        return cleaned_data


class CalendarSettingsForm(forms.Form):
    first_day_of_week = forms.ChoiceField(
        label='First Day of the Calendar Week',
        choices=[(6, "Sunday"), (0, "Monday")],
        widget=forms.Select(attrs={'class': 'form-select'}))
