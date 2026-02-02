import json
import time
from django.shortcuts import render
from django.views import View
from django_redis import get_redis_connection


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
            "ip": self.get_client_ip(request),
        }
        key = f"{self.redis_prefix}:{int(time.time() * 1000)}"
        redis_conn.set(key, json.dumps(log_entry), ex=self.redis_expire)

    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


class SuperTemplateView(RedisLoggingMixin, View):
    def dispatch(self, request, *args, **kwargs):
        self.log_request(request)
        return super().dispatch(request, *args, **kwargs)
