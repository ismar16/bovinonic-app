from django.contrib import admin

from .models import Animal, Brand, Owner, Paddock


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ("name", "farm", "id_number", "phone")
    list_filter = ("farm",)
    search_fields = ("name", "id_number")


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("code", "farm", "title_owner")
    list_filter = ("farm", "title_owner")
    search_fields = ("code", "title_owner__name")


@admin.register(Paddock)
class PaddockAdmin(admin.ModelAdmin):
    list_display = ("name", "farm")
    list_filter = ("farm",)
    search_fields = ("name",)


@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = (
        "tag",
        "name",
        "farm",
        "sex",
        "category",
        "status",
        "owner",
        "brand",
        "paddock",
    )
    list_filter = ("farm", "status", "category", "sex", "owner", "brand")
    search_fields = ("tag", "name", "owner__name")
    autocomplete_fields = ("mother", "father", "owner", "brand", "paddock")
    raw_id_fields = ("mother", "father")
