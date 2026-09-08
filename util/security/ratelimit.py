# util/security/ratelimit.py
from django.contrib import messages
from django.shortcuts import redirect
from django_ratelimit.core import is_ratelimited
from util.analytics import get_client_ip

class RateLimitedPostMixin:
    ratelimit_rate = '5/m'
    
    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST':
            def safe_ip_key(group, req):
                ip = get_client_ip(req)
                return ip if ip else '127.0.0.1'

            try:
                limited = is_ratelimited(
                    request=request,
                    group=self.__class__.__name__,
                    key=safe_ip_key,
                    rate=getattr(self, 'ratelimit_rate', self.ratelimit_rate),
                    increment=True
                )
                if limited:
                    messages.error(request, "Too many attempts. Please wait a moment and try again.")
                    return redirect(request.META.get('HTTP_REFERER', request.path))
            except Exception:
                # Fallback gracefully if cache backend or ratelimit fails so login isn't blocked completely
                pass

        return super().dispatch(request, *args, **kwargs)
    
    
class RateLimitedGetMixin:
    """
    Mixin to rate-limit GET requests (e.g., login, registration, or search pages).
    """
    ratelimit_rate = '10/m'  # Adjust rate limit per minute as needed

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            def safe_ip_key(group, req):
                ip = get_client_ip(req)
                return ip if ip else '127.0.0.1'

            try:
                limited = is_ratelimited(
                    request=request,
                    group=f"{self.__class__.__name__}_GET",
                    key=safe_ip_key,
                    rate=getattr(self, 'ratelimit_rate', self.ratelimit_rate),
                    increment=True
                )
                if limited:
                    messages.error(request, "Too many requests. Please wait a moment and refresh.")
                    # Redirect to a lightweight page or referer to stop further GET processing
                    return redirect(request.META.get('HTTP_REFERER', '/'))
            except Exception:
                # Graceful fallback if Redis/Cache fails
                pass

        return super().dispatch(request, *args, **kwargs)