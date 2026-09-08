from django import forms


class UserModelChoiceField(forms.ModelChoiceField):
    """Renders a User option as their display name, falling back to email."""

    def label_from_instance(self, obj):
        return obj.name or obj.email
