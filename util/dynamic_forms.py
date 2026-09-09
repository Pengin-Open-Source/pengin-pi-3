# util/dynamic_forms.py
# Builds a plain Django Form class at request time from a JSON Schema
# (validated as structurally sound by util/json_schema.py before it ever
# gets here - this module assumes `schema` is already a valid JSON Schema
# document). Deliberately a small hand-rolled mapping rather than a
# generic low-code form-builder library: the field vocabulary a JSON
# Schema property can reasonably ask for is bounded (text, number, date,
# boolean, choice, file/image), and we already have full control of
# Django's own form machinery, so a 3rd-party dependency isn't buying
# anything here.
#
# Schema shape expected: a top-level object schema, e.g.
#   {
#     "type": "object",
#     "required": ["title"],
#     "properties": {
#       "title": {"type": "string", "title": "Title"},
#       "body": {"type": "string", "format": "textarea"},
#       "published_on": {"type": "string", "format": "date"},
#       "featured": {"type": "boolean"},
#       "priority": {"type": "integer", "minimum": 0},
#       "category": {"type": "string", "enum": ["news", "guide"]},
#       "cover_image": {"type": "string", "format": "image"},
#       "attachment": {"type": "string", "format": "file"}
#     }
#   }
#
# `format` is the one non-standard-but-JSON-Schema-legal extension point
# used here beyond the base "type" keyword - JSON Schema itself defines
# `format` as an open, implementation-defined annotation, so "textarea",
# "image", and "file" are legitimate uses of it, not a violation of the
# spec.
import datetime

from django import forms

from util.file import get_file_handler


def _base_kwargs(name, prop, required):
    return {
        'label': prop.get('title', name.replace('_', ' ').title()),
        'help_text': prop.get('description', ''),
        'required': required,
    }


def _build_field(name, prop, required):
    prop_type = prop.get('type', 'string')
    fmt = prop.get('format')
    enum = prop.get('enum')
    kwargs = _base_kwargs(name, prop, required)

    if enum is not None:
        choices = [(v, v) for v in enum]
        if not required:
            choices = [('', '---------')] + choices
        return forms.ChoiceField(choices=choices, **kwargs)

    if prop_type == 'boolean':
        # Checkboxes can't be "required" the way other fields can (an
        # unchecked required checkbox would make the box mandatory to
        # check on every submit) - always optional at the field level.
        kwargs['required'] = False
        return forms.BooleanField(**kwargs)

    if prop_type == 'integer':
        field_kwargs = dict(kwargs)
        if 'minimum' in prop:
            field_kwargs['min_value'] = prop['minimum']
        if 'maximum' in prop:
            field_kwargs['max_value'] = prop['maximum']
        return forms.IntegerField(**field_kwargs)

    if prop_type == 'number':
        field_kwargs = dict(kwargs)
        if 'minimum' in prop:
            field_kwargs['min_value'] = prop['minimum']
        if 'maximum' in prop:
            field_kwargs['max_value'] = prop['maximum']
        return forms.FloatField(**field_kwargs)

    # prop_type == 'string' (default) from here down, branching on `format`
    if fmt == 'textarea':
        return forms.CharField(widget=forms.Textarea(attrs={'rows': 6}), **kwargs)
    if fmt == 'date':
        return forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), **kwargs)
    if fmt == 'datetime':
        return forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}), **kwargs)
    if fmt == 'email':
        return forms.EmailField(**kwargs)
    if fmt == 'url':
        return forms.URLField(**kwargs)
    if fmt == 'image':
        return forms.ImageField(**kwargs)
    if fmt == 'file':
        return forms.FileField(**kwargs)

    field_kwargs = dict(kwargs)
    if 'maxLength' in prop:
        field_kwargs['max_length'] = prop['maxLength']
    return forms.CharField(widget=forms.TextInput(), **field_kwargs)


def build_dynamic_form_class(schema):
    """Returns a Form subclass (not an instance) with one field per
    schema['properties'] entry, in the order properties were defined.
    Property order matters here (dicts are ordered) since it drives the
    order fields render in - author schemas with that in mind."""
    properties = schema.get('properties', {})
    required = set(schema.get('required', []))

    field_dict = {
        name: _build_field(name, prop, name in required)
        for name, prop in properties.items()
    }
    return type('DynamicSlugDataForm', (forms.Form,), field_dict)


def build_dynamic_form(schema, data=None, files=None, initial=None):
    """Convenience: build the form class and instantiate it in one call."""
    form_class = build_dynamic_form_class(schema)
    return form_class(data=data, files=files, initial=initial)


def serialize_cleaned_data(schema, cleaned_data, existing_data=None):
    """Converts a validated dynamic form's cleaned_data into the plain,
    JSON/BSON-safe dict util.slug_dynamic_data actually stores.

    - date/datetime values become ISO strings (BSON has no bare "date
      without a time" type, and an ISO string is also directly usable as
      an HTML5 <input type="date"> value later, so there's no need to
      convert back on the way out for editing).
    - file/image fields: an uploaded file is handed to
      util.file.get_file_handler() and replaced with the returned
      storage key/filename. If no new file was uploaded (the field came
      back empty - normal on an edit where the user didn't touch it),
      the existing stored key in `existing_data` is kept rather than
      being wiped out.
    """
    existing_data = existing_data or {}
    properties = schema.get('properties', {})
    result = {}

    for name, prop in properties.items():
        if name not in cleaned_data:
            continue
        value = cleaned_data[name]
        fmt = prop.get('format')

        if fmt in ('file', 'image'):
            if value:  # an UploadedFile was actually submitted
                result[name] = get_file_handler().create(value)
            elif name in existing_data:
                result[name] = existing_data[name]
            continue

        if isinstance(value, (datetime.date, datetime.datetime)):
            result[name] = value.isoformat()
            continue

        result[name] = value

    return result
