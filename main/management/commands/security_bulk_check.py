# main/management/commands/security_bulk_check.py
"""
Checks a specific, already-filtered list of IPs against AbuseIPDB in one
command invocation - meant to run AFTER a host-side orchestrator has
already excluded IPs that are already permanently banned or already
reported (see security_scan --no-abuse-check for the cheap DB-only
candidate list that filtering starts from), so AbuseIPDB API calls are
only spent on IPs that might actually need action.

  echo '["1.2.3.4","5.6.7.8"]' | docker exec -i <container> \
      python manage.py security_bulk_check --json
"""
import json
import sys

from django.core.management.base import BaseCommand, CommandError

from util.security import abuseipdb


class Command(BaseCommand):
    help = "Check a list of IPs (JSON array, via --ips-file or stdin) against AbuseIPDB"

    def add_arguments(self, parser):
        parser.add_argument("--ips-file", help="Path to a JSON file containing a list of IPs "
                                                  "(default: read the list from stdin)")
        parser.add_argument("--json", action="store_true",
                             help="Print machine-readable JSON instead of a table")

    def handle(self, *args, **options):
        if options["ips_file"]:
            with open(options["ips_file"]) as f:
                raw = f.read()
        else:
            raw = sys.stdin.read()

        try:
            ips = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CommandError(f"Expected a JSON array of IPs: {exc}")

        results = {}
        for ip in ips:
            try:
                data = abuseipdb.check_ip(ip)
            except Exception as exc:
                self.stderr.write(f"AbuseIPDB check failed for {ip}: {exc}")
                data = {}
            results[ip] = {
                "abuse_score": data.get("abuseConfidenceScore", 0),
                "total_reports": data.get("totalReports", 0),
                "isp": data.get("isp"),
                "country": data.get("countryCode"),
            }

        if options["json"]:
            self.stdout.write(json.dumps(results, indent=2))
            return

        for ip, r in sorted(results.items(), key=lambda kv: -kv[1]["abuse_score"]):
            self.stdout.write(
                f"{ip:<16} score={r['abuse_score']:>3} reports={r['total_reports']:>4} "
                f"{(r['country'] or '??'):<3} {r['isp'] or ''}"
            )
