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
