from django.contrib import admin

from .models import Farm, FarmMembership


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "created_at")
    search_fields = ("name",)


@admin.register(FarmMembership)
class FarmMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "farm", "role", "created_at")
    list_filter = ("farm", "role")
    search_fields = ("user__username", "farm__name")
