# main/models/mixins.py
from django.db import models
from django.db.models.fields.files import FieldFile

from util.utils import UUIDEncoder

# Duck-typed contract, not an imported base class: core has no
# encrypted-field implementation of its own (there's nothing here worth
# encrypting yet), but HistoryMixin/AbstractHistory still need to handle
# one correctly if an app branch adds one (e.g. an SSN field) - forcing
# every such app to import a class from core, just to satisfy an isinstance
# check, would be backwards for a CMS whose apps are meant to extend core,
# not the other way around. Any field whose class defines BOTH of these
# methods is treated as encrypted-at-rest for history purposes:
#   - encrypt_for_snapshot(value): value (decrypted) -> ciphertext-safe form to snapshot
#   - decrypt_from_snapshot(value): the reverse, for get_snapshot() below
# A field can get both for free by inheriting a small mixin that
# implements them via its own get_prep_value()/from_db_value() - see
# util/crypto.py in any app branch that adds one - but core only ever
# checks for the two method names, never a specific class.


class SitemapEntry:
    """
    Opt-in marker for models that should appear in the public sitemap.
    Subclass this explicitly instead of relying on get_absolute_url()
    duck-typing — that's what let unrelated models leak in/out unpredictably.
    """
    sitemap_lastmod_field = None  # e.g. 'updated_at'

    def get_absolute_url(self):
        raise NotImplementedError(f"{self.__class__.__name__} must implement get_absolute_url()")

class HistoryMixin:
    # TODO: some models may only ever want a lightweight "who touched this
    # and when" audit trail (object+user+changed_at, no field snapshot) -
    # e.g. high-churn or high-cardinality tables where a full snapshot per
    # edit is overkill. Consider re-adding an opt-in lighter mode (a
    # save_history(user, snapshot=False) flag, or a separate mixin) rather
    # than forcing every history-tracked model through the full snapshot
    # path this class builds today.
    def save_history(self, user):
        """Snapshots this object's field values, AS THEY CURRENTLY STAND IN
        THE DATABASE, into its paired History model (found via the `history`
        reverse FK, e.g. Home -> HomeHistory).

        Deliberately re-fetches from the database rather than reading `self`'s
        in-memory attributes: by the time most call sites reach this method,
        `self` is often a ModelForm-bound instance whose fields were already
        mutated in-place by form.is_valid() (Django's _post_clean() applies
        cleaned_data onto the instance during validation, well before .save()
        ever runs) - so trusting `self` here would frequently snapshot the
        *new* values instead of the pre-change ones. Re-fetching makes this
        correct regardless of exactly when a caller invokes it relative to
        form processing, as long as it's called before the real .save().
        """
        history_model = self._meta.get_field('history').related_model
        try:
            current = type(self).objects.get(pk=self.pk)
        except type(self).DoesNotExist:
            # Not persisted yet - nothing in the DB to read back, fall back
            # to whatever's currently set on the in-memory instance.
            current = self

        snapshot = {}
        for field in current._meta.fields:  # excludes ManyToManyField automatically
            if field.primary_key or not field.editable:
                # Skip the pk and auto_now/auto_now_add timestamps - nothing
                # meaningful to revert about either.
                continue
            value = field.value_from_object(current)
            if isinstance(value, FieldFile):
                # File/ImageField isn't JSON-serializable - store the stored name/key.
                value = str(value)
            elif hasattr(field, 'encrypt_for_snapshot'):
                # field.value_from_object() already ran the field's own
                # from_db_value() (via the ORM fetch above), so `value`
                # here is the DECRYPTED plaintext (e.g. a real SSN) -
                # storing that directly would put plaintext PII in this
                # model's History table forever, defeating the point of
                # encrypting the column. Re-encrypt it for the snapshot;
                # AbstractHistory.get_snapshot() is what decrypts it back
                # for any caller that needs the real value.
                if value not in (None, ''):
                    value = field.encrypt_for_snapshot(value)
            snapshot[field.name] = value
        history_model.objects.create(object=self, user=user, snapshot=snapshot)


class AbstractHistory(models.Model):
    snapshot = models.JSONField(encoder=UUIDEncoder, default=dict, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ['-changed_at']

    def __str__(self):
        return f'{self.object_id} @ {self.changed_at}'

    def get_snapshot(self):
        """Returns this history entry's snapshot with any encrypted-at-rest
        fields (SSN, etc. - see the duck-typed contract in this module's
        docstring above HistoryMixin) decrypted back to their real values.
        ALWAYS use this instead of reading .snapshot directly when you need
        a field's actual value (e.g. a revert view doing
        setattr(obj, name, value)) - .snapshot stores encrypted fields as
        ciphertext, and setting a live field to that ciphertext string
        (which then gets re-encrypted on save()) would silently corrupt the
        field into double-encrypted garbage instead of reverting it."""
        model = self._meta.get_field('object').related_model
        fields_by_name = {f.name: f for f in model._meta.fields}
        result = dict(self.snapshot)
        for name, value in result.items():
            field = fields_by_name.get(name)
            if field is not None and hasattr(field, 'decrypt_from_snapshot') and value not in (None, ''):
                result[name] = field.decrypt_from_snapshot(value)
        return result