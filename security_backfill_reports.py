#!/usr/bin/env python3
"""
Backfills AbuseIPDB reports for IPs already in fail2ban's permanent-ban
jail that we've never reported (most of these predate
security_reported_ips.json entirely - the original block_permanent.sh
seed list, plus anything banned by the nginx-log-driven jails like
nginx-404/nginx-dos, whose triggering traffic never shows up in
analytics.PageViewLog at all, since PageViewLoggerMiddleware only logs
requests that got a response under 400).

Evidence sources, per IP:
  - nginx's access.log - the authoritative record of EVERY request,
    including the 403/404/429/444 responses that got most of these IPs
    banned in the first place.
  - analytics.PageViewLog (via the app container) - supplementary, for
    any successful hits that predate the current access.log's window.

IPs with literally no matching log lines in either source are skipped
outright rather than given a report with fabricated specificity -
AbuseIPDB expects factual, evidence-backed reports, and "this IP is in
our firewall list" on its own isn't that.

Batched (--batch-size) and rate-limited (--delay) to run repeatedly
against a perma-ban list this size without hammering the API in one go.

Usage:
  python3 security_backfill_reports.py                       # dry run, first 25
  python3 security_backfill_reports.py --batch-size 50 --confirm
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import types
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

from security_pipeline import _valid_ips  # noqa: E402


def _load_util_security():
    """
    Loads abuseipdb.py/report_builder.py/abuse_scan.py directly from
    their file paths, bypassing util/__init__.py and
    util/security/__init__.py entirely. None of the three actually needs
    Django (abuse_scan.py's one Django import is already lazy, inside
    find_candidate_ips() - see that file), but on some deployments (e.g.
    apm-web prod) util/__init__.py is itself a real Django AppConfig that
    unconditionally imports django, which this plain host script doesn't
    have installed - a normal `from util.security import x` always runs
    every __init__.py along the way regardless of what you're importing.
    Registers stub `util`/`util.security` packages in sys.modules first
    so report_builder.py's `from . import abuseipdb` still resolves.
    """
    security_dir = REPO_ROOT / "util" / "security"

    util_pkg = types.ModuleType("util")
    util_pkg.__path__ = [str(REPO_ROOT / "util")]
    sys.modules.setdefault("util", util_pkg)

    security_pkg = types.ModuleType("util.security")
    security_pkg.__path__ = [str(security_dir)]
    sys.modules.setdefault("util.security", security_pkg)

    def _load(name, filename):
        if name in sys.modules:
            return sys.modules[name]
        spec = importlib.util.spec_from_file_location(name, security_dir / filename)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    return (
        _load("util.security.abuseipdb", "abuseipdb.py"),
        _load("util.security.report_builder", "report_builder.py"),
        _load("util.security.abuse_scan", "abuse_scan.py"),
    )


abuseipdb, _report_builder_module, _abuse_scan_module = _load_util_security()
build_report = _report_builder_module.build_report
SCANNER_PATH_SIGNATURES = _abuse_scan_module.SCANNER_PATH_SIGNATURES
SENSITIVE_PATHS = _abuse_scan_module.SENSITIVE_PATHS
SENSITIVE_PATH_WINDOW_MINUTES = _abuse_scan_module.SENSITIVE_PATH_WINDOW_MINUTES
SENSITIVE_PATH_MIN_HITS = _abuse_scan_module.SENSITIVE_PATH_MIN_HITS

WEB_CONTAINER = os.environ.get("SECURITY_WEB_CONTAINER", "tobuweb-web")
PERMANENT_BAN_JAIL = "permanent-ban"
REPORTED_LOG_PATH = REPO_ROOT / "security_reported_ips.json"
NGINX_ACCESS_LOG = REPO_ROOT / "logs" / "nginx" / "access.log"

NGINX_LINE_RE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<path>\S+) \S+" (?P<status>\d+) \d+'
)
NGINX_TIME_FMT = "%d/%b/%Y:%H:%M:%S %z"


def load_env_var(name):
    """Minimal .env reader - report_builder.py/abuseipdb.py have no
    Django dependency, so this script calls AbuseIPDB directly rather
    than round-tripping through docker exec for every single call; no
    need for a python-dotenv dependency just to read one value."""
    env_path = REPO_ROOT / ".env"
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1]
    return None


def run(cmd, check=False):
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def get_permanent_ban_ips():
    status = run(["fail2ban-client", "status", PERMANENT_BAN_JAIL]).stdout
    for line in status.splitlines():
        if "Banned IP list:" in line:
            ips = line.split("Banned IP list:")[1].strip()
            return _valid_ips(ips.split()) if ips else set()
    return set()


def load_reported_log():
    if REPORTED_LOG_PATH.exists():
        return json.loads(REPORTED_LOG_PATH.read_text())
    return {}


def save_reported_log(log):
    REPORTED_LOG_PATH.write_text(json.dumps(log, indent=2, sort_keys=True))


def scan_nginx_log_for_ips(target_ips):
    """{ip: [{"path":, "status":, "timestamp": iso}, ...]} for every
    matching line in the current access.log."""
    hits = defaultdict(list)
    if not NGINX_ACCESS_LOG.exists():
        return hits
    with open(NGINX_ACCESS_LOG, "rt", errors="replace") as f:
        for line in f:
            m = NGINX_LINE_RE.match(line)
            if not m or m.group("ip") not in target_ips:
                continue
            try:
                ts = datetime.strptime(m.group("time"), NGINX_TIME_FMT)
            except ValueError:
                continue
            hits[m.group("ip")].append({
                "path": m.group("path"), "status": int(m.group("status")),
                "timestamp": ts.isoformat(),
            })
    return hits


def _last_json_line(output):
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return line
    return "{}"


def get_pageviewlog_hits(ips):
    """Supplementary evidence from analytics.PageViewLog, for any
    successful hits older than the current access.log's window."""
    script = (
        "import json\n"
        "from analytics.models import PageViewLog\n"
        f"ips = {json.dumps(list(ips))}\n"
        "rows = PageViewLog.objects.filter(ip_address__in=ips).values('ip_address', 'path', 'timestamp')\n"
        "out = {}\n"
        "for r in rows:\n"
        "    out.setdefault(r['ip_address'], []).append({'path': r['path'], 'timestamp': r['timestamp'].isoformat()})\n"
        "print(json.dumps(out))\n"
    )
    result = run(["docker", "exec", "-i", WEB_CONTAINER, "python", "manage.py", "shell", "-c", script])
    try:
        return json.loads(_last_json_line(result.stdout))
    except json.JSONDecodeError:
        return {}


