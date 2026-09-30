from django.contrib import admin

from .models import Milking, Weighing


@admin.register(Weighing)
class WeighingAdmin(admin.ModelAdmin):
    list_display = ("animal", "date", "weight_kg", "farm")
    list_filter = ("farm", "date")
    search_fields = ("animal__tag", "animal__name")
    date_hierarchy = "date"


@admin.register(Milking)
class MilkingAdmin(admin.ModelAdmin):
    list_display = ("animal", "date", "shift", "liters", "farm")
    list_filter = ("farm", "shift", "date")
    search_fields = ("animal__tag", "animal__name")
    date_hierarchy = "date"
