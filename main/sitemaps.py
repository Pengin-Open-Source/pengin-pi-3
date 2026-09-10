import fnmatch
from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import AnonymousUser
from django.contrib.sitemaps import Sitemap
from django.test import RequestFactory
from django.urls import reverse, get_resolver, resolve, Resolver404, URLPattern, URLResolver
from main.models import Slug, RobotsRule
from main.models.mixins import SitemapEntry

_PROBE_FACTORY = RequestFactory()


def _returns_redirect(path):
    """True if a bare, anonymous GET to `path` resolves to a view that
    returns a 3xx - Google Search Console flags any sitemap URL that
    redirects instead of resolving directly ("Sitemap contains a
    redirect"), so a URL like this shouldn't be advertised even though
    it resolves to a real view and isn't login-gated. This is generic by
    design (probes the actual response instead of requiring every
    redirecting view to be named/marked one-by-one) because a redirect
    can come from anywhere - an unnamed `path('', lambda request:
    redirect(...))` alias (invisible to both the ignored_names set and
    _requires_login, since it's neither named nor gated) or a view
    class whose dispatch() redirects unauthenticated/unqualified users
    elsewhere entirely (also invisible to _requires_login's mixin/marker
    checks, since that's arbitrary imperative logic, not a mixin or a
    decorator).

    Best-effort probe, not a full request: no session/messages
    middleware is attached (a bare RequestFactory request doesn't get
    them), so a view that touches request.session/request._messages
    before it would otherwise redirect raises instead - caught and
    treated as "not a redirect" (fails open) rather than risking a
    false positive that hides a page that's actually fine. A wrongly
    included redirect is a minor sitemap warning; a wrongly excluded
    real page is a bigger loss."""
    try:
        match = resolve(path)
    except Resolver404:
        return False
    try:
        request = _PROBE_FACTORY.get(path)
        request.user = AnonymousUser()
        response = match.func(request, *match.args, **match.kwargs)
        return 300 <= getattr(response, 'status_code', 200) < 400
    except Exception:
        return False


def _get_robots_rules():
    return list(RobotsRule.objects.all())


def _normalize(path):
    path = (path or '').strip()
    if not path.startswith('/'):
        path = f'/{path}'
    return '/' + path.strip('/') + '/' if path.strip('/') else '/'


def is_disallowed(path, rules=None):
    if not path:
        return False

    clean_path = _normalize(path)
    rules = _get_robots_rules() if rules is None else rules
    if not rules:
        return False

    best = None  # (specificity, allow)
    for rule in rules:
        rule_path = (rule.path or '').strip()
        if not rule_path:
            continue

        if '*' in rule_path:
            pattern = rule_path if rule_path.startswith(('*', '/')) else f'*{rule_path}*'
            if not fnmatch.fnmatch(clean_path, pattern):
                continue
        else:
            norm_rule = _normalize(rule_path)
            if not (clean_path == norm_rule or clean_path.startswith(norm_rule)):
                continue

        # Specificity = length of the rule exactly as authored. This matches
        # Google's robots.txt precedence rules: longest matching pattern
        # wins; ties favor Allow. Comparing raw length (not a normalized/
        # stripped version) is what makes the units comparable across
        # wildcard and prefix rules.
        specificity = len(rule_path)
        if best is None or specificity > best[0] or (specificity == best[0] and rule.allow):
            best = (specificity, rule.allow)

    return best is not None and not best[1]


def collect_static_routes(urlpatterns, prefix=''):
    routes = []
    for pattern in urlpatterns:
        if isinstance(pattern, URLResolver):
            if pattern.namespace == 'admin' or str(pattern.pattern).startswith('admin'):
                continue
            new_prefix = f"{prefix}{pattern.namespace}:" if pattern.namespace else prefix
            routes.extend(collect_static_routes(pattern.url_patterns, new_prefix))
        elif isinstance(pattern, URLPattern) and pattern.name:
            if '<' in str(pattern.pattern):
                continue
            routes.append((f"{prefix}{pattern.name}", pattern.callback))
    return routes


def _requires_login(callback):
    """
    True if a resolved view requires an authenticated user - lets the
    sitemap generically skip any app's login-gated create/edit/"my stuff"
    pages without every app having to be named one-by-one in ignored_names
    below. Two independent gating styles are detected:
      - A class-based view with LoginRequiredMixin anywhere in its MRO.
      - A view (function-based, or a CBV decorated via
        @method_decorator(is_admin_required, name='dispatch') /
        @is_admin_required directly) wrapped by one of main.auth.decorators'
        real access-gating decorators (group_required, is_admin_required),
        which mark their wrapped function with `.requires_auth = True` for
        exactly this reason - see main/auth/decorators.py. is_admin_provider
        and user_group_provider are NOT gates (they just pass extra
        context, never block), so they're deliberately not marked and
        won't trip this check.
    """
    view_class = getattr(callback, 'view_class', None)
    if view_class is not None and issubclass(view_class, LoginRequiredMixin):
        return True
    if getattr(callback, 'requires_auth', False):
        return True
    if view_class is not None and getattr(view_class.dispatch, 'requires_auth', False):
        return True
    return False


class StaticAppSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        resolver = get_resolver()
        all_routes = collect_static_routes(resolver.url_patterns)
        rules = _get_robots_rules()

        ignored_names = {
            'robots_txt', 'sitemap', 'login', 'logout', 'signup',
            'profile', 'slug', 'slug_edit', 'slug_delete',
            'generate_prt', 'reset_password', 'edit_password',
            'send_validation_email', 'validate_account'
        }

        valid_routes, seen_paths = [], set()
        for route_name, callback in all_routes:
            base_name = route_name.split(':')[-1]
            if base_name in ignored_names or route_name in ignored_names:
                continue
            if _requires_login(callback):
                continue
            try:
                path = reverse(route_name)
            except Exception:
                continue
            if is_disallowed(path, rules=rules) or path in seen_paths:
                continue
            if _returns_redirect(path):
                continue
            valid_routes.append(route_name)
            seen_paths.add(path)
        return valid_routes

    def location(self, item):
        return reverse(item)


class SlugDatabaseSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'daily'
    priority = 0.8

    def items(self):
        rules = _get_robots_rules()
        allowed = []
        for slug in Slug.objects.all():
            try:
                url = slug.get_absolute_url()
            except Exception:
                continue
            if url and not is_disallowed(url, rules=rules) and not _returns_redirect(url):
                allowed.append(slug)
        return allowed

    def lastmod(self, obj):
        return getattr(obj, 'updated_at', getattr(obj, 'date', None))

    def location(self, obj):
        return obj.get_absolute_url()


class DynamicAppSitemap(Sitemap):
    """
    Sitemaps every model that explicitly subclasses SitemapEntry (Product,
    Job, ...). Nothing appears here just because it happens to define
    get_absolute_url — see main/models/mixins.py.
    """
    protocol = 'https'
    changefreq = 'daily'
    priority = 0.7

    def items(self):
        rules = _get_robots_rules()
        items = []
        for model in apps.get_models():
            if not (isinstance(model, type) and issubclass(model, SitemapEntry)):
                continue
            for obj in model.objects.all():
                try:
                    url = obj.get_absolute_url()
                except Exception:
                    continue
                if url and not is_disallowed(url, rules=rules) and not _returns_redirect(url):
                    items.append(obj)
        return items

    def location(self, obj):
        return obj.get_absolute_url()

    def lastmod(self, obj):
        field = getattr(obj, 'sitemap_lastmod_field', None)
        return getattr(obj, field, None) if field else None