# util/security/abuse_scan.py
"""
Finds IPs in a PageViewLog-shaped table worth checking against AbuseIPDB:
either they hit a path only a vulnerability scanner/bot would ever request,
or they hit a real sensitive endpoint (like /login) an unusual number of
times in a short window (a brute-force signature). Read-only - never bans
or reports anything itself; see util.security.abuseipdb for that.
"""
from collections import defaultdict
from datetime import timedelta

# Paths no legitimate visitor would ever request - a single hit is already
# a strong signal. Matched as a case-insensitive substring against the
# logged path.
SCANNER_PATH_SIGNATURES = [
    "wp-login", "wp-admin", "wp-content", "wp-json", "wp-includes",
    "xmlrpc.php", ".env", ".git/config", ".git/head", "phpmyadmin",
    "/pma/", "adminer", "actuator", "/.aws/", "/config.json",
    "/vendor/phpunit", "eval-stdin.php", "/cgi-bin/", "/shell.php",
    "/console/", "/debug/default/view", "/.ssh/", "/telescope/",
]

# Real, sensitive endpoints - only suspicious at volume within a tight
# window (a brute-force signature), not on a single hit.
SENSITIVE_PATHS = ["/login", "/signup", "/reset-password", "/generate-prt"]
SENSITIVE_PATH_WINDOW_MINUTES = 10
SENSITIVE_PATH_MIN_HITS = 8


def find_candidate_ips(model, days=30):
    """
    `model` is the caller's PageViewLog model (passed in rather than
    imported directly, so this stays usable from any project with an
    equivalently-shaped table - see main.management.commands.security_scan
    for how tobuwebprod wires it up). Returns
    {ip: {"scanner_hits": [...], "sensitive_hits": [...]}} for every IP
    that tripped either signal.

    Imports django.utils.timezone lazily (rather than at module level) so
    this module's plain constants (SCANNER_PATH_SIGNATURES etc.) stay
    importable from a plain host-side script with no Django installed -
    see security_backfill_reports.py.
    """
    from django.utils import timezone
    since = timezone.now() - timedelta(days=days)
    rows = model.objects.filter(timestamp__gte=since).values(
        "ip_address", "path", "timestamp"
    ).order_by("ip_address", "timestamp")

    by_ip = defaultdict(lambda: {"scanner_hits": [], "sensitive_hits": []})
    sensitive_timestamps = defaultdict(list)

    for row in rows:
        ip = row["ip_address"]
        path = row["path"] or ""
        path_lower = path.lower()

        if any(sig in path_lower for sig in SCANNER_PATH_SIGNATURES):
            by_ip[ip]["scanner_hits"].append({
                "path": path, "timestamp": row["timestamp"].isoformat(),
            })

        if any(path_lower.startswith(p) for p in SENSITIVE_PATHS):
            sensitive_timestamps[ip].append(row["timestamp"])

    window = timedelta(minutes=SENSITIVE_PATH_WINDOW_MINUTES)
    for ip, timestamps in sensitive_timestamps.items():
        timestamps.sort()
        for i, t in enumerate(timestamps):
            cluster = [x for x in timestamps[i:] if x - t <= window]
            if len(cluster) >= SENSITIVE_PATH_MIN_HITS:
                by_ip[ip]["sensitive_hits"] = [{
                    "count": len(cluster),
                    "window_minutes": SENSITIVE_PATH_WINDOW_MINUTES,
                    "first": cluster[0].isoformat(),
                    "last": cluster[-1].isoformat(),
                }]
                break

    return {
        ip: data for ip, data in by_ip.items()
        if data["scanner_hits"] or data["sensitive_hits"]
    }
