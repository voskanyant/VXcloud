from __future__ import annotations

import json
import os
from datetime import timedelta
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.db.models import Q, QuerySet
from django.db.utils import OperationalError, ProgrammingError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.html import format_html
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from blog.admin import BLOCK_EDITOR_ASSET_VERSION
from blog.models import Category, Page, Post, PostType, SiteText
from cabinet.models import (
    BotOrder,
    BotSubscription,
    BotUser,
    LinkedAccount,
    SupportMessage,
    SupportTicket,
    VPNNode,
    VPNNodeClient,
)

from .forms import (
    BackofficeCategoryForm,
    BackofficePageForm,
    BackofficePostForm,
    BackofficePostTypeForm,
    BackofficeSiteTextForm,
    StaffAuthenticationForm,
    TicketReplyForm,
)

LEGACY_CONTENT_NOTICE = (
    "Публичный контент уже живёт в WordPress. Django здесь нужен для бота, оплат, VPN-операций и поддержки."
)

STALE_PENDING_ORDER_TTL = timedelta(minutes=30)
WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET = 10**12


class StaffRequiredMixin:
    login_url = reverse_lazy("backoffice:login")

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return redirect(f"{self.login_url}?next={request.path}")
        if not request.user.is_staff:
            raise PermissionDenied("Доступ только для staff")
        return super().dispatch(request, *args, **kwargs)


class LegacyContentContextMixin:
    content_management = False

    def is_content_readonly(self) -> bool:
        return self.content_management and settings.WORDPRESS_CONTENT_READONLY

    def get_wordpress_notice(self) -> str:
        return LEGACY_CONTENT_NOTICE if self.content_management else ""

    def add_wordpress_context(self, ctx: dict[str, Any]) -> dict[str, Any]:
        ctx["wordpress_notice"] = self.get_wordpress_notice()
        ctx["wordpress_public_site_enabled"] = settings.WORDPRESS_PUBLIC_SITE_ENABLED
        ctx["wordpress_content_readonly"] = self.is_content_readonly()
        ctx["wordpress_public_site_url"] = settings.WORDPRESS_PUBLIC_SITE_URL or "/"
        return ctx


class LegacyContentMutationGuardMixin(LegacyContentContextMixin):
    success_url_name = ""

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if self.is_content_readonly():
            messages.warning(
                request,
                "Legacy CMS закрыт для изменений. Публичный контент редактируется в WordPress.",
            )
            return redirect(reverse(self.success_url_name))
        return super().dispatch(request, *args, **kwargs)


class BackofficeLoginView(LoginView):
    template_name = "backoffice/login.html"
    authentication_form = StaffAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self) -> str:
        return self.get_redirect_url() or reverse("backoffice:dashboard")


class BackofficeLogoutView(LogoutView):
    next_page = reverse_lazy("backoffice:login")


def safe_count(qs: QuerySet) -> int:
    try:
        return qs.count()
    except (OperationalError, ProgrammingError):
        return 0


def safe_get(queryset_callable, fallback):
    try:
        return queryset_callable()
    except (OperationalError, ProgrammingError):
        return fallback


def format_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if hasattr(value, "isoformat") and hasattr(value, "tzinfo"):
        try:
            value = timezone.localtime(value)
        except Exception:
            pass
        return value.strftime("%d.%m.%Y %H:%M")
    return value


def status_badge(text: str, tone: str = "secondary") -> str:
    return format_html('<span class="badge text-bg-{} bo-badge">{}</span>', tone, text)


def boolean_badge(flag: bool, true_label: str = "Да", false_label: str = "Нет") -> str:
    return status_badge(true_label if flag else false_label, "success" if flag else "secondary")


def user_source_label(telegram_id: int | None) -> str:
    if telegram_id is None:
        return "unknown"
    return "telegram" if telegram_id > 0 else "site-only"


def user_source_badge(telegram_id: int | None) -> str:
    source = user_source_label(telegram_id)
    tone = "primary" if source == "telegram" else "secondary"
    label = "Telegram" if source == "telegram" else "Site-only"
    return status_badge(label, tone)


def order_status_badge(status: str | None) -> str:
    normalized = (status or "").lower()
    tone_map = {
        "activated": "success",
        "paid": "success",
        "pending": "warning",
        "cancelled": "secondary",
        "failed": "danger",
    }
    return status_badge(status or "-", tone_map.get(normalized, "secondary"))


