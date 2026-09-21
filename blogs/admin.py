# blogs/admin.py
from django.contrib import admin
from .models import BlogPost, BlogHistory


class BlogHistoryInline(admin.TabularInline):
    model = BlogHistory
    extra = 0
    readonly_fields = ('changed_at', 'user')
    can_delete = False
    ordering = ('-changed_at',)


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'author',
        'date',
        'is_event',
    )
    list_filter = (
        'date',
        'is_event',
    )
    search_fields = (
        'title',
        'content',
        'tags'
    )
    readonly_fields = ('date',)
    raw_id_fields = ('author', 'event')
    inlines = [BlogHistoryInline]

    fieldsets = (
        (None, {
            'fields': ('title',)
        }),
        ('Content & Classification', {
            'fields': ('content', 'tags', 'meta_description')
        }),
        ('Attachment', {
            'fields': ('file', 'file_name'),
            'classes': ('collapse',),
        }),
        ('Event', {
            'fields': ('is_event', 'event'),
            'classes': ('collapse',),
        }),
        ('Audit Metadata', {
            'fields': ('author', 'date'),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change and not obj.author:
            obj.author = request.user
        super().save_model(request, obj, form, change)

        if hasattr(obj, 'save_history'):
            obj.save_history(user=request.user)
