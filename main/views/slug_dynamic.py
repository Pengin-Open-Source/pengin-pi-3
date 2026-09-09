# main/views/slug_dynamic.py
# Create/edit views for instances of a dynamic Slug's content type - the
# form is built at request time from the parent Slug's JSON Schema (see
# util/dynamic_forms.py); the submitted field values are stored in
# FerretDB (see util/slug_dynamic_data.py), not on the child Slug row
# itself. Mirrors SlugCreateView/SlugEditView's shape (main/views/slug.py)
# closely on purpose - same login/rate-limit gating, same
# save_history()-before-mutate convention.
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from main.forms.slug import SlugChildMetaForm
from main.models import Slug
from util.dynamic_forms import build_dynamic_form, serialize_cleaned_data
from util.security.ratelimit import RateLimitedPostMixin
from util.slug_dynamic_data import get_dynamic_data, save_dynamic_data


class SlugDynamicCreateView(LoginRequiredMixin, RateLimitedPostMixin, View):
    #TODO: Enforce is_admin on view, not just LoginRequiredMixin (matches
    # the same pre-existing TODO on SlugCreateView/SlugEditView).
    ratelimit_rate = '10/m'

    def get(self, request, parent_id):
        parent = get_object_or_404(Slug, id=parent_id, is_dynamic=True)
        meta_form = SlugChildMetaForm()
        dynamic_form = build_dynamic_form(parent.json)
        return render(request, "slug/slug_dynamic_form.html", {
            "parent": parent,
            "meta_form": meta_form,
            "dynamic_form": dynamic_form,
            "action": "create",
        })

    def post(self, request, parent_id):
        parent = get_object_or_404(Slug, id=parent_id, is_dynamic=True)
        meta_form = SlugChildMetaForm(request.POST)
        dynamic_form = build_dynamic_form(parent.json, data=request.POST, files=request.FILES)

        if meta_form.is_valid() and dynamic_form.is_valid():
            child = Slug(
                parent=parent,
                name=meta_form.cleaned_data["name"],
                author=request.user,
            )
            child.save()

            data = serialize_cleaned_data(parent.json, dynamic_form.cleaned_data)
            save_dynamic_data(child.id, data)

            return redirect("slug_dynamic_edit", parent_id=parent.id, slug_id=child.id)

        return render(request, "slug/slug_dynamic_form.html", {
            "parent": parent,
            "meta_form": meta_form,
            "dynamic_form": dynamic_form,
            "action": "create",
        })


class SlugDynamicEditView(LoginRequiredMixin, RateLimitedPostMixin, View):
    ratelimit_rate = '20/m'

    def get(self, request, parent_id, slug_id):
        parent = get_object_or_404(Slug, id=parent_id, is_dynamic=True)
        child = get_object_or_404(Slug, id=slug_id, parent=parent)
        existing_data = get_dynamic_data(child.id)

        meta_form = SlugChildMetaForm(instance=child)
        dynamic_form = build_dynamic_form(parent.json, initial=existing_data)
        return render(request, "slug/slug_dynamic_form.html", {
            "parent": parent,
            "child": child,
            "meta_form": meta_form,
            "dynamic_form": dynamic_form,
            "existing_data": existing_data,
            "action": "edit",
        })

    def post(self, request, parent_id, slug_id):
        parent = get_object_or_404(Slug, id=parent_id, is_dynamic=True)
        child = get_object_or_404(Slug, id=slug_id, parent=parent)
        existing_data = get_dynamic_data(child.id)

        meta_form = SlugChildMetaForm(request.POST, instance=child)
        dynamic_form = build_dynamic_form(parent.json, data=request.POST, files=request.FILES)

        if meta_form.is_valid() and dynamic_form.is_valid():
            child.save_history(user=request.user)
            child.name = meta_form.cleaned_data["name"]
            child.save()

            data = serialize_cleaned_data(parent.json, dynamic_form.cleaned_data, existing_data=existing_data)
            save_dynamic_data(child.id, data)

            return redirect("slug_dynamic_edit", parent_id=parent.id, slug_id=child.id)

        return render(request, "slug/slug_dynamic_form.html", {
            "parent": parent,
            "child": child,
            "meta_form": meta_form,
            "dynamic_form": dynamic_form,
            "existing_data": existing_data,
            "action": "edit",
        })
