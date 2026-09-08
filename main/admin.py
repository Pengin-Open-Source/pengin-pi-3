# admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User, UserHistory, Address, AddressHistory, Slug, SlugHistory, RobotsRule


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



admin.site.register(Address)
admin.site.register(AddressHistory)