def _is_stale_pending_order(order: BotOrder, *, now=None) -> bool:
    if str(getattr(order, "status", "") or "").lower() != "pending":
        return False
    created_at = getattr(order, "created_at", None)
    if created_at is None:
        return False
    current_time = now or timezone.now()
    try:
        return created_at <= current_time - STALE_PENDING_ORDER_TTL
    except Exception:
        return False


def order_status_display(order: BotOrder, *, now=None) -> str:
    if _is_stale_pending_order(order, now=now):
        method = str(getattr(order, "payment_method", "") or getattr(order, "channel", "") or "").lower()
        if method == "card":
            return status_badge("stale", "danger")
        return status_badge("stale-stars", "warning")
    return order_status_badge(getattr(order, "status", None))


def cancel_stale_pending_card_orders() -> int:
    cutoff = timezone.now() - STALE_PENDING_ORDER_TTL
    return BotOrder.objects.filter(
        status="pending",
        payment_method="card",
        created_at__lt=cutoff,
    ).update(status="cancelled")


def ticket_status_badge(status: str | None) -> str:
    normalized = (status or "").lower()
    tone = "success" if normalized == "closed" else "warning"
    return status_badge(status or "-", tone)


def sync_state_badge(state: str | None) -> str:
    normalized = (state or "").lower()
    if normalized == "ok":
        tone = "success"
    elif normalized in {"pending", "queued"}:
        tone = "warning"
    else:
        tone = "danger"
    return status_badge(state or "-", tone)


def health_badge(node: VPNNode) -> str:
    if not node.is_active:
        return status_badge("offline", "secondary")
    if node.last_health_ok is True:
        return status_badge("healthy", "success")
    if node.last_health_ok is False:
        return status_badge("error", "danger")
    return status_badge("unknown", "warning")


def env_value(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else str(value)


def send_telegram_text(telegram_id: int, text: str) -> None:
    token = (
        env_value("TELEGRAM_WEBAPP_BOT_TOKEN")
        or env_value("TELEGRAM_BOT_TOKEN")
        or settings.TELEGRAM_WEBAPP_BOT_TOKEN
    )
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    payload = json.dumps(
        {"chat_id": telegram_id, "text": text, "disable_web_page_preview": True}
    ).encode("utf-8")
    req = urllib_request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=10) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError(f"Telegram API error: {body}")


