"""Monkeypatch for a reentrancy bug in the vendored django-macros package.

django-macros' DefineMacroNode.render() (macros/templatetags/macros.py)
resolves its kwarg defaults by mutating self.kwargs in place, replacing each
template.Variable with its already-resolved value. Combined with Django's
cached template loader (the default here - see TEMPLATES in settings.py),
the SAME DefineMacroNode object is reused across every future render of any
template that {% loadmacros %} that file, for the life of the process. The
first render mutates self.kwargs from Variables to plain resolved values;
every render after that crashes calling .resolve() on an already-resolved
value (e.g. AttributeError: 'SafeString' object has no attribute 'resolve').

This reliably reproduces the moment the same macro file is loaded via
{% include %} more than once in a process's lifetime - which is exactly
the pattern the tickets/forums shared partials use. Rather than patch the
third-party package in site-packages (lost on every reinstall), this
monkeypatches both node classes at app startup (see main/apps.py) to
resolve kwargs into a fresh, per-node cache attribute instead of mutating
the parsed Variables - restoring idempotency without changing behavior for
any existing caller.
"""
from django import template
from macros.templatetags import macros as macros_module

_PATCH_MARKER = '_macros_reentrancy_patch'


def patch_macros_node_mutation_bug():
    if getattr(macros_module, _PATCH_MARKER, False):
        return  # already patched (e.g. ready() called more than once)

    def define_macro_render(self, context):
        resolved = {}
        for name, value in self.kwargs.items():
            if isinstance(value, template.Variable):
                resolved[name] = value.resolve(context)
            else:
                resolved[name] = value
        self._resolved_kwargs = resolved
        return ''

    def use_macro_render(self, context):
        for i, arg in enumerate(self.macro.args):
            try:
                template_variable = self.args[i]
                context[arg] = template_variable.resolve(context)
            except IndexError:
                context[arg] = ""

        resolved_defaults = getattr(self.macro, '_resolved_kwargs', None) or {}
        for name, default in self.macro.kwargs.items():
            if name in self.kwargs:
                context[name] = self.kwargs[name].resolve(context)
            elif name in resolved_defaults:
                context[name] = resolved_defaults[name]
            elif isinstance(default, template.Variable):
                context[name] = default.resolve(context)
            else:
                context[name] = default

        return self.macro.nodelist.render(context)

    macros_module.DefineMacroNode.render = define_macro_render
    macros_module.UseMacroNode.render = use_macro_render
    setattr(macros_module, _PATCH_MARKER, True)
