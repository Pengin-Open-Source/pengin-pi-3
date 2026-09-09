# util/json_schema.py
# Thin wrapper around the `jsonschema` library for the one thing Slug's
# is_dynamic feature needs: confirming an admin-authored JSON document is
# itself a structurally valid JSON Schema (not validating some other piece
# of data against it - that happens separately, once per submitted dynamic
# form, via util/dynamic_forms.py). Kept as a single function rather than
# spreading jsonschema calls across model/form code so the draft version
# used is defined in exactly one place.
import jsonschema
from jsonschema.validators import Draft202012Validator


class InvalidSchemaError(Exception):
    """Raised when a document isn't a structurally valid JSON Schema."""


def validate_schema_document(schema):
    """Raises InvalidSchemaError if `schema` isn't a valid JSON Schema
    (Draft 2020-12) document. A bare {} is technically valid JSON Schema
    (matches anything) but useless for building a form from, so callers
    that need at least one real field should check `schema.get('properties')`
    themselves - this function only checks structural validity.
    """
    if not isinstance(schema, dict):
        raise InvalidSchemaError("A JSON Schema must be a JSON object.")
    try:
        Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as e:
        raise InvalidSchemaError(e.message) from e
