# main/models/mixins.py
from django.forms.models import model_to_dict
from django.apps import apps
from django.db import models
from django.utils.timezone import now


class HistoryMixin(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, user=None, **kwargs):
        is_create = self._state.adding

        if not is_create:
            self._write_history(user=user)

        super().save(*args, **kwargs)

    def _write_history(self, user=None):
        model = self.__class__
        original = model.objects.get(pk=self.pk)

        data = model_to_dict(
            original,
            fields=[f.name for f in model._meta.fields]
        )

        history_model = self._get_history_model()

        history_model.objects.create(
            object=original,
            snapshot=data,
            last_author=getattr(original, "author", None),
            modify_user=user,
            changed_at=now(),
        )

    def _get_history_model(self):
        model_name = self._meta.model_name
        app_label = self._meta.app_label
        return apps.get_model(app_label, f"{model_name.capitalize()}History")
