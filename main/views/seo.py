# main/views/seo.py
from django.http import HttpResponse
from django.urls import reverse
from main.models import RobotsRule


def robots_txt(request):
    rules = RobotsRule.objects.all()
    lines = []
    current_agent = None

    for rule in rules:
        if rule.user_agent != current_agent:
            lines.append(f"User-agent: {rule.user_agent}")
            current_agent = rule.user_agent
        directive = "Allow" if rule.allow else "Disallow"
        lines.append(f"{directive}: {rule.path}")

    # Fallback default if no rules are defined in the DB yet
    if not lines:
        lines = [
            "User-agent: *",
            "Disallow: /admin/",
            "Disallow: /login/",
            "Disallow: /slug/",
        ]

    # Append absolute URL for dynamic sitemap.xml
    sitemap_url = request.build_absolute_uri(reverse('sitemap'))
    lines.append(f"\nSitemap: {sitemap_url}")

    return HttpResponse("\n".join(lines), content_type="text/plain")