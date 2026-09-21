# main/views/wiki.py
# Wiki pages are plain Slugs (Slug.wiki_root/wiki_body - see
# main/models/slug.py) rendered through a wiki-specific layout instead of
# template_name/render_template/json. SlugView.get() delegates here the
# moment it resolves a Slug with wiki_root_id set - the URL resolution
# itself is unchanged, still the same catch-all path walk every other
# Slug uses.
#
# Three URL entry points, registered in main/urls.py BEFORE the plain
# catch-all so they take priority for these specific suffixes:
#   <path:base_path>/wiki/create/  - turn any existing (non-wiki) Slug into
#                                    the root of a brand new wiki, one child
#                                    page at a time - "create a wiki on a
#                                    whim" starts here.
#   <path:base_path>/create/       - add a new child page under an
#                                    existing wiki page (including the
#                                    root) - reached from the "+ New Page"
#                                    link on wiki/page.html, or from
#                                    clicking a missing [[Wiki Link]].
#   <path:base_path>/edit/         - edit an existing wiki page's name/body
#                                    in place.
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.text import slugify
from django.views import View

from ..models import Slug
from ..models.slug import SlugHistory
from util.security.ratelimit import RateLimitedPostMixin
from util.wiki_markdown import render_wiki_markdown


def display_name(slug_name):
    """Slug.save() only lowercases `name` - it doesn't slugify spaces to
    hyphens, since ordinary (non-wiki) pages are given short one-word
    names by whoever creates them and never hit this. Wiki article titles
    are naturally multi-word, so the wiki views slugify on write (clean
    URLs, no literal spaces/%20) and reconstruct a human-readable label
    for display with this, rather than adding a separate title field."""
    return slug_name.replace("-", " ").strip()


def _resolve_slug_path(base_path):
    """Same walk as SlugView._resolve_slug (including its empty-path ->
    'home' fallback, so a wiki can be hung directly off the site root) -
    duplicated rather than imported to avoid a circular import (slug.py
    will import from this module too, to call render_wiki_page)."""
    slug_names = [s for s in (base_path or "").strip("/").split("/") if s]
    if not slug_names:
        return Slug.objects.filter(parent=None, name="home").first()

    current_slug = None
    for name in slug_names:
        try:
            current_slug = Slug.objects.get(name=name, parent=current_slug)
        except (Slug.DoesNotExist, Slug.MultipleObjectsReturned):
            return None
    return current_slug


def _wikilink_resolver(current_slug):
    """Builds the resolve_wikilink(target) -> (url, exists) closure for
    one specific page's render - a missing link's create-URL is scoped to
    THIS page as the new page's parent (the page containing the link is
    the natural place to hang a new child off of), not always the wiki
    root."""
    wiki_root = current_slug.wiki_root

    def resolve(target):
        page = wiki_root.wiki_pages.filter(name=slugify(target)).first()
        if page:
            return page.get_absolute_url(), True
        create_url = current_slug.get_absolute_url() + f"create/?name={target}"
        return create_url, False

    return resolve


def render_wiki_page(request, slug):
    """Called from SlugView.get() for any resolved Slug with
    wiki_root_id set."""
    wiki_root = slug.wiki_root
    article_html, toc = render_wiki_markdown(slug.wiki_body, _wikilink_resolver(slug))

    # Breadcrumb: walk up to (and including) the wiki root - the same
    # ancestry Slug.get_absolute_url() already walks, just kept as objects
    # here instead of collapsed into a URL string.
    breadcrumb = []
    node = slug
    while node:
        breadcrumb.append(node)
        if node.id == wiki_root.id:
            break
        node = node.parent
    breadcrumb.reverse()

    child_pages = slug.children.filter(wiki_root=wiki_root).order_by("name")

    last_edit, maintainers = _editors_for(slug)

    return render(request, "wiki/page.html", {
        "slug": slug,
        "display_name": display_name(slug.name),
        "wiki_root": wiki_root,
        "wiki_root_display_name": display_name(wiki_root.name),
        "article_html": article_html,
        "toc": toc,
        "breadcrumb": [(crumb, display_name(crumb.name)) for crumb in breadcrumb],
        "child_pages": [(child, display_name(child.name)) for child in child_pages],
        "last_edit": last_edit,
        "maintainers": maintainers,
        "is_admin": request.user.is_staff,
        "title": display_name(slug.name),
        "meta_description": slug.meta_description,
        "primary_title": display_name(slug.name),
    })


def _editors_for(slug):
    """Returns (last_edit, maintainers):
      - last_edit: the most recent SlugHistory row for this page (its
        `user`/`changed_at` record who made THAT edit and when - the
        snapshot it carries is the PRE-edit state, but the user/timestamp
        themselves describe the edit that produced the page's current
        content), or None if the page has never been edited since it was
        created.
      - maintainers: one entry per distinct person who has ever touched
        this page - every save_history() caller plus the original author
        (who has no History row of their own, since save_history() is
        never called on create) - each with their own most recent edit
        to this specific page, newest first. A maintainer who only ever
        created the page (never edited it since) shows their creation
        date instead of an edit date.
    """
    history_qs = (
        SlugHistory.objects.filter(object=slug)
        .exclude(user=None)
        .select_related("user")
        .order_by("-changed_at")
    )
    last_edit = history_qs.first()

    last_edit_by_user = {}
    for row in history_qs:
        last_edit_by_user.setdefault(row.user_id, row)

    maintainers = [
        {"user": row.user, "last_activity": row.changed_at, "is_creator": row.user_id == slug.author_id}
        for row in last_edit_by_user.values()
    ]
    if slug.author_id and slug.author_id not in last_edit_by_user:
        maintainers.append({"user": slug.author, "last_activity": slug.date, "is_creator": True})

    maintainers.sort(key=lambda m: m["last_activity"], reverse=True)
    return last_edit, maintainers


