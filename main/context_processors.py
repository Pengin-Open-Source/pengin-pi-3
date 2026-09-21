# main/context_processors.py
from util.defaults import default
from .models import Site


def site_context(request):
    """
    Exposes the site's own identity (company name, address, phone, social
    links) as `site` in every template's context. This is what
    templates/nav_bar.html, footer_bar.html, layout.html and copyright.html
    read instead of hardcoding a company name - and what a page's view can
    build util.seo.build_organization_schema(site) from for JSON-LD.
    """
    return {'site': Site.objects.first() or default.Site()}


def navigation_context(request):
    """
    Small nav-chrome flags read by templates/nav_bar.html - manages_team,
    for a "My Team" link (main.auth.get_managed_groups(user) is non-empty
    for anyone with Manager-tier authority over at least one department,
    including the two site-wide departments), and is_site_executive, for
    the Executive-tier "Manage Users" link. Deliberately doesn't compute
    anything about an app's own models (e.g. an active-jobs flag) - core
    main has no dependency on any app being installed, so a flag like that
    belongs in the app's own context processor instead.
    """
    from main.auth import get_managed_groups, is_executive_manager
    manages_team = bool(request.user.is_authenticated and get_managed_groups(request.user).exists())
    return {
        'manages_team': manages_team,
        'is_site_executive': is_executive_manager(request.user),
    }
