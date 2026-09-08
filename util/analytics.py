# util/analytics.py
import re


EXCLUDED_PATHS = [
    re.compile(r'^/admin/'),
    re.compile(r'^/static/'),
    re.compile(r'^/media/'),
    re.compile(r'^/favicon\.ico$'),
    re.compile(r'^/apple-touch-icon.*\.png$'),
    re.compile(r'^/robots\.txt/?$'),
    re.compile(r'^/sitemap\.xml/?$'),
    # Add common static file extensions to prevent garbage tracking
    re.compile(r'.*\.(css|js|map|woff|woff2|ttf|ico|png|jpg|jpeg|svg|webp)$', re.IGNORECASE),
]

def get_client_ip(request):
    """
    Extract real client IP handling CloudFront, Traefik, and Nginx reverse proxies.
    """
    # 1. Direct CloudFront viewer header (IP:Port format)
    cloudfront_address = request.META.get('HTTP_CLOUDFRONT_VIEWER_ADDRESS')
    if cloudfront_address:
        # Strip out the port if present
        ip = cloudfront_address.split(':')[0].strip()
        if ip:
            return ip

    # 2. Standard X-Forwarded-For header chain
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Client IP is ALWAYS the first element in X-Forwarded-For
        ips = [ip.strip() for ip in x_forwarded_for.split(',')]
        if ips:
            return ips[0]

    # 3. Fallback to direct connection IP
    return request.META.get('REMOTE_ADDR')

def is_trackable_path(path):
    return not any(pattern.search(path) for pattern in EXCLUDED_PATHS)