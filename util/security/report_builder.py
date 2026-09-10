# util/security/report_builder.py
"""
Turns the raw evidence util.security.abuse_scan.find_candidate_ips()
collects for one IP into an AbuseIPDB category list and a factual,
English, PII-free comment describing exactly what that IP did - per
AbuseIPDB's own reporting guidance (be specific, be factual, no personal
data - notably PageViewLog.email_alias is deliberately never touched
here). Consumed by main.management.commands.security_report_auto so the
category/comment logic has one home instead of being re-derived by hand
per report.
"""
from . import abuseipdb

# Scanner-path substrings that specifically suggest an attempted exploit/
# code-execution attempt rather than plain reconnaissance - reported as
# Hacking (15) in addition to the baseline Bad Web Bot (19) / Web App
# Attack (21) every scanner hit already gets.
EXPLOIT_ATTEMPT_SIGNATURES = [
    "eval-stdin.php", "shell.php", "actuator", "vendor/phpunit",
    "adminer", "/console/",
]


def _format_hits_summary(hits, limit=8):
    counts = {}
    for hit in hits:
        counts[hit["path"]] = counts.get(hit["path"], 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: -kv[1])
    parts = [f"{path} (x{count})" for path, count in ordered[:limit]]
    if len(ordered) > limit:
        parts.append(f"and {len(ordered) - limit} other path(s)")
    return ", ".join(parts)


def build_report(ip, evidence):
    """
    Returns {"categories": [...], "comment": "..."} for `ip` given its
    evidence dict - grounded in the actual paths, statuses, and counts
    observed for that specific IP, not a generic template. Understands
    three evidence buckets (all optional):
      - scanner_hits: [{"path", "timestamp"}] - hits on known
        vulnerability-scanner/CMS-probe paths (from find_candidate_ips()
        or a nginx-log scan using the same SCANNER_PATH_SIGNATURES).
      - sensitive_hits: [{"count", "window_minutes", "first", "last"}] -
        a brute-force cluster on a real sensitive endpoint (/login etc).
      - blocked_hits: [{"path", "status", "timestamp"}] - nginx responses
        >=400 that AREN'T scanner-path hits (a plain 404/403/429/444
        storm is itself automated-abuse evidence even when the path
        itself isn't on the scanner-signature list) - only meaningful
        for nginx-log-derived evidence; PageViewLog never has these,
        since it only logs responses under 400.
      - volume_summary: {"total", "distinct_paths", "first", "last"} -
        last-resort fallback used ONLY when none of the above produced a
        specific claim: a genuinely high total hit count on otherwise
        ordinary paths is itself a signal (a human doesn't request the
        same handful of pages dozens of times), reported as Bad Web Bot
        with the real total/path-count/timespan, never a generic comment.
    """
    scanner_hits = evidence.get("scanner_hits") or []
    sensitive_hits = evidence.get("sensitive_hits") or []
    blocked_hits = evidence.get("blocked_hits") or []
    volume_summary = evidence.get("volume_summary")

    categories = set()
    comment_parts = []

    if scanner_hits:
        categories.add(abuseipdb.CATEGORY_BAD_WEB_BOT)
        categories.add(abuseipdb.CATEGORY_WEB_APP_ATTACK)
        if any(
            any(sig in h["path"].lower() for sig in EXPLOIT_ATTEMPT_SIGNATURES)
            for h in scanner_hits
        ):
            categories.add(abuseipdb.CATEGORY_HACKING)

        timestamps = sorted(h["timestamp"] for h in scanner_hits)
        comment_parts.append(
            f"{len(scanner_hits)} request(s) to known vulnerability-scanner/CMS-probe "
            f"paths between {timestamps[0]} and {timestamps[-1]} UTC: "
            f"{_format_hits_summary(scanner_hits)}."
        )

    if sensitive_hits:
        categories.add(abuseipdb.CATEGORY_BRUTE_FORCE)
        sh = sensitive_hits[0]
        comment_parts.append(
            f"{sh['count']} request(s) to a login/account endpoint within a "
            f"{sh['window_minutes']}-minute window between {sh['first']} and "
            f"{sh['last']} UTC (brute-force pattern)."
        )

    if blocked_hits:
        categories.add(abuseipdb.CATEGORY_BAD_WEB_BOT)
        timestamps = sorted(h["timestamp"] for h in blocked_hits)
        status_counts = {}
        for h in blocked_hits:
            status_counts[h["status"]] = status_counts.get(h["status"], 0) + 1
        status_summary = ", ".join(f"{count}x HTTP {status}" for status, count in
                                    sorted(status_counts.items(), key=lambda kv: -kv[1]))
        comment_parts.append(
            f"{len(blocked_hits)} additional blocked/error request(s) "
            f"({status_summary}) between {timestamps[0]} and {timestamps[-1]} UTC: "
            f"{_format_hits_summary(blocked_hits)}."
        )

    if not categories and volume_summary:
        categories.add(abuseipdb.CATEGORY_BAD_WEB_BOT)
        comment_parts.append(
            f"{volume_summary['total']} total requests across "
            f"{volume_summary['distinct_paths']} distinct path(s) between "
            f"{volume_summary['first']} and {volume_summary['last']} UTC - "
            f"sustained high-volume automated traffic pattern."
        )

    comment = " ".join(comment_parts) or "Automated abusive traffic detected in web server logs."
    return {"categories": sorted(categories), "comment": comment}
