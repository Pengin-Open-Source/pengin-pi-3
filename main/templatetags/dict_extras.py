# main/templatetags/dict_extras.py
# Django's template dot-lookup (dict.key) only works for a literal key -
# templates/slug/slug_dynamic_form.html needs to look a dynamic form
# field's name up in existing_data (a plain dict) inside a {% for %} loop,
# where the key is itself a variable.
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)
