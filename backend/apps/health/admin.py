from django.contrib import admin

from .models import HealthEvent


@admin.register(HealthEvent)
class HealthEventAdmin(admin.ModelAdmin):
    list_display = (
        "animal",
        "type",
        "product",
        "date",
        "farm",
        "withdrawal_days",
        "withdrawal_end_date",
    )
    list_filter = ("farm", "type", "date")
    search_fields = ("animal__tag", "animal__name", "product")
    date_hierarchy = "date"
    readonly_fields = ("withdrawal_end_date",)
