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
            "json",
        ]

        widgets = {
            "meta_tags": forms.TextInput(attrs={"placeholder": "comma,separated,tags"}),
            "meta_description": forms.Textarea(attrs={"rows": 2}),
            "render_template": forms.Textarea(attrs={"rows": 12, "class": "monospace"}),
            "json": forms.Textarea(attrs={"rows": 8, "class": "monospace"}),
        }
