# main/management/commands/security_check.py
"""Look up a single IP's AbuseIPDB score and public report history."""
import json

from django.core.management.base import BaseCommand

from util.security import abuseipdb


class Command(BaseCommand):
    help = "Check a single IP's AbuseIPDB score and report history"

    def add_arguments(self, parser):
        parser.add_argument("ip")
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        ip = options["ip"]
        check = abuseipdb.check_ip(ip)
        reports = abuseipdb.get_reports(ip)

        if options["json"]:
            self.stdout.write(json.dumps({"check": check, "reports": reports}, indent=2))
            return

        self.stdout.write(f"IP: {ip}")
        self.stdout.write(f"Abuse score: {check.get('abuseConfidenceScore', 0)}")
        self.stdout.write(f"Total reports: {check.get('totalReports', 0)}")
        self.stdout.write(f"ISP: {check.get('isp')}  Country: {check.get('countryCode')}")
        self.stdout.write(f"Public report history ({reports.get('total', 0)} total):")
        for r in reports.get("results", [])[:10]:
            self.stdout.write(f"  - {r.get('reportedAt')}: {(r.get('comment') or '')[:100]}")
