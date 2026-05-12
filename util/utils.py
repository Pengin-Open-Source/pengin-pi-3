# util/utils.py
from django.core.serializers.json import DjangoJSONEncoder
from uuid import UUID

class UUIDEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)