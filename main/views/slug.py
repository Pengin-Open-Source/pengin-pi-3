import json
from django.http import HttpResponse
from django.template import Template, Context, RequestContext
from django.template.loader import get_template
from django.shortcuts import get_object_or_404
from .base import SuperTemplateView
from ..models import Slug
from django.views import View
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from main.forms.slug import SlugForm
from django.http import HttpResponseForbidden


class SlugView(SuperTemplateView):
    def get(self, request, slug_path=""):
        slug_names = [s for s in slug_path.strip("/").split("/") if s]
        current_slug = None

        if not slug_names:  # Handle root URL ("/")
            try:
                # Conventionally, the root slug might be named 'home' or have a specific flag.
                # Here, we'll just try to find a root slug. This might need refinement
                # if multiple root slugs exist.
                current_slug = Slug.objects.get(parent=None, name='home') # Or some other default
            except Slug.DoesNotExist:
                return self.handle_missing_slug(request)
        else:
            for name in slug_names:
                try:
                    # Use case-sensitive lookup for slug names
                    current_slug = Slug.objects.get(name=name, parent=current_slug)
                except (Slug.DoesNotExist, Slug.MultipleObjectsReturned):
                    return self.handle_missing_slug(request)

        if not current_slug:
            return self.handle_missing_slug(request)

        context = {
            "title": current_slug.name,
            "meta_tags": current_slug.meta_tags,
            "meta_description": current_slug.meta_description,
            "date": current_slug.date,
            "creator": current_slug.author,
            "is_admin": request.user.is_staff,
        }

        template_obj = None
        is_from_string = False

        # If render_template is provided, it's the primary source.
        # It can optionally extend a template from template_name.
        if current_slug.render_template:
            template_string = current_slug.render_template
            try:
                # If render_template contains JSON, it's for block content.
                # We'll inject it into the template specified by template_name.
                blocks = json.loads(template_string)
                context.update(blocks)
                if not current_slug.template_name:
                    # Default to a simple template if none is specified
                    template_obj = Template("{{ main|safe }}")
                    is_from_string = True
                else:
                    template_obj = get_template(current_slug.template_name)
            except json.JSONDecodeError:
                # The render_template is a full Django template string.
                template_obj = Template(template_string)
                is_from_string = True
        elif current_slug.template_name:
            # Only a static template is provided.
            template_obj = get_template(current_slug.template_name)
        else:
            # No template information, return empty response or an error.
            return HttpResponse("")

        if is_from_string:
            # For templates from strings, use RequestContext to make it request-aware.
            rendered = template_obj.render(RequestContext(request, context))
        else:
            # For templates from get_template(), the render method accepts the request directly.
            rendered = template_obj.render(context, request)

        return HttpResponse(rendered)

    def handle_missing_slug(self, request):
        if request.user.is_authenticated:
            if request.user.is_staff:
                return redirect("/slug/create")
            return HttpResponseForbidden("403 Forbidden")
        return redirect("/login")


@method_decorator(login_required, name="dispatch")
class SlugCreateView(View):
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
            slug.save()  # no history on create
            return redirect("slug_edit", slug_id=slug.id)

        return render(request, "slug/slug.html", {
            "form": form,
            "action": "create",
        })


@method_decorator(login_required, name="dispatch")
class SlugEditView(View):
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
            slug.save(user=request.user)  # history snapshot
            return redirect("slug_edit", slug_id=slug.id)

        return render(request, "slug/slug_edit.html", {
            "form": form,
            "slug": slug,
            "action": "edit",
        })



@method_decorator(login_required, name="dispatch")
class SlugDeleteView(View):
    def post(self, request, slug_id):
        slug = get_object_or_404(Slug, id=slug_id)
        slug.delete()
        return redirect("slug_list")