class DashboardView(StaffRequiredMixin, TemplateView):
    template_name = "backoffice/dashboard.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Bot Control Center"

        metrics = {
            "users_total": safe_count(BotUser.objects.all()),
            "users_telegram": safe_count(BotUser.objects.filter(telegram_id__gt=0)),
            "subscriptions_active": safe_count(BotSubscription.objects.filter(is_active=True)),
            "orders_pending": safe_count(BotOrder.objects.filter(status="pending")),
            "orders_pending_stale": safe_count(
                BotOrder.objects.filter(status="pending", created_at__lt=timezone.now() - STALE_PENDING_ORDER_TTL)
            ),
            "orders_activated": safe_count(BotOrder.objects.filter(status="activated")),
            "tickets_open": safe_count(SupportTicket.objects.exclude(status="closed")),
            "nodes_total": safe_count(VPNNode.objects.all()),
            "nodes_unhealthy": safe_count(
                VPNNode.objects.filter(is_active=True).exclude(last_health_ok=True)
            ),
            "sync_errors": safe_count(VPNNodeClient.objects.exclude(sync_state="ok")),
        }
        ctx["headline_metrics"] = [
            {"label": "Пользователи", "value": metrics["users_total"], "tone": "primary"},
            {"label": "Активные подписки", "value": metrics["subscriptions_active"], "tone": "success"},
            {"label": "Открытые тикеты", "value": metrics["tickets_open"], "tone": "warning"},
            {"label": "Stale pending", "value": metrics["orders_pending_stale"], "tone": "danger"},
        ]
        ctx["secondary_metrics"] = [
            {"label": "Telegram users", "value": metrics["users_telegram"]},
            {"label": "Fresh pending", "value": max(metrics["orders_pending"] - metrics["orders_pending_stale"], 0)},
            {"label": "Activated orders", "value": metrics["orders_activated"]},
            {"label": "VPN nodes", "value": metrics["nodes_total"]},
            {"label": "Node sync errors", "value": metrics["sync_errors"]},
        ]
        ctx["system_cards"] = [
            {
                "label": "Оплата",
                "value": "Карты включены" if settings.ENABLE_CARD_PAYMENTS else "Только Stars / manual",
                "meta": f"{settings.PAYMENT_PROVIDER} · {settings.CARD_PAYMENT_AMOUNT_MINOR / 100:.0f} {settings.CARD_PAYMENT_CURRENCY}",
            },
            {
                "label": "Cluster mode",
                "value": "Включён" if env_value("VPN_CLUSTER_ENABLED", "0") == "1" else "Выключен",
                "meta": f"health {env_value('VPN_CLUSTER_HEALTHCHECK_INTERVAL_SECONDS', '30')}s · sync {env_value('VPN_CLUSTER_SYNC_INTERVAL_SECONDS', '60')}s",
            },
            {
                "label": "HAProxy frontend",
                "value": f"{env_value('HAPROXY_FRONTEND_BIND_ADDR', '0.0.0.0')}:{env_value('HAPROXY_FRONTEND_PORT', env_value('VPN_PUBLIC_PORT', '-'))}",
                "meta": env_value("HAPROXY_RELOAD_CMD", "reload command not set"),
            },
            {
                "label": "Public VPN",
                "value": f"{env_value('VPN_PUBLIC_HOST', '-')}:{env_value('VPN_PUBLIC_PORT', '-')}",
                "meta": f"inbound #{env_value('XUI_INBOUND_ID', '-')}",
            },
            {
                "label": "Legacy Directus",
                "value": "Enabled" if env_value("CMS_BASE_URL") and env_value("CMS_TOKEN") else "Off",
                "meta": "bot text bridge",
            },
        ]
        ctx["recent_orders"] = safe_get(
            lambda: BotOrder.objects.select_related("user").order_by("-id")[:8],
            [],
        )
        recent_orders_payload: list[dict[str, Any]] = []
        for order in ctx["recent_orders"]:
            recent_orders_payload.append(
                {
                    "id": int(order.id),
                    "user_label": (getattr(getattr(order, "user", None), "username", "") or getattr(getattr(order, "user", None), "client_code", "") or "-"),
                    "status_badge": order_status_display(order),
                    "created_at": getattr(order, "created_at", None),
                }
            )
        ctx["recent_orders_payload"] = recent_orders_payload
        ctx["recent_tickets"] = safe_get(
            lambda: SupportTicket.objects.select_related("user").order_by("-updated_at")[:8],
            [],
        )
        ctx["recent_nodes"] = safe_get(lambda: VPNNode.objects.order_by("-updated_at")[:8], [])
        ctx["action_links"] = [
            {"label": "Тикеты", "url": reverse("backoffice:ticket_list")},
            {"label": "Заказы", "url": reverse("backoffice:bot_order_list")},
            {"label": "Пользователи", "url": reverse("backoffice:bot_user_list")},
            {"label": "Ноды", "url": reverse("backoffice:vpn_node_list")},
            {"label": "Cluster & HAProxy", "url": reverse("backoffice:system_overview")},
        ]
        return ctx


class BaseListView(LegacyContentContextMixin, StaffRequiredMixin, ListView):
    template_name = "backoffice/list.html"
    paginate_by = 25
    context_object_name = "items"

    title = ""
    subtitle = ""
    add_url_name = ""
    edit_url_name = ""
    delete_url_name = ""
    columns: list[tuple[str, str]] = []
    search_fields: list[str] = []
    readonly = False

    def get_queryset(self):
        try:
            qs = super().get_queryset()
            query = (self.request.GET.get("q") or "").strip()
            if query and self.search_fields:
                where = Q()
                for field in self.search_fields:
                    where |= Q(**{f"{field}__icontains": query})
                qs = qs.filter(where)
            return qs
        except (OperationalError, ProgrammingError):
            return self.model.objects.none()

    def get_table_rows(self) -> list[dict[str, Any]]:
        rows = []
        for item in self.object_list:
            cells = [format_cell(getattr(item, field, "")) for field, _ in self.columns]
            rows.append({"obj": item, "cells": cells})
        return rows

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = self.title
        ctx["subtitle"] = self.subtitle
        ctx["query"] = (self.request.GET.get("q") or "").strip()
        ctx["headers"] = [label for _, label in self.columns]
        ctx["rows"] = self.get_table_rows()
        ctx["add_url_name"] = self.add_url_name
        ctx["edit_url_name"] = self.edit_url_name
        ctx["delete_url_name"] = self.delete_url_name
        ctx["readonly"] = self.readonly or self.is_content_readonly()
        ctx["toolbar_actions"] = []
        return self.add_wordpress_context(ctx)


