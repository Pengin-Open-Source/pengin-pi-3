# util/security/recaptcha.py
import json
import os
import urllib.parse
import urllib.request
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect

VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


def verify_recaptcha_token(token, min_score=0.5):
    """
    Validates a Google reCAPTCHA v3 token using Python's standard library.

    If RECAPTCHA_SITE_KEY/RECAPTCHA_SECRET_KEY aren't configured, reCAPTCHA is
    considered disabled and verification is skipped (treated as passing) so
    forms aren't permanently locked out in environments without Google keys.
    """
    if not getattr(settings, 'RECAPTCHA_ENABLED', False):
        print("[reCAPTCHA Debug] reCAPTCHA not configured - skipping verification (disabled)")
        return True

    if not token:
        print("[reCAPTCHA Debug] No token received in request POST data")
        return False

    secret_key = os.getenv("RECAPTCHA_SECRET_KEY")

    try:
        data = urllib.parse.urlencode({
            'secret': secret_key,
            'response': token
        }).encode('utf-8')

        req = urllib.request.Request(VERIFY_URL, data=data)
        with urllib.request.urlopen(req, timeout=5) as response:
            g_response = json.loads(response.read().decode('utf-8'))
            
            print("[reCAPTCHA Response]:", g_response)

            success = g_response.get("success", False)
            score = g_response.get("score", 0.0)
            
            return success and score >= min_score
    except Exception as e:
        print("[reCAPTCHA Debug Exception]:", str(e))
        return False


class RecaptchaRequiredMixin:
    """
    CBV Mixin that automatically enforces reCAPTCHA v3 validation on POST requests.
    """
    recaptcha_min_score = 0.5

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST':
            token = request.POST.get('g-recaptcha-response')
            
            if not verify_recaptcha_token(token, min_score=self.recaptcha_min_score):
                messages.error(request, "Human verification failed. Please try again.")
                return redirect(request.META.get('HTTP_REFERER', request.path))
                
        return super().dispatch(request, *args, **kwargs)