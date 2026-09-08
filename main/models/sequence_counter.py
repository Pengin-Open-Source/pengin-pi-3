from django.db import models, transaction


class SequenceCounter(models.Model):
    """A named, atomically-incrementing counter (e.g. human-friendly ticket numbers)."""

    name = models.CharField(max_length=50, primary_key=True)
    last_value = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.name} = {self.last_value}"

    @classmethod
    def get_next_id(cls, name):
        with transaction.atomic():
            counter, _ = cls.objects.select_for_update().get_or_create(name=name)
            counter.last_value += 1
            counter.save(update_fields=['last_value'])
            return counter.last_value

    @classmethod
    def set_next_id(cls, name, value):
        with transaction.atomic():
            counter, _ = cls.objects.select_for_update().get_or_create(name=name)
            counter.last_value = value
            counter.save(update_fields=['last_value'])
            return counter.last_value
