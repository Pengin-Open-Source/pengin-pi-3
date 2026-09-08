# util/middleware/analytics.py
import json
from django.utils import timezone
from django.core.cache import cache  # Or your project's redis client
from util.analytics import get_client_ip, is_trackable_path

class PageViewLoggerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.method == 'GET' and response.status_code < 400:
            path = request.path
            if is_trackable_path(path):
                ip = get_client_ip(request)
                email = None

                if request.user.is_authenticated:
                    email = getattr(request.user, 'email', None) or request.user.get_username()

                payload = json.dumps({
                    'path': path[:500],
                    'ip_address': ip,
                    'email_alias': email,
                    'timestamp': timezone.now().isoformat()
                })

                # Push hit to Redis list named 'pending_page_views'
                try:
                    client = cache.client.get_client()  # django-redis client
                    client.rpush('pending_page_views', payload)
                except Exception:
                    pass  # Fallback or silent catch to keep request latency low

        return response