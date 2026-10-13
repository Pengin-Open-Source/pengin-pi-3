# Pengin-Pi-3 — Pengin Open Source
# util/forms/fields.py
#
# Shared form fields, such as a User choice field labeled by display name.
#
# Copyright (C) 2026 Tobu Pengin, L.L.C. and contributors
# Authors:
#   Stuart Anderson <stuart@tobupengin.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
from django import forms


class UserModelChoiceField(forms.ModelChoiceField):
    """Renders a User option as their display name, falling back to email."""

    def label_from_instance(self, obj):
        return obj.name or obj.email
