# util/mixins.py
# Generic, non-auth view mixins. Auth/permission mixins live in
# main/auth/mixins.py instead - this file is for reusable behavior that has
# nothing to do with who the user is or what they're allowed to do.
import json
import time

from django.core.serializers.json import DjangoJSONEncoder
from django_redis import get_redis_connection

from util.analytics import get_client_ip


class RedisLoggingMixin:
    redis_prefix = "request_log"
    redis_expire = 3600

    def log_request(self, request):
        redis_conn = get_redis_connection("default")
        log_entry = {
            "user_id": getattr(request.user, "id", None),
            "username": getattr(request.user, "email", "Anonymous"),
            "method": request.method,
            "path": request.path,
            "ip": get_client_ip(request),
        }
        key = f"{self.redis_prefix}:{int(time.time() * 1000)}"
        # Use DjangoJSONEncoder to serialize UUIDs, datetime, etc.
        redis_conn.set(key, json.dumps(log_entry, cls=DjangoJSONEncoder), ex=self.redis_expire)
