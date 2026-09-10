# analytics/management/commands/flush_redis_views.py
import json
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.utils.dateparse import parse_datetime
from analytics.models import PageViewLog

class Command(BaseCommand):
    help = 'Flushes page view logs from Redis buffer into PostgreSQL in bulk.'

    def handle(self, *args, **options):
        client = cache.client.get_client()
        
        # Pull up to 1,000 logs at a time
        logs_to_create = []
        batch_size = 1000

        for _ in range(batch_size):
            raw_data = client.lpop('pending_page_views')
            if not raw_data:
                break
            
            data = json.loads(raw_data.decode('utf-8') if isinstance(raw_data, bytes) else raw_data)
            logs_to_create.append(
                PageViewLog(
                    path=data['path'],
                    ip_address=data['ip_address'],
                    email_alias=data['email_alias'],
                    timestamp=parse_datetime(data['timestamp'])
                )
            )

        if logs_to_create:
            PageViewLog.objects.bulk_create(logs_to_create)
            self.stdout.write(self.style.SUCCESS(f'Successfully flushed {len(logs_to_create)} views to Postgres.'))
        else:
            self.stdout.write('No pending views in Redis.')