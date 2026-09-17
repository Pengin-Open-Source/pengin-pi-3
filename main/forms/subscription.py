# main/forms/subscription.py
# Only needed for the anonymous email-only path (main.views.subscription.
# SubscribeView) - an authenticated subscription needs no form, since the
# account's own email is used directly.
from django import forms


class SubscribeForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'you@example.com'}))