def build_evidence(nginx_hits, pageview_hits):
    """
    Merges nginx-log hits (path+status+timestamp) and PageViewLog hits
    (path+timestamp, always a successful response) into the
    {"scanner_hits", "sensitive_hits", "blocked_hits"} shape
    report_builder.build_report() understands.
    """
    all_hits = list(nginx_hits) + [
        {"path": h["path"], "status": 200, "timestamp": h["timestamp"]} for h in pageview_hits
    ]

    scanner_hits, blocked_hits, sensitive_timestamps = [], [], []
    for h in all_hits:
        path_lower = (h["path"] or "").lower()
        if any(sig in path_lower for sig in SCANNER_PATH_SIGNATURES):
            scanner_hits.append({"path": h["path"], "timestamp": h["timestamp"]})
        elif h.get("status", 200) >= 400:
            blocked_hits.append({"path": h["path"], "status": h["status"], "timestamp": h["timestamp"]})

        if any(path_lower.startswith(p) for p in SENSITIVE_PATHS):
            sensitive_timestamps.append(datetime.fromisoformat(h["timestamp"]))

    sensitive_hits = []
    sensitive_timestamps.sort()
    window = timedelta(minutes=SENSITIVE_PATH_WINDOW_MINUTES)
    for i, t in enumerate(sensitive_timestamps):
        cluster = [x for x in sensitive_timestamps[i:] if x - t <= window]
        if len(cluster) >= SENSITIVE_PATH_MIN_HITS:
            sensitive_hits = [{
                "count": len(cluster), "window_minutes": SENSITIVE_PATH_WINDOW_MINUTES,
                "first": cluster[0].isoformat(), "last": cluster[-1].isoformat(),
            }]
            break

    volume_summary = None
    if all_hits:
        timestamps = sorted(h["timestamp"] for h in all_hits)
        volume_summary = {
            "total": len(all_hits),
            "distinct_paths": len(set(h["path"] for h in all_hits)),
            "first": timestamps[0],
            "last": timestamps[-1],
        }

    return {
        "scanner_hits": scanner_hits, "sensitive_hits": sensitive_hits,
        "blocked_hits": blocked_hits, "volume_summary": volume_summary,
        "total_hits": len(all_hits),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--batch-size", type=int, default=25, help="How many unreported IPs to process this run (default 25)")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds to sleep between AbuseIPDB report calls (default 1.0)")
    parser.add_argument("--confirm", action="store_true", help="Actually file reports (default dry-run)")
    parser.add_argument("--volume-threshold", type=int, default=None,
                         help="Last-resort fallback: if an IP matches no specific scanner/brute-force/"
                              "blocked-status pattern but its TOTAL hit count exceeds this, report it "
                              "as a high-volume Bad Web Bot using the real total/path-count/timespan "
                              "instead of skipping it. Off by default - only applies when set.")
    args = parser.parse_args()

    api_key = load_env_var("ABUSEIPDB_API_KEY")
    if api_key:
        os.environ["ABUSEIPDB_API_KEY"] = api_key

    permaban_ips = get_permanent_ban_ips()
    reported_log = load_reported_log()
    unreported = sorted(permaban_ips - set(reported_log.keys()))

    print(f"permanent-ban jail: {len(permaban_ips)} IPs")
    print(f"already reported: {len(reported_log)} IPs")
    print(f"unreported: {len(unreported)} IPs")

    batch = unreported[:args.batch_size]
    print(f"processing this batch: {len(batch)} IPs "
          f"({max(0, len(unreported) - len(batch))} remaining after this run)\n")

    print("scanning nginx access.log...")
    nginx_hits = scan_nginx_log_for_ips(set(batch))
    print(f"  log lines found for {len(nginx_hits)}/{len(batch)} IPs")

    print("pulling supplementary PageViewLog hits...")
    pageview_hits = get_pageviewlog_hits(batch)
    print(f"  rows found for {len(pageview_hits)}/{len(batch)} IPs\n")

    reported, skipped, errors = 0, 0, 0
    for ip in batch:
        evidence = build_evidence(nginx_hits.get(ip, []), pageview_hits.get(ip, []))
        if evidence["total_hits"] == 0:
            print(f"  {ip}: SKIPPED - no log evidence available")
            skipped += 1
            continue

        if args.volume_threshold is None or evidence["total_hits"] < args.volume_threshold:
            evidence = {**evidence, "volume_summary": None}

        built = build_report(ip, evidence)

        # AbuseIPDB's /report endpoint requires at least one category, and
        # a report needs SOME specific claim behind it regardless - if none
        # of scanner_hits/sensitive_hits/blocked_hits matched anything (the
        # IP's only logged activity was ordinary page views), we genuinely
        # have no evidence of abuse from our own data, even though it's
        # already permabanned (almost certainly on AbuseIPDB's own
        # pre-existing score at the time, via the old getbadip.py logic -
        # not on anything we observed). Skip rather than file a report
        # with a fabricated/generic claim.
        if not built["categories"]:
            print(f"  {ip}: SKIPPED - {evidence['total_hits']} hit(s) logged but none match "
                  f"a scanner/brute-force/blocked-status pattern (no factual claim to report)")
            skipped += 1
            continue

        if not args.confirm:
            print(f"  {ip}: [DRY RUN] categories={built['categories']} "
                  f"comment={built['comment'][:110]}...")
            continue

        try:
            abuseipdb.report_ip(ip, built["categories"], built["comment"])
            reported_log[ip] = {
                "reported_at": datetime.now(timezone.utc).isoformat(),
                "categories": built["categories"],
                "comment": built["comment"],
                "source": "backfill",
            }
            print(f"  {ip}: reported (categories={built['categories']})")
            reported += 1
        except Exception as exc:
            print(f"  {ip}: ERROR - {exc}")
            errors += 1

        time.sleep(args.delay)

    if args.confirm and reported:
        save_reported_log(reported_log)

    print(f"\nDone. {reported} reported, {skipped} skipped (no evidence), {errors} errors, "
          f"{max(0, len(unreported) - len(batch))} remaining for the next batch.")


if __name__ == "__main__":
    main()