class PostListView(BaseListView):
    model = Post
    title = "Legacy posts"
    subtitle = "Оставлено только для переноса старого контента."
    add_url_name = "backoffice:post_create"
    edit_url_name = "backoffice:post_update"
    delete_url_name = "backoffice:post_delete"
    columns = [
        ("id", "ID"),
        ("title", "Заголовок"),
        ("slug", "Slug"),
        ("is_published", "Опубликован"),
        ("published_at", "Дата публикации"),
        ("updated_at", "Обновлён"),
    ]
    search_fields = ["title", "slug", "summary"]
    content_management = True

    def get_queryset(self):
        return super().get_queryset().order_by("-published_at", "-id")


class PageListView(BaseListView):
    model = Page
    title = "Legacy pages"
    subtitle = "Публичные страницы теперь редактируются в WordPress."
    add_url_name = "backoffice:page_create"
    edit_url_name = "backoffice:page_update"
    delete_url_name = "backoffice:page_delete"
    columns = [
        ("id", "ID"),
        ("title", "Заголовок"),
        ("path", "Путь"),
        ("is_published", "Опубликована"),
        ("show_in_nav", "В меню"),
        ("updated_at", "Обновлена"),
    ]
    search_fields = ["title", "slug", "path", "summary"]
    content_management = True

    def get_queryset(self):
        return super().get_queryset().order_by("nav_order", "title")


class CategoryListView(BaseListView):
    model = Category
    title = "Legacy categories"
    subtitle = "Старые категории Django CMS."
    add_url_name = "backoffice:category_create"
    edit_url_name = "backoffice:category_update"
    delete_url_name = "backoffice:category_delete"
    columns = [
        ("id", "ID"),
        ("title", "Название"),
        ("slug", "Slug"),
        ("is_active", "Активна"),
        ("updated_at", "Обновлена"),
    ]
    search_fields = ["title", "slug"]
    content_management = True


class PostTypeListView(BaseListView):
    model = PostType
    title = "Legacy post types"
    subtitle = "Старые типы постов Django CMS."
    add_url_name = "backoffice:post_type_create"
    edit_url_name = "backoffice:post_type_update"
    delete_url_name = "backoffice:post_type_delete"
    columns = [
        ("id", "ID"),
        ("title", "Название"),
        ("slug", "Slug"),
        ("is_active", "Активен"),
        ("updated_at", "Обновлён"),
    ]
    search_fields = ["title", "slug"]
    content_management = True


class SiteTextListView(BaseListView):
    model = SiteText
    title = "Legacy site texts"
    subtitle = "Наследие Django CMS, не основная панель сайта."
    add_url_name = "backoffice:site_text_create"
    edit_url_name = "backoffice:site_text_update"
    delete_url_name = "backoffice:site_text_delete"
    columns = [("id", "ID"), ("key", "Ключ"), ("updated_at", "Обновлён")]
    search_fields = ["key", "value"]
    content_management = True


class BotUserListView(BaseListView):
    model = BotUser
    title = "Пользователи"
    subtitle = "Единая база bot users и site-only placeholder accounts."
    readonly = True
    columns = [
        ("id", "ID"),
        ("client_code", "Client code"),
        ("telegram_id", "Telegram ID"),
        ("source", "Source"),
        ("username", "Username"),
        ("email", "Email"),
        ("first_name", "Имя"),
        ("created_at", "Создан"),
    ]
    search_fields = ["telegram_id", "username", "first_name", "client_code"]

    def get_queryset(self):
        return super().get_queryset().order_by("-id")

    def get_table_rows(self) -> list[dict[str, Any]]:
        telegram_ids = [int(item.telegram_id) for item in self.object_list if int(item.telegram_id) > 0]
        site_user_ids = [
            int(abs(int(item.telegram_id)) - WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET)
            for item in self.object_list
            if int(item.telegram_id) < 0 and abs(int(item.telegram_id)) > WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET
        ]

        linked_emails = {
            int(link.telegram_id): (getattr(link.user, "email", "") or "")
            for link in LinkedAccount.objects.select_related("user").filter(telegram_id__in=telegram_ids)
        }
        site_emails = {
            int(user.id): (user.email or "")
            for user in User.objects.filter(id__in=site_user_ids).only("id", "email")
        }

        rows = []
        for item in self.object_list:
            telegram_id = int(item.telegram_id)
            email = ""
            if telegram_id > 0:
                email = linked_emails.get(telegram_id, "")
            elif abs(telegram_id) > WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET:
                site_user_id = abs(telegram_id) - WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET
                email = site_emails.get(int(site_user_id), "")
            rows.append(
                {
                    "obj": item,
                    "cells": [
                        item.id,
                        item.client_code,
                        item.telegram_id,
                        user_source_badge(item.telegram_id),
                        item.username or "",
                        email,
                        item.first_name or "",
                        format_cell(item.created_at),
                    ],
                }
            )
        return rows


