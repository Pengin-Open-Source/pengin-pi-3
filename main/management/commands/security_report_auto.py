# main/management/commands/security_report_auto.py
"""
Files an AbuseIPDB report for one IP built automatically from its actual
observed evidence (see util.security.report_builder), rather than a
category/comment typed by hand each time. Dry-run by default - pass
--confirm to actually submit. The evidence JSON is the per-IP shape
security_scan --no-abuse-check produces:

  {"scanner_hits": [{"path": ..., "timestamp": ...}, ...],
   "sensitive_hits": [{"count": ..., "window_minutes": ..., "first": ..., "last": ...}]}

  docker exec <container> python manage.py security_report_auto \
      --ip 1.2.3.4 --evidence-json '{"scanner_hits": [...], "sensitive_hits": []}' \
      --confirm
"""
import json

from django.core.management.base import BaseCommand, CommandError

from util.security import abuseipdb
from util.security.report_builder import build_report


class Command(BaseCommand):
    help = "File an evidence-derived AbuseIPDB report for an IP (dry-run unless --confirm is passed)"

    def add_arguments(self, parser):
        parser.add_argument("--ip", required=True)
        parser.add_argument("--evidence-json", required=True,
                             help="JSON evidence dict for this IP, as produced by "
                                  "security_scan --no-abuse-check")
        parser.add_argument("--confirm", action="store_true",
                             help="Actually submit the report (default is dry-run)")

    def handle(self, *args, **options):
        try:
            evidence = json.loads(options["evidence_json"])
        except json.JSONDecodeError as exc:
            raise CommandError(f"--evidence-json is not valid JSON: {exc}")

        built = build_report(options["ip"], evidence)

        if not options["confirm"]:
            self.stdout.write(json.dumps({"dry_run": True, "ip": options["ip"], **built}))
            return

        try:
            result = abuseipdb.report_ip(options["ip"], built["categories"], built["comment"])
        except Exception as exc:
            raise CommandError(f"AbuseIPDB report failed: {exc}")

        self.stdout.write(json.dumps({
            "dry_run": False, "ip": options["ip"], **built, "result": result,
        }))
