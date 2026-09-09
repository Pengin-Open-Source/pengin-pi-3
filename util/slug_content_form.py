# util/slug_content_form.py
# Builds a per-field editing form from a Slug's *content* json (a plain
# dict of page content like {"hero_title": "...", "features": [...]}),
# as opposed to util/dynamic_forms.py which builds a form from an
# explicit JSON *Schema* (used for is_dynamic slugs' child instances,
# where json holds a schema, not content).
#
# There's no stored schema here - every call sniffs the *current*
# key/value shape of the dict it's given and infers a matching field.
# That's deliberate (the user's call): re-derive the form from the data
# every time rather than caching a schema, so editing the raw json
# (still exposed as an "Advanced" escape hatch - see templates/slug/
# slug_edit.html) and saving immediately produces an updated smart form
# on the next load, with no separate migration step.
#
# Scope: top-level scalar keys (str/bool/int/float) each get a widget
# matched to what the value looks like (image path, video path, HTML
# block, plain text). A list of plain strings becomes a one-per-line
# textarea. Anything more structured (list of dicts, nested dict) is
# out of scope for a per-field widget - it becomes its own clearly
# labeled, pretty-printed JSON sub-block instead of one field per
# nested key, since a fully generic recursive repeatable-widget editor
# for arbitrary nesting is its own project. That still beats one
# undifferentiated blob for the whole page: each list/dict field is at
# least isolated, labeled, and validated independently.
import json
import re

from django import forms
from django.template.loader import get_template

IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')
VIDEO_EXTS = ('.mp4', '.webm', '.ogg', '.mov')
FIELD_PREFIX = 'field__'
UPLOAD_PREFIX = 'upload__'


def upload_field_name(key):
    """The name of an image/video content field's companion file input -
    templates/slug/slug_edit.html renders one next to every image/video
    field's path text input; serialize_content_form checks request.FILES
    for it under this same name."""
    return UPLOAD_PREFIX + key

_TAG_RE = re.compile(r'\{\{.*?\}\}|\{%.*?%\}', re.DOTALL)
_STRING_LITERAL_RE = re.compile(r"""(['"]).*?\1""")
_IDENTIFIER_RE = re.compile(r'[a-zA-Z_][a-zA-Z0-9_.]*')
_FOR_RE = re.compile(r'^for\s+(.+?)\s+in\s+([a-zA-Z_][a-zA-Z0-9_.]*)')

# Template tag/filter/keyword vocabulary, and context variables the
# surrounding view/layout machinery always provides (SlugView, layout.html,
# nav_bar.html's own context processors) - never candidates for a content
# form field, so they're excluded from extract_referenced_keys' results.
_DENYLIST = {
    'if', 'else', 'elif', 'endif', 'for', 'endfor', 'in', 'not', 'and', 'or',
    'is', 'with', 'endwith', 'as', 'static', 'url', 'csrf_token', 'now',
    'firstof', 'ifchanged', 'cycle', 'regroup', 'spaceless', 'endspaceless',
    'autoescape', 'endautoescape', 'load', 'default', 'safe', 'escape',
    'length', 'first', 'last', 'stringformat', 'lower', 'upper', 'slice',
    'add', 'date', 'time', 'pluralize', 'forloop', 'counter', 'counter0',
    'revcounter', 'parentloop', 'True', 'False', 'None', 'use_macro',
    'loadmacros', 'macro', 'endmacro',
    'title', 'meta_tags', 'meta_description', 'slug', 'is_admin', 'site',
    'request', 'user', 'messages', 'creator', 'date', 'primary_title',
}


def _label(key):
    return key.replace('_', ' ').replace('html', '').strip().title() or key


def _looks_like_image(key, value):
    return key.endswith('image') or (isinstance(value, str) and value.lower().endswith(IMAGE_EXTS))


def _looks_like_video(key, value):
    return key.endswith('video') or (isinstance(value, str) and value.lower().endswith(VIDEO_EXTS))


def _looks_like_html(value):
    return '<' in value and '>' in value


