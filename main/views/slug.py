import json
import os

from django.apps import apps
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin  # Replaces @method_decorator(login_required)

from .base import SuperTemplateView
from ..models import Slug
from main.forms.slug import SlugForm
from util.dynamic_render import render_dynamic_content
from util.security.ratelimit import RateLimitedPostMixin


class SlugView(SuperTemplateView):
    def get(self, request, slug_path=""):
        slug_names = [s for s in slug_path.strip("/").split("/") if s]
        current_slug = None

        if not slug_names:  # Handle root URL ("/")
            try:
                current_slug = Slug.objects.get(parent=None, name='home')
            except Slug.DoesNotExist:
                return self.handle_missing_slug(request)
        else:
            for name in slug_names:
                try:
                    current_slug = Slug.objects.get(name=name, parent=current_slug)
                except (Slug.DoesNotExist, Slug.MultipleObjectsReturned):
                    return self.handle_missing_slug(request)

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
    ratelimit_rate = '20/m'

    def get(self, request, slug_id):
        slug = get_object_or_404(Slug, id=slug_id)
        form = SlugForm(instance=slug)

        return render(request, "slug/slug_edit.html", {
            "form": form,
            "slug": slug,
            "action": "edit",
        })

    def post(self, request, slug_id):
        slug = get_object_or_404(Slug, id=slug_id)
        form = SlugForm(request.POST, instance=slug)

        if form.is_valid():
            slug = form.save(commit=False)
            slug.save_history(user=request.user)
            slug.save()
            return redirect("slug_edit", slug_id=slug.id)

        return render(request, "slug/slug_edit.html", {
            "form": form,
            "slug": slug,
            "action": "edit",
        })


class SlugDeleteView(LoginRequiredMixin, RateLimitedPostMixin, View):
    ratelimit_rate = '5/m'

    def post(self, request, slug_id):
        slug = get_object_or_404(Slug, id=slug_id)
        slug.delete()
        return redirect("slug_list")