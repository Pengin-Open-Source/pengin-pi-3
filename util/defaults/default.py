# Pengin-Pi-3 — Pengin Open Source
# util/defaults/default.py
#
# Empty placeholder objects used when a Site, Home or
# About record doesn't exist yet.
#
# Copyright (C) 2026 Tobu Pengin, L.L.C. and contributors
# Authors:
#   Stuart Anderson <stuart@tobupengin.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
class Home:
    company_name = ""
    article = ""
    image = ""


class About:
    name = ""
    article = "No company description available"
    image = ""


class Site:
    company_name = ""
    tagline = ""
    address1 = ""
    address2 = ""
    city = ""
    state = ""
    zipcode = ""
    country = ""
    google_maps_url = ""
    phone = ""
    webmaster = ""
    facebook = ""
    twitter = ""
    instagram = ""
    linkedin = ""
    youtube = ""


image = "/static/images/test.png"
