# forms/slug.py
from django import forms
from main.models import Slug

class SlugForm(forms.ModelForm):
    class Meta:
        model = Slug
        fields = [
            "parent",
            "name",
            "meta_tags",
            "meta_description",
            "template_name",
            "render_template",
            "is_dynamic",
            "json",
        ]

        widgets = {
            "meta_tags": forms.TextInput(attrs={"placeholder": "comma,separated,tags"}),
            "meta_description": forms.Textarea(attrs={"rows": 2}),
            "render_template": forms.Textarea(attrs={"rows": 12, "class": "monospace"}),
            # id="id_json" is Django's default id_for_label for this field
            # anyway - named explicitly since templates/slug/slug.html's
            # inline JSON-validation script hooks into it by id.
            "json": forms.Textarea(attrs={"rows": 8, "class": "monospace", "id": "id_json"}),
        }

    # Model.clean() (see main/models/slug.py) already enforces "is_dynamic
    # requires parent + a valid JSON Schema in json" - ModelForm._post_clean()
    # calls instance.clean() automatically and maps its field-keyed
    # ValidationErrors onto this form's fields, so no duplicate validation
    # logic is needed here to get proper form-level error display.


class SlugChildMetaForm(forms.ModelForm):
    """The one fixed field every dynamic child instance needs regardless
    of what its parent's schema asks for: the URL slug segment itself
    (Slug.name). Deliberately NOT part of the JSON Schema - keeping it a
    plain, always-present field (same as the top-level SlugForm above)
    means a schema author never has to know about a reserved property
    name to make their content type work. Rendered alongside the
    schema-built form from util.dynamic_forms - see
    main/views/slug_dynamic.py."""
    class Meta:
        model = Slug
        fields = ["name"]
