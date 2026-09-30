from django.contrib import admin

from .models import ReproductiveEvent


@admin.register(ReproductiveEvent)
class ReproductiveEventAdmin(admin.ModelAdmin):
    list_display = (
        "animal",
        "type",
        "date",
        "farm",
        "estimated_calving_date",
        "suggested_drying_off_date",
    )
    list_filter = ("farm", "type", "date")
    search_fields = ("animal__tag", "animal__name", "bull_straw")
    date_hierarchy = "date"
    readonly_fields = ("estimated_calving_date", "suggested_drying_off_date")