class BotSubscriptionListView(BaseListView):
    model = BotSubscription
    title = "Подписки"
    subtitle = "Текущие устройства, сроки и импортные конфиги."
    readonly = True
    columns = [
        ("id", "ID"),
        ("user_id", "User ID"),
        ("display_name", "Имя"),
        ("client_email", "3x-ui name"),
        ("is_active", "Статус"),
        ("expires_at", "Истекает"),
        ("updated_at", "Обновлена"),
    ]
    search_fields = ["display_name", "client_email", "user__username", "user__client_code"]

    def get_queryset(self):
        return super().get_queryset().select_related("user").order_by("-id")

    def get_table_rows(self) -> list[dict[str, Any]]:
        rows = []
        for item in self.object_list:
            rows.append(
                {
                    "obj": item,
                    "cells": [
                        item.id,
                        item.user_id,
                        item.display_name,
                        item.client_email,
                        boolean_badge(item.is_active, "active", "inactive"),
                        format_cell(item.expires_at),
                        format_cell(item.updated_at),
                    ],
                }
            )
        return rows


class BotOrderListView(BaseListView):
    model = BotOrder
    title = "Заказы"
    subtitle = "Оплаты картой и Stars в одном журнале. Card pending старше 30 минут считаются stale."
    readonly = True
    columns = [
        ("id", "ID"),
        ("user_id", "User ID"),
        ("username", "Username"),
        ("payment", "Оплата"),
        ("method", "Метод"),
        ("status", "Статус"),
        ("created_at", "Создан"),
        ("paid_at", "Оплачен"),
    ]
    search_fields = [
        "payload",
        "status",
        "telegram_payment_charge_id",
        "provider_payment_charge_id",
        "card_payment_id",
        "user__username",
        "user__first_name",
    ]

    def get_queryset(self):
        return super().get_queryset().select_related("user").order_by("-id")

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        action = (request.POST.get("action") or "").strip()
        if action == "cancel_stale_card_pending":
            updated = cancel_stale_pending_card_orders()
            if updated:
                messages.success(request, f"Отменено stale card pending заказов: {updated}.")
            else:
                messages.info(request, "Stale card pending заказов не найдено.")
        query = (request.GET.get("q") or "").strip()
        target_url = reverse("backoffice:bot_order_list")
        if query:
            target_url = f"{target_url}?q={query}"
        return redirect(target_url)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        stale_pending_count = safe_count(
            BotOrder.objects.filter(
                status="pending",
                payment_method="card",
                created_at__lt=timezone.now() - STALE_PENDING_ORDER_TTL,
            )
        )
        ctx["toolbar_actions"] = [
            {
                "label": "Очистить stale card pending",
                "action": "cancel_stale_card_pending",
                "style": "outline-danger",
                "count": stale_pending_count,
            }
        ]
        return ctx

    def get_table_rows(self) -> list[dict[str, Any]]:
        rows = []
        now = timezone.now()
        for item in self.object_list:
            username = getattr(getattr(item, "user", None), "username", "") or ""
            payment_value = (
                f"{item.amount_minor / 100:.2f} {item.currency_iso}"
                if item.amount_minor
                else f"{item.amount_stars} stars"
            )
            method = item.payment_method or item.channel or "-"
            rows.append(
                {
                    "obj": item,
                    "cells": [
                        item.id,
                        item.user_id,
                        username,
                        payment_value,
                        method,
                        order_status_display(item, now=now),
                        format_cell(item.created_at),
                        format_cell(item.paid_at),
                    ],
                }
            )
        return rows


