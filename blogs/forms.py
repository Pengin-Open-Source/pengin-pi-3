# blogs/forms.py
from django import forms
from .models import BlogPost


class BlogForm(forms.ModelForm):
    attachment = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )
    file_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Display title (e.g., Press Kit.pdf)'})
    )
    is_event = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_is_event'})
    )
    event_location = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Location / Room / Link'})
    )
    event_start_datetime = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )
    event_end_datetime = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )

    class Meta:
        model = BlogPost
        fields = ['title', 'tags', 'content', 'file_name', 'is_event']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter post title...'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 8, 'placeholder': 'Type content here...'}),
            'tags': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Announcements, Product Updates'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = True

        if self.instance and self.instance.pk and self.instance.event:
            self.fields['event_location'].initial = self.instance.event.location
            self.fields['event_start_datetime'].initial = (
                self.instance.event.start_datetime.strftime('%Y-%m-%dT%H:%M')
                if self.instance.event.start_datetime else None
            )
            self.fields['event_end_datetime'].initial = (
                self.instance.event.end_datetime.strftime('%Y-%m-%dT%H:%M')
                if self.instance.event.end_datetime else None
            )

    def clean(self):
        cleaned_data = super().clean()
        is_event = cleaned_data.get('is_event')

        if is_event:
            if not cleaned_data.get('event_start_datetime'):
                self.add_error('event_start_datetime', 'Start date & time is required for event posts.')
            if not cleaned_data.get('event_end_datetime'):
                self.add_error('event_end_datetime', 'End date & time is required for event posts.')

        return cleaned_data
