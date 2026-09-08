"""Small, purpose-built query-filtering helpers.

Kept as plain functions building Q()/ordering by hand rather than adopting
django-filter: today TicketFilterForm is the only consumer, and the field
set is small and fixed, so a framework isn't worth the dependency.
"""
from django.db.models import Q


def apply_ticket_filters(queryset, cleaned_data):
    """Apply TicketFilterForm's cleaned_data onto a Ticket queryset.

    cleaned_data may legitimately be an empty dict (unbound/invalid form -
    no filters selected yet) - that still needs the default ordering below,
    so there's no early-return-on-falsy-dict here.
    """
    cleaned_data = cleaned_data or {}

    if cleaned_data.get('priority'):
        queryset = queryset.filter(priority=cleaned_data['priority'])
    if cleaned_data.get('ticket_number'):
        queryset = queryset.filter(ticket_number__icontains=cleaned_data['ticket_number'].strip())
    if cleaned_data.get('summary'):
        queryset = queryset.filter(summary__icontains=cleaned_data['summary'])
    if cleaned_data.get('content'):
        queryset = queryset.filter(content__icontains=cleaned_data['content'])
    if cleaned_data.get('role'):
        queryset = queryset.filter(role=cleaned_data['role'])
    if cleaned_data.get('author'):
        queryset = queryset.filter(author__name__icontains=cleaned_data['author'])
    if cleaned_data.get('owner'):
        queryset = queryset.filter(owner__name__icontains=cleaned_data['owner'])
    if cleaned_data.get('last_edited_by'):
        queryset = queryset.filter(last_edited_by__name__icontains=cleaned_data['last_edited_by'])
    if cleaned_data.get('tags'):
        queryset = queryset.filter(tags__icontains=cleaned_data['tags'])

    if cleaned_data.get('after_ticket_date'):
        queryset = queryset.filter(date__gte=cleaned_data['after_ticket_date'])
    if cleaned_data.get('before_ticket_date'):
        queryset = queryset.filter(date__lte=cleaned_data['before_ticket_date'])
    if cleaned_data.get('ticket_resolution_after_date'):
        queryset = queryset.filter(resolution_date__gte=cleaned_data['ticket_resolution_after_date'])
    if cleaned_data.get('ticket_resolution_before_date'):
        queryset = queryset.filter(resolution_date__lte=cleaned_data['ticket_resolution_before_date'])
    if cleaned_data.get('ticket_activity_after_date'):
        queryset = queryset.filter(
            ticketlatestactivity__latest_activity__gte=cleaned_data['ticket_activity_after_date'])
    if cleaned_data.get('ticket_activity_before_date'):
        queryset = queryset.filter(
            ticketlatestactivity__latest_activity__lte=cleaned_data['ticket_activity_before_date'])

    ordering_map = {
        '-last_activity': '-ticketlatestactivity__latest_activity',
        'last_activity': 'ticketlatestactivity__latest_activity',
        '-resolution_date': '-resolution_date',
        'resolution_date': 'resolution_date',
        'summary': 'summary',
        '-summary': '-summary',
        '-ticket_number': '-ticket_number',
        'ticket_number': 'ticket_number',
        'role__name': 'role__name',
        '-role__name': '-role__name',
        'author__name': 'author__name',
        '-author__name': '-author__name',
        'owner__name': 'owner__name',
        '-owner__name': '-owner__name',
    }
    sort_order = cleaned_data.get('sort_order') or '-last_activity'
    queryset = queryset.order_by(ordering_map.get(sort_order, '-ticketlatestactivity__latest_activity'))

    return queryset.distinct()