def _is_string_list(value):
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _field_kind(key, value):
    """Returns one of: 'bool', 'number', 'image', 'video', 'html',
    'text', 'string_list', 'json' - the single source of truth both
    build_json_content_form and serialize_content_form key off of, so
    the two stay in sync by construction."""
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, (int, float)):
        return 'number'
    if isinstance(value, str):
        if _looks_like_image(key, value):
            return 'image'
        if _looks_like_video(key, value):
            return 'video'
        if _looks_like_html(value) or len(value) > 120:
            return 'html'
        return 'text'
    if _is_string_list(value):
        return 'string_list'
    return 'json'


class SlugContentForm(forms.Form):
    """Base class the dynamically-typed form below subclasses. Holds the
    key->kind map (set by build_json_content_form) so clean() can
    validate the JSON sub-blocks without needing per-field clean_<x>
    methods generated dynamically."""
    field_kinds = {}

    def clean(self):
        cleaned = super().clean()
        for key, kind in self.field_kinds.items():
            if kind != 'json':
                continue
            field_name = FIELD_PREFIX + key
            raw = cleaned.get(field_name)
            if not raw:
                continue
            try:
                json.loads(raw)
            except json.JSONDecodeError as e:
                self.add_error(field_name, f"Not valid JSON: {e}")
        return cleaned


def _read_template_source(template_name):
    if not template_name:
        return ''
    try:
        template = get_template(template_name)
        origin = getattr(template, 'origin', None)
        if origin and origin.name:
            with open(origin.name, encoding='utf-8') as f:
                return f.read()
    except Exception:
        pass
    return ''


def extract_referenced_keys(template_name, render_template):
    """Best-effort scan of a Slug's full rendering surface - its named
    template_name file's source (read straight off disk, not rendered)
    combined with its raw render_template override text, "the named
    template + the written put together" - for context variable names
    referenced anywhere in {{ }} or {% %} tags (including tag arguments
    like {% static hero_image %}, not just {{ }} output). Not a full
    Django template parse (tag/filter syntax varies too much to handle
    perfectly with regex) - a denylisted-keyword heuristic good enough
    to surface likely content keys the template expects that don't
    exist in json yet, so the content form can offer an input for them
    before the key is even added. Re-reads the template source fresh
    every call, same "no stored schema" principle as the rest of this
    module - editing the template file or render_template immediately
    changes what shows up here, next time this is called."""
    source = _read_template_source(template_name) + '\n' + (render_template or '')

    loop_locals = set()
    referenced = set()

    for tag_match in _TAG_RE.finditer(source):
        raw = tag_match.group(0)
        content = raw[2:-2]
        # {% block name %}/{% endblock %} - "name" is a template block
        # name, not a context variable; skip identifier scanning for it
        # entirely rather than risk flagging it as a missing content key.
        stripped = content.strip()
        if stripped.startswith('block ') or stripped == 'endblock' or stripped.startswith('endblock '):
            continue

        content = _STRING_LITERAL_RE.sub('', content)

        for_match = _FOR_RE.match(stripped)
        if for_match:
            for name in for_match.group(1).split(','):
                loop_locals.add(name.strip())
            referenced.add(for_match.group(2).split('.')[0])
            continue

        for identifier in _IDENTIFIER_RE.findall(content):
            referenced.add(identifier.split('.')[0])

    return referenced - loop_locals - _DENYLIST


