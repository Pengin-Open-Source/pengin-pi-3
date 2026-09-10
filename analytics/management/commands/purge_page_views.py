# analytics/management/commands/purge_page_views.py
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from analytics.models import PageViewLog

class Command(BaseCommand):
    help = 'Purges page view logs older than a specified number of days (default: 30 days).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Retention limit in days. Records older than this will be deleted.'
        )

    def handle(self, *args, **options):
        days = options['days']
        cutoff = timezone.now() - timedelta(days=days)
        deleted_count, _ = PageViewLog.objects.filter(timestamp__lt=cutoff).delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully deleted {deleted_count} page view logs older than {days} days.')
        )