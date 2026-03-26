from django.contrib import admin

from .models import LinkedAccount


@admin.register(LinkedAccount)
class LinkedAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "telegram_id", "created_at")
    search_fields = ("user__username", "telegram_id")
