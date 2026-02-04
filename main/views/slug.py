import json
from django.http import HttpResponse
from django.template import Template, Context
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

        for name in slug_names:
            try:
                current_slug = Slug.objects.get(
                    name=name,
                    parent=current_slug
                )
            except Slug.DoesNotExist:
                return self.handle_missing_slug(request)

        # Handle root ("/") with no slugs defined
        if not slug_names and not current_slug:
            try:
                current_slug = Slug.objects.get(parent=None)
            except Slug.DoesNotExist:
                return self.handle_missing_slug(request)

        context = {
            "title": current_slug.name,
            "meta_tags": current_slug.meta_tags,
            "meta_description": current_slug.meta_description,
            "date": current_slug.date,
            "creator": current_slug.author,
            "is_admin": request.user.is_staff,
        }

        rendered = ""

        if current_slug.template_name:
            static_template = get_template(current_slug.template_name)
            rendered = static_template.render(context, request)

        if current_slug.render_template:
            try:
                blocks = json.loads(current_slug.render_template)
                context.update(blocks)
            except json.JSONDecodeError:
                context["main"] = current_slug.render_template

            dynamic_template = Template(rendered or "{{ main|safe }}")
            rendered = dynamic_template.render(Context(context))

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
