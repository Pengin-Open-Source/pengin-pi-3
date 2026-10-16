# Pengin-Pi-3 — Pengin Open Source
# util/context_processors.py
#
# Template context processor that exposes the reCAPTCHA site key to every page.
#
# Copyright (C) 2026 Tobu Pengin, L.L.C. and contributors
# Authors:
#   Stuart Anderson <stuart@tobupengin.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import os


def recaptcha_context(request):
    """
    Automatically injects 'site_key' into all template contexts site-wide.
    """
    return {
        'site_key': os.getenv('RECAPTCHA_SITE_KEY', '')
    }