class SupportTicketListView(BaseListView):
    model = SupportTicket
    title = "Тикеты"
    subtitle = "Telegram support queue with web visibility and replies."
    readonly = True
    columns = [
        ("id", "ID"),
        ("client", "Клиент"),
        ("subject", "Тема"),
        ("status", "Статус"),
        ("updated_at", "Обновлён"),
        ("created_at", "Создан"),
    ]
    search_fields = ["subject", "status", "user__username", "user__first_name", "user__client_code"]

    def get_queryset(self):
        return super().get_queryset().select_related("user").order_by("-updated_at", "-id")

    def get_table_rows(self) -> list[dict[str, Any]]:
        rows = []
        for item in self.object_list:
            user = item.user
            client = f"{getattr(user, 'client_code', '-')}" if user else "-"
            if user and user.username:
                client = f"{client} · @{user.username}"
            rows.append(
                {
                    "obj": item,
                    "cells": [
                        format_html(
                            '<a href="{}">#{}</a>',
                            reverse("backoffice:ticket_detail", args=[item.id]),
                            item.id,
                        ),
                        client,
                        item.subject or "Без темы",
                        ticket_status_badge(item.status),
                        format_cell(item.updated_at),
                        format_cell(item.created_at),
                    ],
                }
            )
        return rows


