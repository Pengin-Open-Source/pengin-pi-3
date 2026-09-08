# util/utils.py
from django.core.serializers.json import DjangoJSONEncoder
from uuid import UUID

#TODO: Deprecate not used

class UUIDEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)