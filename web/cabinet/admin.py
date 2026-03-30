from datetime import timedelta

from django.contrib import admin
from django.db.models import Count, Q
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from .models import (
    BotOrder,
    BotSubscription,
    BotUser,
    LinkedAccount,
    PaymentEvent,
    TelegramLinkToken,
    WebLoginToken,
)


@admin.register(LinkedAccount)
class LinkedAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "telegram_id", "created_at")
    search_fields = ("user__username", "telegram_id")


@admin.register(TelegramLinkToken)
class TelegramLinkTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "code", "created_at", "expires_at", "consumed_at", "consumed_telegram_id")
    search_fields = ("user__username", "code", "consumed_telegram_id")
    list_filter = ("consumed_at",)


@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ("id", "client_code", "telegram_id", "username", "first_name", "created_at")
    search_fields = ("client_code", "telegram_id", "username", "first_name")
    ordering = ("-id",)
    list_per_page = 50


@admin.register(BotSubscription)
class BotSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "display_name",
        "inbound_id",
        "client_email",
        "is_active",
        "expires_at",
        "revoked_at",
        "updated_at",
    )
    search_fields = (
        "id",
        "user__client_code",
        "user__telegram_id",
        "display_name",
        "client_email",
        "client_uuid",
    )
    list_filter = ("is_active", "inbound_id")
    ordering = ("-id",)
    list_per_page = 50
    actions = ("mark_inactive", "mark_active")

    @admin.action(description="Отключить выбранные подписки")
    def mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Отключено подписок: {updated}")

    @admin.action(description="Активировать выбранные подписки")
    def mark_active(self, request, queryset):
        updated = queryset.update(is_active=True, revoked_at=None)
        self.message_user(request, f"Активировано подписок: {updated}")


@admin.register(BotOrder)
class BotOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "status",
        "channel",
        "payment_method",
        "amount_minor",
        "currency_iso",
        "card_provider",
        "card_payment_id",
        "created_at",
        "paid_at",
    )
    search_fields = (
        "id",
        "payload",
        "user__client_code",
        "user__telegram_id",
        "card_payment_id",
        "provider_payment_charge_id",
        "telegram_payment_charge_id",
    )
    list_filter = ("status", "channel", "payment_method", "card_provider")
    ordering = ("-id",)
    list_per_page = 50


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "event_id", "created_at", "processed_at")
    search_fields = ("event_id", "provider")
    list_filter = ("provider",)
    ordering = ("-id",)
    list_per_page = 50


@admin.register(WebLoginToken)
class WebLoginTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "telegram_id", "expires_at", "consumed_at", "created_at")
    search_fields = ("id", "telegram_id", "token")
    list_filter = ("consumed_at",)
    ordering = ("-id",)
    list_per_page = 50


def ops_dashboard_view(request):
    now = timezone.now()
    day_ago = now - timedelta(days=1)
    week_ahead = now + timedelta(days=7)

    total_users = BotUser.objects.count()
    total_subscriptions = BotSubscription.objects.count()
    active_subscriptions = BotSubscription.objects.filter(
        is_active=True,
        revoked_at__isnull=True,
        expires_at__gt=now,
    ).count()
    expiring_7d = BotSubscription.objects.filter(
        is_active=True,
        revoked_at__isnull=True,
        expires_at__gt=now,
        expires_at__lte=week_ahead,
    ).count()

    total_orders = BotOrder.objects.count()
    pending_orders = BotOrder.objects.filter(status="pending").count()
    paid_24h = BotOrder.objects.filter(
        status__in=["paid", "activating", "activated"],
        paid_at__gte=day_ago,
    ).count()

    webhook_events_24h = PaymentEvent.objects.filter(created_at__gte=day_ago).count()
    unprocessed_webhooks = PaymentEvent.objects.filter(processed_at__isnull=True).count()

    recent_orders = BotOrder.objects.select_related("user").order_by("-id")[:20]
    recent_subscriptions = BotSubscription.objects.select_related("user").order_by("-id")[:20]
    recent_webhooks = PaymentEvent.objects.order_by("-id")[:20]

    top_users = (
        BotUser.objects.annotate(
            total_subs=Count("botsubscription"),
            active_subs=Count(
                "botsubscription",
                filter=Q(
                    botsubscription__is_active=True,
                    botsubscription__revoked_at__isnull=True,
                    botsubscription__expires_at__gt=now,
                ),
            ),
        )
        .order_by("-active_subs", "-total_subs", "id")[:10]
    )

    context = {
        **admin.site.each_context(request),
        "title": "Ops Dashboard",
        "metrics": {
            "total_users": total_users,
            "total_subscriptions": total_subscriptions,
            "active_subscriptions": active_subscriptions,
            "expiring_7d": expiring_7d,
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "paid_24h": paid_24h,
            "webhook_events_24h": webhook_events_24h,
            "unprocessed_webhooks": unprocessed_webhooks,
        },
        "recent_orders": recent_orders,
        "recent_subscriptions": recent_subscriptions,
        "recent_webhooks": recent_webhooks,
        "top_users": top_users,
    }
    return TemplateResponse(request, "admin/ops_dashboard.html", context)


_original_get_urls = admin.site.get_urls


def _get_urls():
    custom_urls = [
        path("ops/", admin.site.admin_view(ops_dashboard_view), name="ops_dashboard"),
    ]
    return custom_urls + _original_get_urls()


admin.site.get_urls = _get_urls
