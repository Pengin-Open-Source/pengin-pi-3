# main/management/commands/security_scan.py
"""
Scans analytics.PageViewLog for IPs worth checking against AbuseIPDB (see
util.security.abuse_scan for the detection logic), polls AbuseIPDB for
each one, and prints a structured report. Read-only - files no reports and
bans nothing itself. Meant to be run via
`docker exec <container> python manage.py security_scan`, so a host-side
script (or a person) can pull this data without needing raw DB/psql access.
"""
import json

from django.core.management.base import BaseCommand

from analytics.models import PageViewLog
from util.security import abuseipdb
from util.security.abuse_scan import find_candidate_ips


class Command(BaseCommand):
    help = "Scan PageViewLog for suspicious IPs and check them against AbuseIPDB"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30,
                             help="Lookback window in days (default 30)")
        parser.add_argument("--min-score", type=int, default=0,
                             help="Only include IPs with an AbuseIPDB score >= this (default 0 = show all, ignored with --no-abuse-check)")
        parser.add_argument("--json", action="store_true",
                             help="Print machine-readable JSON instead of a table")
        parser.add_argument("--no-abuse-check", action="store_true",
                             help="Skip AbuseIPDB lookups entirely - just the DB-side evidence "
                                  "(fast, no API calls; for a pipeline that will filter the "
                                  "candidate list down before spending API calls on it)")

    def handle(self, *args, **options):
        candidates = find_candidate_ips(PageViewLog, days=options["days"])

        if options["no_abuse_check"]:
            report = [
                {"ip": ip, "scanner_hits": evidence["scanner_hits"],
                 "sensitive_hits": evidence["sensitive_hits"]}
                for ip, evidence in candidates.items()
            ]
            if options["json"]:
                self.stdout.write(json.dumps(report, indent=2))
                return
            for r in report:
                self.stdout.write(
                    f"{r['ip']:<16} scanner_hits={len(r['scanner_hits']):>3} "
                    f"sensitive_hits={len(r['sensitive_hits']):>2}"
                )
            return

        report = []
        for ip, evidence in candidates.items():
            try:
                abuse_data = abuseipdb.check_ip(ip)
            except Exception as exc:
                self.stderr.write(f"AbuseIPDB check failed for {ip}: {exc}")
                abuse_data = {}

            score = abuse_data.get("abuseConfidenceScore", 0)
            if score < options["min_score"]:
                continue

            report.append({
                "ip": ip,
                "abuse_score": score,
                "total_reports": abuse_data.get("totalReports", 0),
                "isp": abuse_data.get("isp"),
                "country": abuse_data.get("countryCode"),
                "scanner_hits": evidence["scanner_hits"],
                "sensitive_hits": evidence["sensitive_hits"],
            })

        report.sort(key=lambda r: r["abuse_score"], reverse=True)

        if options["json"]:
            self.stdout.write(json.dumps(report, indent=2))
            return

        if not report:
            self.stdout.write("No candidates found.")
            return

        for r in report:
            self.stdout.write(
                f"{r['ip']:<16} score={r['abuse_score']:>3} reports={r['total_reports']:>4} "
                f"{(r['country'] or '??'):<3} scanner_hits={len(r['scanner_hits']):>3} "
                f"sensitive_hits={len(r['sensitive_hits']):>2}  {r['isp'] or ''}"
            )
