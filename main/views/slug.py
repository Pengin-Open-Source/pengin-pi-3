import json
import os

from django.apps import apps
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin  # Replaces @method_decorator(login_required)

from .base import SuperTemplateView
from ..models import Slug
from main.forms.slug import SlugForm
from util.dynamic_render import render_dynamic_content
from util.security.ratelimit import RateLimitedPostMixin
from util.security.recaptcha import verify_recaptcha_token
from util.slug_content_form import build_json_content_form, serialize_content_form

# SlugForm fields always shown as the page "envelope" in slug_edit.html,
# regardless of whether the smart content form (util.slug_content_form) is
# active - everything else in SlugForm lives in that template's collapsible
# Advanced section instead. A real list (not a comma-joined string) so the
# template's {% if field.name in envelope_fields %} is exact membership,
# not substring matching.
ENVELOPE_FIELDS = ["name", "meta_tags", "meta_description"]


class SlugView(RateLimitedPostMixin, SuperTemplateView):
    """Renders whatever Slug matches the request path. Doesn't define a
    post() - nothing needs one today - but a Slug's own content
    (render_template/json) could embed a raw <form> that posts back to
    this same page, so dispatch() already stands ready for that: any
    POST is rate-limited unconditionally (RateLimitedPostMixin, harmless
    dead weight until a post() exists, real protection the moment one
    does), and additionally reCAPTCHA-gated when the resolved Slug has
    requires_recaptcha set (see that field's docstring on the model)."""
    ratelimit_rate = '30/m'

    def _resolve_slug(self, slug_path):
        """Looks up the Slug for a given path (empty/None resolves the
        root '/' to the 'home' slug); returns None if any segment
        doesn't resolve. Shared by get() (falls back to
        handle_missing_slug on a None) and dispatch() (checks
        requires_recaptcha before letting a POST through)."""
        slug_names = [s for s in (slug_path or "").strip("/").split("/") if s]
        if not slug_names:
            return Slug.objects.filter(parent=None, name='home').first()

        current_slug = None
        for name in slug_names:
            try:
                current_slug = Slug.objects.get(name=name, parent=current_slug)
            except (Slug.DoesNotExist, Slug.MultipleObjectsReturned):
                return None
        return current_slug

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST':
            current_slug = self._resolve_slug(kwargs.get('slug_path', ''))
            if current_slug and current_slug.requires_recaptcha:
                token = request.POST.get('g-recaptcha-response')
                if not verify_recaptcha_token(token):
                    messages.error(request, "Human verification failed. Please try again.")
                    return redirect(request.path)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, slug_path=""):
        current_slug = self._resolve_slug(slug_path)

        if not current_slug:
            return self.handle_missing_slug(request)

        # Base context provided to templates
        context = {
            "title": current_slug.name,
            "meta_tags": current_slug.meta_tags,
            "meta_description": current_slug.meta_description,
            "date": current_slug.date,
            "creator": current_slug.author,
            "is_admin": request.user.is_staff,
            "slug": current_slug,
        }

        # Retrieve JSON payload or schema dict
        raw_json = current_slug.json
        if isinstance(raw_json, str) and raw_json.strip():
            try:
                schema_data = json.loads(raw_json)
            except json.JSONDecodeError:
                schema_data = {}
        elif isinstance(raw_json, dict):
            schema_data = raw_json
        else:
            schema_data = {}

        # MODE A: Dynamic Schema Querying (e.g. {"datasource": {"app_label": "articles", "model": "Article"}})
        if "datasource" in schema_data:
            ds = schema_data["datasource"]
            try:
                TargetModel = apps.get_model(ds["app_label"], ds["model"])
                lookup_field = ds.get("lookup_field", "slug")
                lookup_val = ds.get("lookup_value", current_slug.name)
                
                target_instance = get_object_or_404(TargetModel, **{lookup_field: lookup_val})
                context_key = ds.get("context_key", "object")
                context[context_key] = target_instance
            except (LookupError, Exception):
                pass

        # MODE B: Generic Foreign Key Linkage
        elif current_slug.content_object:
            context["object"] = current_slug.content_object

        # MODE C: Static Textual Content Mode
        # Injects remaining raw top-level key/value pairs into context (e.g., {"interview_article": "# ..."})
        context.update(schema_data)

        # Template Resolving Logic - shared with main.models.event.Event,
        # which has the same template_name/render_template/json shape (see
        # util/dynamic_render.py).
        response = render_dynamic_content(
            request, current_slug.template_name, current_slug.render_template, context
        )
        return response if response is not None else HttpResponse("")

    def handle_missing_slug(self, request):
        path = request.path_info
        
        _, ext = os.path.splitext(path)
        if ext:
            raise Http404("Asset file not found")

        fetch_dest = request.META.get('HTTP_SEC_FETCH_DEST', '')
        if fetch_dest and fetch_dest not in ['document', 'empty', '']:
            raise Http404("Non-document asset not found")

        if request.user.is_authenticated and request.user.is_staff:
            return redirect("/slug/create")
            
        if request.user.is_authenticated:
            return HttpResponseForbidden("403 Forbidden")
            
        return redirect("/login")


