# main/auth/admin.py
from django.contrib import admin
from .models import TeamRole, TeamUserRole, TeamRoleHistory, TeamUserRoleHistory


class TeamRoleHistoryInline(admin.TabularInline):
    model = TeamRoleHistory
    fk_name = "object"
    extra = 0
    readonly_fields = ('changed_at', 'user')
    can_delete = False
    ordering = ('-changed_at',)


@admin.register(TeamRole)
class TeamRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'is_manager_role')
    list_filter = ('group', 'is_manager_role')
    search_fields = ('name', 'group__name')
    inlines = [TeamRoleHistoryInline]


@admin.register(TeamUserRole)
class TeamUserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'date_assigned')
    list_filter = ('role__group', 'role')
    search_fields = ('user__name', 'user__email', 'role__name', 'role__group__name')


admin.site.register(TeamUserRoleHistory)
