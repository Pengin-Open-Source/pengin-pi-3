# admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import (
    User, UserHistory, Site, SiteHistory, Slug, SlugHistory, RobotsRule,
    Event, EventHistory, EventParticipant,
)
from main.auth import admin as auth_admin  # noqa: F401 - registers TeamRole/TeamUserRole admin


class UserHistoryInline(admin.TabularInline):
    model = UserHistory
    fk_name = "object"
    extra = 0
    readonly_fields = ("changed_at", "user")
    can_delete = False
    ordering = ("-changed_at",)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    ordering = ("email",)
    list_display = ("email", "name", "is_staff", "is_active", "validated")
    list_filter = ("is_staff", "is_active", "validated")
    search_fields = ("email", "name")
    inlines = [UserHistoryInline]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("name", "image")}),
        ("Validation", {"fields": ("validated", "validation_date")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "name", "password1", "password2")}),
    )

    def save_model(self, request, obj, form, change):
        if change:
            obj.save_history(user=request.user)
        super().save_model(request, obj, form, change)


@admin.register(RobotsRule)
class RobotsRuleAdmin(admin.ModelAdmin):
    list_display = ("user_agent", "path", "allow")
    list_filter = ("allow", "user_agent")
    search_fields = ("path",)

@admin.register(Slug)
class SlugAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "author", "date")
    search_fields = ("name",)
    list_filter = ("date",)

@admin.register(SlugHistory)
class SlugHistoryAdmin(admin.ModelAdmin):
    list_display = ("object", "changed_at", "user")
    readonly_fields = ("snapshot",)



class SiteHistoryInline(admin.TabularInline):
    model = SiteHistory
    fk_name = "object"
    extra = 0
    readonly_fields = ("changed_at", "user", "snapshot")
    can_delete = False
    ordering = ("-changed_at",)


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("company_name", "city", "state", "phone", "updated_at")
    inlines = [SiteHistoryInline]

    def save_model(self, request, obj, form, change):
        if change:
            obj.save_history(user=request.user)
        super().save_model(request, obj, form, change)


class EventHistoryInline(admin.TabularInline):
    model = EventHistory
    extra = 0
    readonly_fields = ('changed_at', 'user')
    can_delete = False
    ordering = ('-changed_at',)


class EventParticipantInline(admin.TabularInline):
    model = EventParticipant
    extra = 0
    raw_id_fields = ('participant', 'added_by')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'start_datetime',
        'end_datetime',
        'visibility',
        'is_recurring',
        'author',
        'organizer',
        'date_created',
    )
    list_filter = (
        'visibility',
        'is_recurring',
        'is_public_reservable_time',
        'is_internal_reservable_time',
        'start_datetime',
        'date_created',
    )
    search_fields = (
        'title',
        'description',
        'location',
    )
    raw_id_fields = ('author', 'organizer', 'last_edited_by')
    filter_horizontal = ('roles',)
    fieldsets = (
        (None, {'fields': ('title', 'description', 'location', 'visibility', 'roles')}),
        ('Schedule', {'fields': ('start_datetime', 'end_datetime', 'is_recurring', 'recur_until')}),
        ('People', {'fields': ('author', 'organizer', 'last_edited_by')}),
        ('Reservable Time', {'fields': ('is_public_reservable_time', 'is_internal_reservable_time', 'slot_duration_minutes')}),
        ('Dynamic Page (advanced - raw Django template code)', {
            'classes': ('collapse',),
            'fields': ('template_name', 'render_template', 'json'),
        }),
    )
    inlines = [EventParticipantInline, EventHistoryInline]

    def save_model(self, request, obj, form, change):
        is_create = not change
        if is_create and not obj.author_id:
            obj.author = request.user
        if is_create and not obj.organizer_id:
            obj.organizer = request.user
        super().save_model(request, obj, form, change)
        obj.save_history(user=request.user)