class SupportTicketDetailView(StaffRequiredMixin, TemplateView):
    template_name = "backoffice/ticket_detail.html"

    def _ticket(self) -> SupportTicket:
        return get_object_or_404(SupportTicket.objects.select_related("user"), pk=self.kwargs["pk"])

    def _messages(self, ticket: SupportTicket):
        return safe_get(
            lambda: SupportMessage.objects.select_related("sender_user")
            .filter(ticket=ticket)
            .order_by("created_at", "id"),
            [],
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ticket = self._ticket()
        ctx["title"] = f"Тикет #{ticket.id}"
        ctx["ticket"] = ticket
        ctx["ticket_messages"] = self._messages(ticket)
        ctx["reply_form"] = kwargs.get("reply_form") or TicketReplyForm()
        return ctx

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        ticket = self._ticket()
        if "close_ticket" in request.POST:
            if ticket.status != "closed":
                ticket.status = "closed"
                ticket.closed_at = timezone.now()
                ticket.updated_at = timezone.now()
                ticket.save(update_fields=["status", "closed_at", "updated_at"])
                messages.success(request, f"Тикет #{ticket.id} закрыт.")
            else:
                messages.info(request, f"Тикет #{ticket.id} уже закрыт.")
            return redirect("backoffice:ticket_detail", pk=ticket.id)

        reply_form = TicketReplyForm(request.POST)
        if not reply_form.is_valid():
            return self.render_to_response(self.get_context_data(reply_form=reply_form))

        reply_text = reply_form.cleaned_data["message"].strip()
        now = timezone.now()
        SupportMessage.objects.create(
            ticket=ticket,
            sender_role="admin",
            sender_user=None,
            message_text=reply_text,
            created_at=now,
        )
        ticket.status = "closed" if reply_form.cleaned_data["close_after_send"] else "open"
        ticket.updated_at = now
        ticket.closed_at = now if reply_form.cleaned_data["close_after_send"] else None
        ticket.save(update_fields=["status", "updated_at", "closed_at"])

        delivery_warning = None
        telegram_id = getattr(ticket.user, "telegram_id", None)
        if telegram_id and telegram_id > 0:
            try:
                send_telegram_text(
                    telegram_id,
                    f"💬 Ответ поддержки по тикету #{ticket.id}\n\n{reply_text}",
                )
            except (RuntimeError, urllib_error.URLError, urllib_error.HTTPError, TimeoutError) as exc:
                delivery_warning = str(exc)
        else:
            delivery_warning = "У пользователя нет реального Telegram ID"

        if delivery_warning:
            messages.warning(
                request,
                f"Ответ сохранён, но не доставлен в Telegram: {delivery_warning}",
            )
        else:
            messages.success(request, f"Ответ по тикету #{ticket.id} отправлен.")
        return redirect("backoffice:ticket_detail", pk=ticket.id)


class VPNNodeListView(BaseListView):
    model = VPNNode
    title = "VPN ноды"
    subtitle = "Состояние нод, load balancer eligibility и health snapshots."
    readonly = True
    columns = [
        ("id", "ID"),
        ("name", "Нода"),
        ("region", "Регион"),
        ("backend", "Backend"),
        ("status", "Статус"),
        ("lb", "LB"),
        ("sync", "Backfill"),
        ("updated_at", "Обновлена"),
    ]
    search_fields = ["name", "region", "backend_host", "xui_base_url"]

    def get_queryset(self):
        return super().get_queryset().order_by("name", "id")

    def get_table_rows(self) -> list[dict[str, Any]]:
        rows = []
        for item in self.object_list:
            backfill_state = "needed" if item.needs_backfill else "ok"
            if item.last_backfill_error:
                backfill_state = "error"
            rows.append(
                {
                    "obj": item,
                    "cells": [
                        item.id,
                        item.name,
                        item.region or "",
                        f"{item.backend_host}:{item.backend_port}",
                        health_badge(item),
                        boolean_badge(item.lb_enabled, "enabled", "off"),
                        sync_state_badge(backfill_state),
                        format_cell(item.updated_at),
                    ],
                }
            )
        return rows


class VPNNodeClientListView(BaseListView):
    model = VPNNodeClient
    title = "Node sync"
    subtitle = "Репликация клиентов между нодами и текущее observed state."
    readonly = True
    columns = [
        ("id", "ID"),
        ("node", "Нода"),
        ("subscription_id", "Subscription"),
        ("client_email", "3x-ui name"),
        ("sync_state", "Sync"),
        ("desired", "Desired"),
        ("observed", "Observed"),
        ("last_synced_at", "Последний sync"),
    ]
    search_fields = ["client_email", "sync_state", "subscription__display_name", "node__name"]

    def get_queryset(self):
        return super().get_queryset().select_related("node", "subscription").order_by("-updated_at", "-id")

    def get_table_rows(self) -> list[dict[str, Any]]:
        rows = []
        for item in self.object_list:
            desired = "enabled" if item.desired_enabled else "disabled"
            observed = (
                "—" if item.observed_enabled is None else ("enabled" if item.observed_enabled else "disabled")
            )
            rows.append(
                {
                    "obj": item,
                    "cells": [
                        item.id,
                        item.node.name if item.node_id else "-",
                        item.subscription_id,
                        item.client_email,
                        sync_state_badge(item.sync_state),
                        f"{desired} · {format_cell(item.desired_expires_at)}",
                        f"{observed} · {format_cell(item.observed_expires_at)}",
                        format_cell(item.last_synced_at),
                    ],
                }
            )
        return rows


class SystemOverviewView(StaffRequiredMixin, TemplateView):
    template_name = "backoffice/system.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Cluster & HAProxy"
        ctx["system_groups"] = [
            {
                "title": "VPN runtime",
                "items": [
                    ("VPN public host", env_value("VPN_PUBLIC_HOST", "-")),
                    ("VPN public port", env_value("VPN_PUBLIC_PORT", "-")),
                    ("3x-ui inbound", env_value("XUI_INBOUND_ID", "-")),
                    ("XUI sub port", env_value("XUI_SUB_PORT", "-")),
                    ("VPN flow", env_value("VPN_FLOW", "xtls-rprx-vision")),
                ],
            },
            {
                "title": "Cluster mode",
                "items": [
                    ("VPN_CLUSTER_ENABLED", env_value("VPN_CLUSTER_ENABLED", "0")),
                    ("Healthcheck interval", f"{env_value('VPN_CLUSTER_HEALTHCHECK_INTERVAL_SECONDS', '30')} sec"),
                    ("Sync interval", f"{env_value('VPN_CLUSTER_SYNC_INTERVAL_SECONDS', '60')} sec"),
                    ("Sync batch size", env_value("VPN_CLUSTER_SYNC_BATCH_SIZE", "200")),
                ],
            },
            {
                "title": "HAProxy",
                "items": [
                    ("Bind address", env_value("HAPROXY_FRONTEND_BIND_ADDR", "0.0.0.0")),
                    ("Frontend port", env_value("HAPROXY_FRONTEND_PORT", env_value("VPN_PUBLIC_PORT", "-"))),
                    ("Template path", env_value("HAPROXY_TEMPLATE_PATH", "ops/haproxy/haproxy.cfg.tpl")),
                    ("Output path", env_value("HAPROXY_OUTPUT_PATH", "/etc/haproxy/haproxy.cfg")),
                    ("Reload command", env_value("HAPROXY_RELOAD_CMD", "-")),
                    ("Binary", env_value("HAPROXY_BIN", "haproxy")),
                ],
            },
        ]
        ctx["ops_commands"] = [
            "python scripts/ops/render_haproxy_cfg.py --env-file .env --dry-run",
            "python scripts/ops/render_haproxy_cfg.py --env-file .env",
        ]
        ctx["notes"] = [
            "Из веб-интерфейса пока показывается operational state и конфиг. Релоад HAProxy и системные команды лучше оставлять на сервере, а не выполнять из Django-контейнера.",
            "Если cluster mode выключен, таблицы нод и sync всё равно полезны как inventory и health audit.",
            "Перед включением lb_enabled на новой ноде: откройте firewall для backend/inbound port, дождитесь health=healthy, закончите backfill и сверьте REALITY key/shortId/SNI с majority пулом.",
            "HAProxy template теперь рассчитан на long-lived TCP sessions. При первом node-add всё равно сделайте dry-run render и тест старым и новым конфигом.",
        ]
        return ctx


class BaseEditView(LegacyContentMutationGuardMixin, StaffRequiredMixin):
    template_name = "backoffice/form.html"
    success_url_name = ""
    title_create = "Создать"
    title_update = "Редактировать"

    def get_success_url(self):
        return reverse(self.success_url_name)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = self.title_update if getattr(self, "object", None) else self.title_create
        ctx["block_editor_asset_version"] = BLOCK_EDITOR_ASSET_VERSION
        return self.add_wordpress_context(ctx)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Сохранено")
        return response


class LegacyContentDeleteView(LegacyContentMutationGuardMixin, StaffRequiredMixin, DeleteView):
    content_management = True


class PostCreateView(BaseEditView, CreateView):
    model = Post
    form_class = BackofficePostForm
    success_url_name = "backoffice:post_list"
    title_create = "Новый пост"
    content_management = True


class PostUpdateView(BaseEditView, UpdateView):
    model = Post
    form_class = BackofficePostForm
    success_url_name = "backoffice:post_list"
    title_update = "Редактирование поста"
    content_management = True


class PostDeleteView(LegacyContentDeleteView):
    model = Post
    template_name = "backoffice/confirm_delete.html"
    success_url_name = "backoffice:post_list"
    success_url = reverse_lazy("backoffice:post_list")


class PageCreateView(BaseEditView, CreateView):
    model = Page
    form_class = BackofficePageForm
    success_url_name = "backoffice:page_list"
    title_create = "Новая страница"
    content_management = True


class PageUpdateView(BaseEditView, UpdateView):
    model = Page
    form_class = BackofficePageForm
    success_url_name = "backoffice:page_list"
    title_update = "Редактирование страницы"
    content_management = True


class PageDeleteView(LegacyContentDeleteView):
    model = Page
    template_name = "backoffice/confirm_delete.html"
    success_url_name = "backoffice:page_list"
    success_url = reverse_lazy("backoffice:page_list")


class CategoryCreateView(BaseEditView, CreateView):
    model = Category
    form_class = BackofficeCategoryForm
    success_url_name = "backoffice:category_list"
    title_create = "Новая категория"
    content_management = True


class CategoryUpdateView(BaseEditView, UpdateView):
    model = Category
    form_class = BackofficeCategoryForm
    success_url_name = "backoffice:category_list"
    title_update = "Редактирование категории"
    content_management = True


class CategoryDeleteView(LegacyContentDeleteView):
    model = Category
    template_name = "backoffice/confirm_delete.html"
    success_url_name = "backoffice:category_list"
    success_url = reverse_lazy("backoffice:category_list")


class PostTypeCreateView(BaseEditView, CreateView):
    model = PostType
    form_class = BackofficePostTypeForm
    success_url_name = "backoffice:post_type_list"
    title_create = "Новый тип поста"
    content_management = True


class PostTypeUpdateView(BaseEditView, UpdateView):
    model = PostType
    form_class = BackofficePostTypeForm
    success_url_name = "backoffice:post_type_list"
    title_update = "Редактирование типа поста"
    content_management = True


class PostTypeDeleteView(LegacyContentDeleteView):
    model = PostType
    template_name = "backoffice/confirm_delete.html"
    success_url_name = "backoffice:post_type_list"
    success_url = reverse_lazy("backoffice:post_type_list")


class SiteTextCreateView(BaseEditView, CreateView):
    model = SiteText
    form_class = BackofficeSiteTextForm
    success_url_name = "backoffice:site_text_list"
    title_create = "Новый текст"
    content_management = True


class SiteTextUpdateView(BaseEditView, UpdateView):
    model = SiteText
    form_class = BackofficeSiteTextForm
    success_url_name = "backoffice:site_text_list"
    title_update = "Редактирование текста"
    content_management = True


class SiteTextDeleteView(LegacyContentDeleteView):
    model = SiteText
    template_name = "backoffice/confirm_delete.html"
    success_url_name = "backoffice:site_text_list"
    success_url = reverse_lazy("backoffice:site_text_list")
