# admin.py
from django.contrib import admin

from .models import User, Address, AddressHistory, Slug, SlugHistory
# admin.py
from django.contrib import admin
from .models import Slug, SlugHistory

@admin.register(Slug)
class SlugAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "author", "date")
    search_fields = ("name",)
    list_filter = ("date",)

@admin.register(SlugHistory)
class SlugHistoryAdmin(admin.ModelAdmin):
    list_display = ("object", "changed_at", "modify_user")
    readonly_fields = ("snapshot",)



admin.site.register(User)
admin.site.register(Address)
admin.site.register(AddressHistory)