# analytics/admin.py
import json
from datetime import timedelta
from django.contrib import admin
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from .models import PageViewLog

@admin.register(PageViewLog)
class PageViewLogAdmin(admin.ModelAdmin):
    list_display = ('path', 'ip_address', 'email_alias', 'timestamp')
    list_filter = ('timestamp', 'path')
    search_fields = ('path', 'ip_address', 'email_alias')
    readonly_fields = ('path', 'ip_address', 'email_alias', 'timestamp')
    date_hierarchy = 'timestamp'
    
    # Direct filename matching your project pattern
    change_list_template = 'change_list.html'

    def changelist_view(self, request, extra_context=None):
        last_30_days = timezone.now() - timedelta(days=30)
        qs = self.get_queryset(request).filter(timestamp__gte=last_30_days)

        # Top 10 Most Looked-At Views
        top_views = (
            qs.values('path')
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )
        top_labels = [item['path'] for item in top_views]
        top_counts = [item['total'] for item in top_views]

        # Daily Traffic Volume Trend
        daily_trend = (
            qs.annotate(date=TruncDate('timestamp'))
            .values('date')
            .annotate(total=Count('id'))
            .order_by('date')
        )
        trend_labels = [item['date'].strftime('%Y-%m-%d') for item in daily_trend if item['date']]
        trend_counts = [item['total'] for item in daily_trend]

        extra_context = extra_context or {}
        extra_context['top_labels'] = json.dumps(top_labels)
        extra_context['top_counts'] = json.dumps(top_counts)
        extra_context['trend_labels'] = json.dumps(trend_labels)
        extra_context['trend_counts'] = json.dumps(trend_counts)

        return super().changelist_view(request, extra_context=extra_context)