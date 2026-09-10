# main/management/commands/security_report.py
"""
Files an AbuseIPDB report for one IP. Dry-run by default - pass --confirm
to actually submit. Meant to be run after reviewing `security_scan`'s
output, e.g.:

  docker exec <container> python manage.py security_report \
      --ip 1.2.3.4 --category web_app_attack --comment "..." --confirm
"""
from django.core.management.base import BaseCommand, CommandError

from util.security import abuseipdb

CATEGORY_CHOICES = {
    "hacking": abuseipdb.CATEGORY_HACKING,
    "brute_force": abuseipdb.CATEGORY_BRUTE_FORCE,
    "web_app_attack": abuseipdb.CATEGORY_WEB_APP_ATTACK,
}


class Command(BaseCommand):
    help = "File an AbuseIPDB report for an IP (dry-run unless --confirm is passed)"

    def add_arguments(self, parser):
        parser.add_argument("--ip", required=True, help="IP address to report")
        parser.add_argument("--category", action="append", required=True,
                             choices=sorted(CATEGORY_CHOICES), dest="categories",
                             help="AbuseIPDB category (repeatable)")
        parser.add_argument("--comment", required=True, help="Evidence description")
        parser.add_argument("--confirm", action="store_true",
                             help="Actually submit the report (default is dry-run)")

    def handle(self, *args, **options):
        category_ids = [CATEGORY_CHOICES[c] for c in options["categories"]]

        if not options["confirm"]:
            self.stdout.write(self.style.WARNING(
                f"[DRY RUN] Would report {options['ip']} - categories={category_ids} "
                f"comment={options['comment']!r}. Pass --confirm to actually submit."
            ))
            return

        try:
            result = abuseipdb.report_ip(options["ip"], category_ids, options["comment"])
        except Exception as exc:
            raise CommandError(f"AbuseIPDB report failed: {exc}")

        self.stdout.write(self.style.SUCCESS(f"Reported {options['ip']}: {result}"))