class SlugCreateView(LoginRequiredMixin, RateLimitedPostMixin, View):
    #TODO: Enforce is_admin on view, not just LoginRequiredMixin
    ratelimit_rate = '10/m'  # Explicit rate limit per admin IP

    def get(self, request):
        form = SlugForm()
        return render(request, "slug/slug.html", {
            "form": form,
            "action": "create",
        })

    def post(self, request):
        form = SlugForm(request.POST)
        if form.is_valid():
            slug = form.save(commit=False)
            slug.author = request.user
            slug.save()
            return redirect("slug_edit", slug_id=slug.id)

        return render(request, "slug/slug.html", {
            "form": form,
            "action": "create",
        })


class SlugEditView(LoginRequiredMixin, RateLimitedPostMixin, View):
    """Static-slug edit. Beyond the raw SlugForm (name/parent/meta/
    template_name/render_template/is_dynamic/json), a non-dynamic Slug
    whose json is a plain content dict also gets a per-field form built
    fresh from that dict's current shape every time this view loads -
    see util.slug_content_form. That form is the primary editing UI;
    the raw fields (template_name/render_template/json) stay reachable
    as an "Advanced" fallback for changing the page's shape (adding/
    removing content keys, swapping templates) - saving from there
    re-derives the per-field form from the new shape on next load, no
    separate migration step. Which one a POST came from is disambiguated
    by the save_mode field on whichever submit button was clicked -
    everything else on the page (name/meta/parent/is_dynamic/
    template_name/render_template) applies either way; only `json`
    itself has two competing sources of truth to resolve."""
    ratelimit_rate = '20/m'

    def _content_form(self, slug, data_post=None):
        if slug.is_dynamic:
            return None
        return build_json_content_form(
            slug.json, template_name=slug.template_name, render_template=slug.render_template,
            data_post=data_post)

    def get(self, request, slug_id):
        slug = get_object_or_404(Slug, id=slug_id)
        form = SlugForm(instance=slug)
        content_form = self._content_form(slug)

        return render(request, "slug/slug_edit.html", {
            "form": form,
            "content_form": content_form,
            "slug": slug,
            "action": "edit",
            "envelope_fields": ENVELOPE_FIELDS,
        })

    def post(self, request, slug_id):
        slug = get_object_or_404(Slug, id=slug_id)
        form = SlugForm(request.POST, instance=slug)
        content_form = self._content_form(slug, data_post=request.POST)
        save_mode = request.POST.get('save_mode', 'advanced')

        content_ok = content_form is None or content_form.is_valid()

        if form.is_valid() and content_ok:
            slug.save_history(user=request.user)
            slug = form.save(commit=False)

            if save_mode == 'content' and content_form is not None:
                slug.json = serialize_content_form(content_form, slug.json, uploaded_files=request.FILES)

            slug.save()
            return redirect("slug_edit", slug_id=slug.id)

        return render(request, "slug/slug_edit.html", {
            "form": form,
            "content_form": content_form,
            "slug": slug,
            "action": "edit",
            "envelope_fields": ENVELOPE_FIELDS,
        })


class SlugDeleteView(LoginRequiredMixin, RateLimitedPostMixin, View):
    ratelimit_rate = '5/m'

    def post(self, request, slug_id):
        slug = get_object_or_404(Slug, id=slug_id)
        slug.delete()
        return redirect("slug_list")