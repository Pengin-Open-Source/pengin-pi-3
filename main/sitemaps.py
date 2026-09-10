import fnmatch
from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.sitemaps import Sitemap
from django.urls import reverse, get_resolver, URLPattern, URLResolver
from main.models import Slug, RobotsRule
from main.models.mixins import SitemapEntry


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
    True if a resolved view's class-based view requires an authenticated
    user (LoginRequiredMixin anywhere in its MRO) - lets the sitemap
    generically skip any app's login-gated create/edit/"my stuff" pages
    without every app having to be named one-by-one in ignored_names below.
    Function-based views aren't introspectable this way and fall through
    to ignored_names instead.
    """
    view_class = getattr(callback, 'view_class', None)
    if view_class is None:
        return False
    return issubclass(view_class, LoginRequiredMixin)


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
            if url and not is_disallowed(url, rules=rules):
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
                if url and not is_disallowed(url, rules=rules):
                    items.append(obj)
        return items

    def location(self, obj):
        return obj.get_absolute_url()

    def lastmod(self, obj):
        field = getattr(obj, 'sitemap_lastmod_field', None)
        return getattr(obj, field, None) if field else None