def build_json_content_form(data, template_name='', render_template='', data_post=None):
    """Builds and returns a bound-or-unbound SlugContentForm instance
    with one field per top-level key in `data` (a plain dict - Slug.json
    for a non-dynamic Slug), in the same order the keys appear in
    `data`, each field's widget chosen by _field_kind - PLUS one
    (blank, plain-text) field for every key extract_referenced_keys
    finds that the template actually uses but `data` doesn't have yet,
    so a template needing a new piece of content doesn't require
    hand-editing the raw json first before it becomes editable here.
    Returns None if there's nothing to build a form from at all."""
    data = data if isinstance(data, dict) else {}
    referenced_keys = extract_referenced_keys(template_name, render_template)
    missing_keys = [k for k in referenced_keys if k not in data]

    if not data and not missing_keys:
        return None

    field_kinds = {}
    fields = {}

    for key, value in data.items():
        kind = _field_kind(key, value)
        field_kinds[key] = kind
        field_name = FIELD_PREFIX + key
        label = _label(key)

        if kind == 'bool':
            fields[field_name] = forms.BooleanField(
                required=False, initial=value, label=label,
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
        elif kind == 'number':
            fields[field_name] = forms.FloatField(
                required=False, initial=value, label=label,
                widget=forms.NumberInput(attrs={'class': 'form-control'}))
        elif kind == 'image':
            fields[field_name] = forms.CharField(
                required=False, initial=value, label=label,
                help_text="Path relative to static/, e.g. images/example.jpg",
                widget=forms.TextInput(attrs={'class': 'form-control content-preview-field content-preview-image'}))
        elif kind == 'video':
            fields[field_name] = forms.CharField(
                required=False, initial=value, label=label,
                help_text="Path relative to static/, e.g. videos/example.mp4",
                widget=forms.TextInput(attrs={'class': 'form-control content-preview-field content-preview-video'}))
        elif kind == 'html':
            fields[field_name] = forms.CharField(
                required=False, initial=value, label=label,
                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 6}))
        elif kind == 'string_list':
            fields[field_name] = forms.CharField(
                required=False, initial='\n'.join(value), label=f"{label} (one per line)",
                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}))
        elif kind == 'json':
            fields[field_name] = forms.CharField(
                required=False, initial=json.dumps(value, indent=2), label=f"{label} (JSON)",
                widget=forms.Textarea(attrs={'class': 'form-control font-monospace small', 'rows': 10}))
        else:  # 'text'
            fields[field_name] = forms.CharField(
                required=False, initial=value, label=label,
                widget=forms.TextInput(attrs={'class': 'form-control'}))

    for key in missing_keys:
        # No existing value to sniff a type from - default to plain
        # text. The *next* load re-sniffs from whatever gets saved
        # here, so typing an image path etc. promotes it to the right
        # widget automatically once it exists in json.
        field_kinds[key] = 'text'
        fields[FIELD_PREFIX + key] = forms.CharField(
            required=False, initial='', label=f"{_label(key)} (new - used by template, not yet set)",
            widget=forms.TextInput(attrs={'class': 'form-control border-warning'}))

    fields['field_kinds'] = field_kinds
    FormClass = type('_GeneratedSlugContentForm', (SlugContentForm,), fields)
    return FormClass(data=data_post)


def serialize_content_form(form, original_data, uploaded_files=None):
    """Reconstructs the json dict from a bound, is_valid()-checked
    build_json_content_form instance, preserving each key's original
    type - the counterpart to build_json_content_form's sniffing, run
    in reverse. Any key present in original_data but not covered by the
    form (shouldn't normally happen - the form is built from this same
    dict) keeps its original value rather than being dropped.

    `uploaded_files` is request.FILES (or None) - for an 'image'/'video'
    field, a file uploaded under its companion UPLOAD_PREFIX + key name
    (see build_json_content_form's file_field_name/upload_field_name,
    used by templates/slug/slug_edit.html's "Browse..." input) takes
    priority over whatever the plain text path field held, saved via
    util.file's already-existing storage backend (the same one profile
    photo uploads use) rather than reinventing upload handling here."""
    result = dict(original_data)
    uploaded_files = uploaded_files or {}

    for key, kind in form.field_kinds.items():
        field_name = FIELD_PREFIX + key
        raw = form.cleaned_data.get(field_name)

        if kind in ('image', 'video'):
            upload = uploaded_files.get(UPLOAD_PREFIX + key)
            if upload:
                from util.file import get_file_handler
                handler = get_file_handler()
                saved_name = handler.create(upload)
                result[key] = handler.get_URL(saved_name)
                continue
            result[key] = raw or ''
        elif kind == 'bool':
            result[key] = bool(raw)
        elif kind == 'number':
            result[key] = raw if raw is not None else original_data.get(key)
        elif kind == 'string_list':
            result[key] = [line.strip() for line in (raw or '').splitlines() if line.strip()]
        elif kind == 'json':
            result[key] = json.loads(raw) if raw else original_data.get(key)
        else:  # html, text
            result[key] = raw or ''

    return result
