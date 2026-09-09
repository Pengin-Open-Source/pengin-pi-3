# blogs/templatetags/blog_tags.py
from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def toggle_tag_url(context, tag_name):
    request = context['request']
    get_dict = request.GET.copy()

    # Remove pagination when filter state changes
    if 'page' in get_dict:
        del get_dict['page']

    current_tags = get_dict.getlist('tag')

    if tag_name in current_tags:
        # Untoggle tag
        current_tags.remove(tag_name)
    else:
        # Toggle tag
        current_tags.append(tag_name)

    get_dict.setlist('tag', current_tags)

    query_string = get_dict.urlencode()
    return f"?{query_string}" if query_string else "?"
