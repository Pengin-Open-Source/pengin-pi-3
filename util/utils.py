# util/utils.py
import re

from django.core.serializers.json import DjangoJSONEncoder
from uuid import UUID

#TODO: Deprecate not used

class UUIDEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)


def digits_only(value):
    """Strips everything but digits from a string - for comparing phone
    numbers that aren't stored in a normalized format (e.g. "(281) 699-2443"
    vs "281-699-2443" vs "2816992443" should all compare equal). Promoted
    out of companies/matching.py, where it was originally written for
    comparing submitted vs. on-file company phone numbers - the function
    itself has no company/model coupling, so any app comparing phone
    numbers can reuse it."""
    return re.sub(r'\D', '', value or '')