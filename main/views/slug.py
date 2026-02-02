import json
from django.http import HttpResponse
from django.template import Template, Context
from django.template.loader import get_template
from django.shortcuts import get_object_or_404
from .base import SuperTemplateView
from ..models import Slug


class SlugView(SuperTemplateView):
    def get(self, request, slug_path=""):
        slug_names = slug_path.strip("/").split("/")
        current_slug = None

        for name in slug_names:
            current_slug = get_object_or_404(
                Slug, name=name, parent=current_slug
            )

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