class WikiRootCreateView(LoginRequiredMixin, RateLimitedPostMixin, View):
    """<path:base_path>/wiki/create/ - base_path must resolve to an
    existing Slug that ISN'T already part of a wiki; the new page becomes
    a child of it and the root of a brand new wiki tree.

    At the literal site root (base_path=''), the new page gets parent=None
    - a genuine top-level Slug, same as 'home' and any other root page -
    rather than being nested under 'home'. 'home' is just the one Slug
    that happens to answer '/' (Slug.get_absolute_url()'s own special
    case); it isn't a namespace everything at the root should live under,
    so a wiki started from '/' should resolve at /docs/, not /home/docs/.
    """
    ratelimit_rate = "10/m"

    def get(self, request, base_path):
        base_slug = self._require_base(base_path)
        return render(request, "wiki/create.html", {
            "base_slug": base_slug,
            "base_display_name": display_name(base_slug.name) if base_slug else "the site root",
            "mode": "root", "primary_title": "Start a New Wiki",
        })

    def post(self, request, base_path):
        base_slug = self._require_base(base_path)
        raw_name = request.POST.get("name", "").strip()
        name = slugify(raw_name)
        wiki_body = request.POST.get("wiki_body", "")

        if not name:
            return render(request, "wiki/create.html", {
                "base_slug": base_slug, "mode": "root", "primary_title": "Start a New Wiki",
                "error": "Page name is required.",
            })

        # A single save works even though wiki_root points at this same
        # row: the pk is already populated in memory (UUID default=), and
        # Postgres's (non-deferred) FK trigger checks referential
        # integrity at end-of-statement, by which point the row already
        # exists - confirmed directly, see the wiki design discussion.
        page = Slug(
            name=name, parent=base_slug, meta_tags="", meta_description="",
            wiki_body=wiki_body, author=request.user,
        )
        page.wiki_root = page
        page.save()
        return redirect(page.get_absolute_url())

    def _require_base(self, base_path):
        # Empty base_path means "the literal site root" - return None
        # (a true top-level parent) rather than resolving to 'home' the
        # way _resolve_slug_path does for other views, where an empty
        # path genuinely does mean "the home Slug itself".
        if not base_path:
            return None
        base_slug = _resolve_slug_path(base_path)
        if base_slug is None:
            raise Http404("No such page.")
        return base_slug


class WikiPageCreateView(LoginRequiredMixin, RateLimitedPostMixin, View):
    """<path:base_path>/create/ - base_path must resolve to an EXISTING
    wiki page (including a wiki root); the new page becomes its child,
    inheriting the same wiki_root."""
    ratelimit_rate = "20/m"

    def get(self, request, base_path):
        parent_slug = self._require_wiki_page(base_path)
        initial_name = request.GET.get("name", "")
        return render(request, "wiki/create.html", {
            "base_slug": parent_slug, "base_display_name": display_name(parent_slug.name),
            "base_wiki_root_display_name": display_name(parent_slug.wiki_root.name),
            "mode": "page", "initial_name": initial_name,
            "primary_title": f"New Page in {display_name(parent_slug.wiki_root.name)}",
        })

    def post(self, request, base_path):
        parent_slug = self._require_wiki_page(base_path)
        raw_name = request.POST.get("name", "").strip()
        name = slugify(raw_name)
        wiki_body = request.POST.get("wiki_body", "")

        if not name:
            return render(request, "wiki/create.html", {
                "base_slug": parent_slug, "mode": "page",
                "primary_title": f"New Page in {parent_slug.wiki_root.name}",
                "error": "Page name is required.",
            })

        page = Slug(
            name=name, parent=parent_slug, wiki_root=parent_slug.wiki_root,
            meta_tags="", meta_description="", wiki_body=wiki_body, author=request.user,
        )
        page.save()
        return redirect(page.get_absolute_url())

    def _require_wiki_page(self, base_path):
        slug = _resolve_slug_path(base_path)
        if slug is None or not slug.is_wiki_page:
            raise Http404("No such wiki page.")
        return slug


class WikiPageEditView(LoginRequiredMixin, RateLimitedPostMixin, View):
    """<path:base_path>/edit/ - edit an existing wiki page's name/body."""
    ratelimit_rate = "20/m"

    def get(self, request, base_path):
        slug = self._require_wiki_page(base_path)
        return render(request, "wiki/edit.html", {
            "slug": slug, "slug_display_name": display_name(slug.name),
            "primary_title": f"Edit {display_name(slug.name)}",
        })

    def post(self, request, base_path):
        slug = self._require_wiki_page(base_path)
        raw_name = request.POST.get("name", "").strip()
        name = slugify(raw_name)
        wiki_body = request.POST.get("wiki_body", "")

        if not name:
            return render(request, "wiki/edit.html", {
                "slug": slug, "primary_title": f"Edit {slug.name}",
                "error": "Page name is required.",
            })

        # Always an edit here - _resolve_slug_path only returns an
        # already-existing Slug, never a fresh one, so no _state.adding
        # guard is needed the way formset loops elsewhere in this project
        # require (see NOTE_HISTORY_FK_BUG.md).
        slug.save_history(user=request.user)
        slug.name = name
        slug.wiki_body = wiki_body
        slug.save()
        return redirect(slug.get_absolute_url())

    def _require_wiki_page(self, base_path):
        slug = _resolve_slug_path(base_path)
        if slug is None or not slug.is_wiki_page:
            raise Http404("No such wiki page.")
        return slug
