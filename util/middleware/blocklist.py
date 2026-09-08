import os
import re
from django.http import HttpResponseForbidden

class HardenedBlocklistMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.blocked_ips = set()
        self.load_blocklist()

    def load_blocklist(self):
        # Path to mounted or shared nginx_blocklist.conf
        blocklist_path = '/app/nginx_blocklist.conf'
        if os.path.exists(blocklist_path):
            with open(blocklist_path, 'r') as f:
                content = f.read()
                # Extracts IP addresses from "deny X.X.X.X;"
                self.blocked_ips = set(re.findall(r'deny\s+([0-9\.]+);', content))

    def __call__(self, request):
        # Unwrap IP from Traefik / Proxy headers
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Client IP is the first IP in X-Forwarded-For chain
            client_ip = x_forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.META.get('REMOTE_ADDR')

        # Fallback check against CloudFront viewer address if present
        cloudfront_ip = request.META.get('HTTP_CLOUDFRONT_VIEWER_ADDRESS')
        if cloudfront_ip:
            client_ip = cloudfront_ip.split(':')[0].strip()

        if client_ip in self.blocked_ips:
            return HttpResponseForbidden("Access Denied")

        return self.get_response(request)