import os


def recaptcha_context(request):
    """
    Automatically injects 'site_key' into all template contexts site-wide.
    """
    return {
        'site_key': os.getenv('RECAPTCHA_SITE_KEY', '')
    }