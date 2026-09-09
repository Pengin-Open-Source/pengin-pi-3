# util/dynamic_render.py
# The Slug-style "let an editor give this row a custom page" pattern -
# originally only main.views.slug.SlugView, now shared with the Event model
# (main.models.event.Event has the same template_name/render_template/json
# field shape) so any future model that wants the same "usually a standard
# page, optionally a fully custom one" behavior can reuse this instead of
# re-deriving the resolution algorithm per app.
import json

from django.http import HttpResponse
from django.template import Template, RequestContext
from django.template.loader import get_template


def render_dynamic_content(request, template_name, render_template, context):
    """Resolves a row's template_name/render_template fields into an
    HttpResponse, exactly like main.views.slug.SlugView.get() does for a
    Slug. Returns None if neither field is set - the caller decides its own
    fallback in that case (an empty response for Slug, a standard detail
    template for Event).

    If render_template holds valid JSON, its keys are merged into `context`
    (mutated in place) as a legacy blocks mechanism; if template_name is
    also set, that named template is rendered with the merged context.
    Otherwise render_template is compiled directly as raw template markup -
    if template_name is set and render_template doesn't already start with
    its own {% extends %}, one is auto-prepended so naming a template
    actually fills its blocks (see the SlugView fix this mirrors).
    """
    template_obj = None
    is_from_string = False

    if render_template:
        template_string = render_template
        try:
            blocks = json.loads(template_string)
            if isinstance(blocks, dict):
                context.update(blocks)
            if not template_name:
                template_obj = Template("{{ main|safe }}")
                is_from_string = True
            else:
                template_obj = get_template(template_name)
        except json.JSONDecodeError:
            if template_name and not template_string.lstrip().startswith('{% extends'):
                template_string = f'{{% extends "{template_name}" %}}\n{template_string}'
            template_obj = Template(template_string)
            is_from_string = True
    elif template_name:
        template_obj = get_template(template_name)
    else:
        return None

    if is_from_string:
        rendered = template_obj.render(RequestContext(request, context))
    else:
        rendered = template_obj.render(context, request)
    return HttpResponse(rendered)
