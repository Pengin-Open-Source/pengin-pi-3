# main/models/mixins.py
from django.db import models
from django.db.models.fields.files import FieldFile

from util.utils import UUIDEncoder


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