# util/security/abuseipdb.py
"""
Thin client for the AbuseIPDB v2 API (https://docs.abuseipdb.com/api-v2)
- polling an IP's abuse score, pulling its public report history, and
filing a new report. Reads the API key from ABUSEIPDB_API_KEY in the
environment (set it in .env) rather than hardcoding it - the original
host-side getbadip.py script this replaces baked the key directly into
the script, which this fixes as a side effect.
"""
import json
import os
import urllib.parse
import urllib.request

BASE_URL = "https://api.abuseipdb.com/api/v2"


def _api_key():
    api_key = os.getenv("ABUSEIPDB_API_KEY")
    if not api_key:
        raise RuntimeError("ABUSEIPDB_API_KEY not set in environment")
    return api_key


def _get(path, params, timeout=10):
    url = f"{BASE_URL}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "Key": _api_key()})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post(path, data, timeout=10):
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/{path}", data=encoded,
        headers={"Accept": "application/json", "Key": _api_key()},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_ip(ip, max_age_days=90):
    """Polls /check - abuse confidence score and summary data for `ip`."""
    result = _get("check", {"ipAddress": ip, "maxAgeInDays": str(max_age_days)})
    return result.get("data", {})


def get_reports(ip, max_age_days=90, page=1, per_page=25):
    """
    Polls /reports - the public report history for `ip` (comments,
    categories, timestamps, reporting country). AbuseIPDB's public API has
    no "reports I personally filed" endpoint, so this is every public
    report for the IP, not just ours - still useful context for deciding
    whether it's already well-documented before reporting it again.
    """
    result = _get("reports", {
        "ipAddress": ip, "maxAgeInDays": str(max_age_days),
        "page": str(page), "perPage": str(per_page),
    })
    return result.get("data", {})


# AbuseIPDB category IDs this project can plausibly detect on its own -
# see https://www.abuseipdb.com/categories for the full list.
CATEGORY_HACKING = 15
CATEGORY_BRUTE_FORCE = 18
CATEGORY_BAD_WEB_BOT = 19
CATEGORY_WEB_APP_ATTACK = 21


def report_ip(ip, categories, comment):
    """
    Submits a new abuse report for `ip`. `categories` is a list of
    AbuseIPDB category IDs (see the CATEGORY_* constants above); `comment`
    should describe the concrete evidence (paths hit, counts, timestamps)
    - a report with no detail is far less useful to everyone else pulling
    from the same database.
    """
    return _post("report", {
        "ip": ip,
        "categories": ",".join(str(c) for c in categories),
        "comment": comment,
    })
