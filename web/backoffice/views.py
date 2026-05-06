from __future__ import annotations

import asyncio
import base64
from collections import Counter
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Avg, Count, Max, Min, Q, QuerySet, Sum
from django.db.utils import OperationalError, ProgrammingError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.utils.html import format_html
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from blog.admin import BLOCK_EDITOR_ASSET_VERSION
from blog.models import Category, Page, Post, PostType, SiteText
from cabinet.models import (
    BotOrder,
    BotSubscription,
    BotUser,
    EdgeServer,
    LinkedAccount,
    SupportMessage,
    SupportTicket,
    VPNNode,
    VPNNodeClient,
    VPNNodeLoadSnapshot,
    VPNNodeMetricSample,
    VPNRebalanceDecision,
    VPNSubscriptionEvent,
    VPNSubscriptionMetricSample,
)
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.xui_client import XUIClient
import qrcode
from src.cluster.provisioner import create_client_on_node
from src.dns_alias import delete_subscription_alias_record, ensure_subscription_alias_record, generate_subscription_alias
from src.cluster.rebalance import emergency_failover_node, manual_rebalance_tick, node_ineligibility_reason, preview_rebalance_plan, score_node
from src.client_naming import build_xui_client_name
from src.config import load_settings
from src.db import DB
from src.subscription_links import build_bot_feed_url, build_subscription_vless_url
from src.vless import build_vless_url
from src.xui_client import NO_EXPIRY_SENTINEL


LOGGER = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2]
HAPROXY_RUNTIME_OUTPUT_PATH = REPO_ROOT / "ops" / "haproxy" / "runtime" / "haproxy.cfg"
VXNODE_METRICS_AGENT_PATH = REPO_ROOT / "scripts" / "ops" / "vxnode_metrics_agent.py"
VXNODE_METRICS_PORT = 9109

from .forms import (
    BackofficeCategoryForm,
    BackofficeEdgeServerForm,
    BackofficePageForm,
    BackofficeSubscriptionCreateForm,
    BackofficeSubscriptionExpiryForm,
    BackofficeUserCreateForm,
    BackofficeUserPasswordResetForm,
    BackofficeVPNNodeForm,
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
BOT_SITE_TEXT_PREFIX = "bot."
BOT_CONTENT_SECTIONS: list[dict[str, Any]] = [
    {
        "title": "Меню и основные кнопки",
        "items": [
            {"key": "menu_trial", "label": "Кнопка меню: Бесплатно 7д", "default": "🎁 Бесплатно 7д", "kind": "button"},
            {"key": "menu_buy", "label": "Кнопка меню: Купить новый доступ", "default": "⭐ Купить новый доступ", "kind": "button"},
            {"key": "menu_renew", "label": "Кнопка меню: Продлить", "default": "🔄 Продлить", "kind": "button"},
            {"key": "menu_mysub", "label": "Кнопка меню: Мой доступ", "default": "📊 Мой доступ", "kind": "button"},
            {"key": "menu_instructions", "label": "Кнопка меню: Инструкция", "default": "💬 Инструкция", "kind": "button"},
            {"key": "menu_support", "label": "Кнопка меню: Поддержка", "default": "🆘 Поддержка", "kind": "button"},
            {"key": "menu_site", "label": "Кнопка меню: Личный кабинет на сайте", "default": "🌐 Личный кабинет на сайте", "kind": "button"},
            {"key": "back_button", "label": "Кнопка: Назад", "default": "⬅️ Назад", "kind": "button"},
            {"key": "buy_new_config_button", "label": "Кнопка: Купить новый доступ в списке конфигов", "default": "⭐ Купить новый доступ", "kind": "button"},
        ],
    },
    {
        "title": "Карточка конфига",
        "items": [
            {"key": "config_copy_button", "label": "Кнопка: Скопировать ссылку", "default": "📋 Скопировать ссылку", "kind": "button"},
            {"key": "config_qr_button", "label": "Кнопка: QR-код", "default": "📷 QR-код", "kind": "button"},
            {"key": "config_renew_button", "label": "Кнопка: Продлить", "default": "🔄 Продлить", "kind": "button"},
            {"key": "config_rename_button", "label": "Кнопка: Переименовать", "default": "✏️ Переименовать", "kind": "button"},
            {"key": "config_delete_button", "label": "Кнопка: Удалить", "default": "🗑️ Удалить", "kind": "button"},
            {"key": "copy_link_hint", "label": "Подсказка после выдачи конфига", "default": "Нажмите «Скопировать ссылку», затем откройте приложение, нажмите + и выберите импорт из буфера обмена.", "kind": "textarea", "rows": 3},
            {"key": "single_device_warning", "label": "Предупреждение про одно устройство", "default": "⚠️ Один доступ нельзя использовать одновременно на двух устройствах.", "kind": "textarea", "rows": 2},
            {"key": "menu_mysub_response", "label": "Текст: краткая карточка доступа", "default": "Доступ активен до: {expires_at}\nID: {client_code}", "kind": "textarea", "rows": 3},
            {"key": "my_configs_list_template", "label": "Текст: список конфигов", "default": "Ваш доступ VXcloud\n\nID: {client_code}\n\nВаши устройства:\n\n{items}", "kind": "textarea", "rows": 6},
            {"key": "my_configs_item_template", "label": "Шаблон одной строки конфига", "default": "{index}. {name}\nДействует до: {expires_at}\nСтатус: {status}", "kind": "textarea", "rows": 4},
            {"key": "my_configs_empty_message", "label": "Текст: пустой список конфигов", "default": "Ваш доступ VXcloud\n\nID: {client_code}\n\nВаши устройства:\n\nСписок устройств пока пуст.", "kind": "textarea", "rows": 5},
        ],
    },
    {
        "title": "Инструкции и навигация",
        "items": [
            {"key": "menu_instructions_response", "label": "Экран: Как подключиться", "default": "Как подключиться\n\nЧтобы всё заработало, нужно сделать два шага:\n\n1. Установить приложение\n2. Оплатить доступ\n\nМы покажем всё по шагам ниже.", "kind": "textarea", "rows": 7},
            {"key": "instructions_install_response", "label": "Экран: Как установить приложение", "default": "Как установить приложение\n\nЕсли вы используете iPhone в России, нужного приложения может не быть в App Store.\n\nЭто нормально — просто нужно временно сменить регион.\n\nСначала:\n• смените регион App Store (на любую другую страну)\n\nЗатем:\n• установите приложение для подключения\n\nПосле установки:\n• можно вернуть регион обратно на Россию\n\nНиже есть подробная инструкция и видео — мы покажем всё по шагам.", "kind": "textarea", "rows": 12},
            {"key": "site_about_response", "label": "Экран: Что можно делать на сайте", "default": "Что можно делать на сайте\n\nВ личном кабинете вы можете:\n\n• увидеть все свои устройства\n• открыть доступ для подключения\n• показать QR-код\n• оплатить новый доступ или продление картой\n• открыть подробные инструкции и видео\n\nСайт и бот работают вместе — ваши данные будут одинаковыми везде.", "kind": "textarea", "rows": 10},
            {"key": "menu_site_response", "label": "Текст: открыть кабинет на сайте", "default": "Откройте личный кабинет на сайте.", "kind": "textarea", "rows": 3},
            {"key": "instructions_install_button", "label": "Кнопка: Установить приложение", "default": "📱 Установить приложение", "kind": "button"},
            {"key": "instructions_access_button", "label": "Кнопка: Мой доступ на экране инструкций", "default": "📊 Мой доступ", "kind": "button"},
            {"key": "instructions_support_button", "label": "Кнопка: Поддержка на экране инструкций", "default": "🆘 Поддержка", "kind": "button"},
            {"key": "instructions_full_guide_button", "label": "Кнопка: Подробная инструкция", "default": "📖 Подробная инструкция", "kind": "button"},
            {"key": "instructions_video_button", "label": "Кнопка: Видео-инструкция", "default": "🎬 Видео-инструкция", "kind": "button"},
            {"key": "menu_instructions_buttons", "label": "Advanced JSON: inline-кнопки для меню инструкций", "default": "", "kind": "textarea", "rows": 6, "help": "Оставьте пустым для штатных кнопок. Формат: JSON массив строк/рядов кнопок."},
            {"key": "instructions_install_buttons", "label": "Advanced JSON: inline-кнопки для экрана установки", "default": "", "kind": "textarea", "rows": 6, "help": "Оставьте пустым для штатных кнопок. Можно переопределить layout полностью."},
            {"key": "site_about_buttons", "label": "Advanced JSON: inline-кнопки для экрана про сайт", "default": "", "kind": "textarea", "rows": 6, "help": "Используется только если вы вручную вызовете этот экран."},
        ],
    },
    {
        "title": "Оплата и восстановление",
        "items": [
            {"key": "pay_card_button", "label": "Кнопка: Оплатить картой", "default": "💳 Оплатить картой", "kind": "button"},
            {"key": "open_instructions", "label": "Кнопка: Инструкция", "default": "💬 Инструкция", "kind": "button"},
            {"key": "open_account", "label": "Кнопка: Личный кабинет на сайте", "default": "🌐 Личный кабинет на сайте", "kind": "button"},
            {"key": "stars_only_notice", "label": "Текст: Stars only notice", "default": "Оплата в боте доступна только через звёзды Telegram ⭐\nДля iPhone обычно используется способ оплаты через мобильный баланс МТС.", "kind": "textarea", "rows": 4},
            {"key": "invoice_title", "label": "Заголовок Stars invoice", "default": "Оплата VXcloud через звёзды", "kind": "input"},
            {"key": "invoice_price_label", "label": "Label Stars price", "default": "Оплата звёздами", "kind": "input"},
            {"key": "invoice_description", "label": "Описание Stars invoice", "default": "Оплата доступа в боте выполняется только через звёзды Telegram. Для iPhone чаще всего — через мобильный баланс МТС.", "kind": "textarea", "rows": 4},
            {"key": "payment_already_processed_message", "label": "Текст: платёж уже обработан", "default": "Платёж уже обработан. Отправляю ваш доступ...", "kind": "textarea", "rows": 3},
            {"key": "provision_delay_message", "label": "Текст: активация задерживается", "default": "Платёж получен, но активация задерживается. Нажмите «📊 Мой доступ» через 10-20 секунд. Если доступ не появится, напишите в поддержку.", "kind": "textarea", "rows": 4},
            {"key": "recovering_subscription_message", "label": "Текст: найден оплаченный заказ", "default": "Найден оплаченный заказ. Пробую восстановить доступ...", "kind": "textarea", "rows": 3},
            {"key": "recover_failed_message", "label": "Текст: восстановление не удалось", "default": "Не удалось автоматически восстановить доступ. Поддержка уже уведомлена, пожалуйста подождите.", "kind": "textarea", "rows": 4},
        ],
    },
    {
        "title": "Поддержка, linking и системные сообщения",
        "items": [
            {"key": "cancel_message", "label": "Текст: отмена действия", "default": "Операция отменена.", "kind": "textarea", "rows": 2},
            {"key": "menu_unknown_message", "label": "Текст: неизвестная команда", "default": "Используйте кнопки меню ниже.", "kind": "textarea", "rows": 2},
            {"key": "support_start_message", "label": "Текст: старт поддержки", "default": "Напишите сообщение одним сообщением в этот чат.\n\nМы получим его вместе с вашим ID и данными по доступу.", "kind": "textarea", "rows": 4},
            {"key": "support_empty_message", "label": "Текст: пустое сообщение в поддержку", "default": "Текст обращения пустой. Нажмите «Поддержка» и попробуйте снова.", "kind": "textarea", "rows": 3},
            {"key": "support_default_subject", "label": "Subject нового тикета", "default": "Запрос из Telegram-бота", "kind": "input"},
            {"key": "support_received_message", "label": "Текст: сообщение принято", "default": "Сообщение отправлено\n\nМы получили ваш запрос и ответим сюда в Telegram.\n\nВаш ID:\n{client_code}", "kind": "textarea", "rows": 5},
            {"key": "support_admin_new_ticket_header", "label": "Текст: шапка для admin-уведомления", "default": "🆘 Новый тикет поддержки", "kind": "input"},
            {"key": "support_admin_reply_subject", "label": "Subject ответа поддержки", "default": "Ответ поддержки", "kind": "input"},
            {"key": "support_admin_reply_prefix", "label": "Текст: ответ поддержки пользователю", "default": "💬 Ответ поддержки:\n\n{message}", "kind": "textarea", "rows": 4},
            {"key": "link_success_message", "label": "Текст: Telegram привязан", "default": "Готово! Telegram успешно привязан к вашему аккаунту на сайте.", "kind": "textarea", "rows": 2},
            {"key": "link_used_message", "label": "Текст: код уже использован", "default": "Этот код уже использован. Сгенерируйте новый код на сайте.", "kind": "textarea", "rows": 2},
            {"key": "link_expired_message", "label": "Текст: код истёк", "default": "Срок действия кода истёк. Сгенерируйте новый код на сайте.", "kind": "textarea", "rows": 2},
            {"key": "link_invalid_message", "label": "Текст: код неверный", "default": "Неверный код привязки. Проверьте код и попробуйте снова.", "kind": "textarea", "rows": 2},
        ],
    },
    {
        "title": "Ссылки и reminders",
        "items": [
            {"key": "site_url", "label": "Базовый URL сайта", "default": "https://vxcloud.ru", "kind": "input"},
            {"key": "account_page_url", "label": "Прямой URL кабинета", "default": "", "kind": "input", "help": "Оставьте пустым, чтобы бот сам собирал magic-link или fallback /account/."},
            {"key": "reminder_expired_message", "label": "Reminder: истёк конфиг", "default": "Истёк конфиг VXcloud: {name}\nДействовал до: {expires_at}\n\nИспользуйте /buy для продления.", "kind": "textarea", "rows": 4},
            {"key": "reminder_1d_message", "label": "Reminder: меньше 24 часов", "default": "Напоминание: конфиг VXcloud скоро истекает\nУстройство: {name}\nДо: {expires_at}", "kind": "textarea", "rows": 3},
            {"key": "reminder_3d_message", "label": "Reminder: меньше 3 дней", "default": "Напоминание: конфиг VXcloud истекает менее чем через 3 дня\nУстройство: {name}\nДо: {expires_at}", "kind": "textarea", "rows": 3},
        ],
    },
]


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


def safe_list(queryset_callable) -> list[Any]:
    try:
        return list(queryset_callable())
    except (OperationalError, ProgrammingError):
        return []


def generate_admin_password(length: int = 16) -> str:
    return get_random_string(length, allowed_chars="abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789")


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


def format_number(value: Any, digits: int = 1, empty: str = "-") -> str:
    if value is None:
        return empty
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return empty


def format_percent(value: Any, digits: int = 0, empty: str = "-") -> str:
    if value is None:
        return empty
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return empty


def format_bytes(value: Any, empty: str = "-") -> str:
    try:
        size = float(value or 0)
    except (TypeError, ValueError):
        return empty
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    for unit in units:
        if abs(size) < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.2f} {unit}"
        size /= 1024
    return empty


def is_no_expiry(value: Any) -> bool:
    return isinstance(value, datetime) and value >= NO_EXPIRY_SENTINEL


def format_subscription_expires_at(value: Any) -> str:
    if value is None or is_no_expiry(value):
        return "Бессрочно"
    formatted = format_cell(value)
    return str(formatted) if formatted else ""


def build_qr_data_url(text: str) -> str:
    img = qrcode.make(text)
    buff = io.BytesIO()
    img.save(buff, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buff.getvalue()).decode('ascii')}"


def _site_base_url() -> str:
    explicit = str(getattr(settings, "WORDPRESS_PUBLIC_SITE_URL", "") or "").strip().rstrip("/")
    if explicit:
        return explicit
    return env_value("WORDPRESS_PUBLIC_SITE_URL", "https://vxcloud.ru").strip().rstrip("/")


def build_subscription_result(subscription: BotSubscription) -> dict[str, Any]:
    vless_url = str(getattr(subscription, "vless_url", "") or "")
    feed_token = str(getattr(subscription, "feed_token", "") or "").strip()
    feed_url = build_bot_feed_url(site_url=_site_base_url(), feed_token=feed_token) if feed_token else ""
    primary_link = feed_url or vless_url
    assigned_node = getattr(subscription, "assigned_node", None)
    current_node = getattr(subscription, "current_node", None) or assigned_node
    desired_node = getattr(subscription, "desired_node", None)
    return {
        "subscription_id": int(getattr(subscription, "id", 0) or 0),
        "display_name": str(getattr(subscription, "display_name", "") or ""),
        "client_email": str(getattr(subscription, "client_email", "") or ""),
        "expires_at_label": format_subscription_expires_at(getattr(subscription, "expires_at", None)),
        "feed_url": feed_url,
        "primary_link": primary_link,
        "raw_vless_url": vless_url,
        "assignment_source": str(getattr(subscription, "assignment_source", "") or ""),
        "migration_state": str(getattr(subscription, "migration_state", "") or ""),
        "assigned_node_label": str(getattr(current_node, "name", "") or ""),
        "current_node_label": str(getattr(current_node, "name", "") or ""),
        "desired_node_label": str(getattr(desired_node, "name", "") or ""),
        "alias_fqdn": str(getattr(subscription, "alias_fqdn", "") or ""),
        "assignment_state": str(getattr(subscription, "assignment_state", "") or ""),
        "compatibility_pool": str(getattr(subscription, "compatibility_pool", "") or ""),
        "overlap_until_label": format_subscription_expires_at(getattr(subscription, "overlap_until", None))
        if getattr(subscription, "overlap_until", None)
        else "",
        "qr_image_data_url": build_qr_data_url(primary_link) if primary_link else "",
    }


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


def edge_health_badge(edge: EdgeServer) -> str:
    if not edge.is_active:
        return status_badge("offline", "secondary")
    if edge.last_health_ok is True:
        return status_badge("healthy", "success")
    if edge.last_health_ok is False:
        return status_badge("error", "danger")
    return status_badge("unknown", "warning")


def edge_role_badge(edge: EdgeServer) -> str:
    return status_badge("primary" if edge.is_primary else "secondary", "primary" if edge.is_primary else "secondary")


def edge_admission_badge(edge: EdgeServer) -> str:
    if not edge.is_active:
        return status_badge("inactive", "secondary")
    if edge.accept_new_clients:
        return status_badge("accepting", "success")
    return status_badge("drain", "warning")


def edge_endpoint(edge: EdgeServer) -> str:
    return f"{edge.public_host}:{edge.frontend_port}"


def env_value(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else str(value)


def subscription_status_state(subscription: BotSubscription, *, now: datetime | None = None) -> tuple[bool, str, str]:
    current_time = now or timezone.now()
    expires_at = getattr(subscription, "expires_at", None)
    revoked_at = getattr(subscription, "revoked_at", None)
    effectively_active = bool(
        getattr(subscription, "is_active", False)
        and expires_at
        and expires_at > current_time
        and revoked_at is None
    )
    if effectively_active:
        return True, "active", "success"
    if revoked_at is not None:
        return False, "revoked", "secondary"
    return False, "expired", "warning"


def bool_env(name: str, default: bool = False) -> bool:
    value = env_value(name, "1" if default else "0").lower()
    return value in {"1", "true", "yes", "on"}


def int_env(name: str, default: int) -> int:
    try:
        return int(env_value(name, str(default)))
    except (TypeError, ValueError):
        return int(default)


def float_env(name: str, default: float) -> float:
    try:
        return float(env_value(name, str(default)))
    except (TypeError, ValueError):
        return float(default)


def _cluster_runtime_settings() -> Any:
    return type(
        "ClusterRuntimeSettings",
        (),
        {
            "vpn_alias_namespace": env_value("VPN_ALIAS_NAMESPACE", "connect.vxcloud.ru"),
            "vpn_alias_provider": env_value("VPN_ALIAS_PROVIDER", "cloudflare"),
            "vpn_alias_default_ttl": int_env("VPN_ALIAS_DEFAULT_TTL", 300),
            "vpn_alias_cutover_ttl": int_env("VPN_ALIAS_CUTOVER_TTL", 60),
            "vpn_alias_overlap_minutes": int_env("VPN_ALIAS_OVERLAP_MINUTES", 310),
            "cloudflare_api_token": env_value("CLOUDFLARE_API_TOKEN", "") or None,
            "cloudflare_zone_id": env_value("CLOUDFLARE_ZONE_ID", "") or None,
            "vpn_public_port": int_env("VPN_PUBLIC_PORT", 443),
            "vpn_tag": env_value("VPN_TAG", "VXcloud"),
            "vpn_flow": env_value("VPN_FLOW", "xtls-rprx-vision"),
            "timezone": env_value("TIMEZONE", "UTC"),
            "vpn_rebalance_interval_seconds": int_env("VPN_REBALANCE_INTERVAL_SECONDS", 604800),
            "vpn_rebalance_workflow_tick_seconds": int_env("VPN_REBALANCE_WORKFLOW_TICK_SECONDS", 300),
            "vpn_rebalance_max_moves_per_node": int_env("VPN_REBALANCE_MAX_MOVES_PER_NODE", 50),
            "vpn_rebalance_move_fraction": float_env("VPN_REBALANCE_MOVE_FRACTION", 0.20),
            "vpn_rebalance_cooldown_hours": int_env("VPN_REBALANCE_COOLDOWN_HOURS", 168),
            "vpn_rebalance_min_score_gap": float_env("VPN_REBALANCE_MIN_SCORE_GAP", 2.5),
        },
    )()


def _alias_runtime_settings() -> Any:
    return _cluster_runtime_settings()


def backoffice_limit_ip() -> int:
    return int_env("BACKOFFICE_MAX_DEVICES_PER_SUB", 0)


def _active_vpn_nodes_snapshot() -> list[dict[str, Any]]:
    try:
        rows = list(
            VPNNode.objects.filter(is_active=True)
            .order_by("id")
            .values(
                "id",
                "xui_base_url",
                "xui_username",
                "xui_password",
                "xui_inbound_id",
                "is_active",
                "public_ip",
                "node_fqdn",
                "compatibility_pool",
                "backend_host",
                "backend_port",
                "backend_weight",
                "bandwidth_capacity_mbps",
                "connection_capacity",
                "lb_enabled",
                "needs_backfill",
                "last_health_ok",
                "last_reality_public_key",
                "last_reality_short_id",
                "last_reality_sni",
                "last_reality_fingerprint",
            )
        )
    except (OperationalError, ProgrammingError):
        return []
    return [dict(row) for row in rows]


def _latest_node_snapshots(node_ids: list[int]) -> dict[int, VPNNodeLoadSnapshot]:
    if not node_ids:
        return {}
    rows = safe_list(lambda: VPNNodeLoadSnapshot.objects.filter(node_id__in=node_ids).order_by("node_id", "-created_at"))
    snapshots: dict[int, VPNNodeLoadSnapshot] = {}
    for row in rows:
        snapshots.setdefault(int(row.node_id), row)
    return snapshots


def _active_assignment_counts(node_ids: list[int]) -> dict[int, int]:
    if not node_ids:
        return {}
    now = timezone.now()
    try:
        rows = list(
            BotSubscription.objects.filter(
                current_node_id__in=node_ids,
                is_active=True,
                revoked_at__isnull=True,
                expires_at__gt=now,
            )
            .values("current_node_id")
            .annotate(total=Count("id"))
        )
    except (OperationalError, ProgrammingError):
        return {}
    return {int(row["current_node_id"]): int(row["total"]) for row in rows if row.get("current_node_id")}


def _recent_move_counts(node_ids: list[int]) -> dict[int, int]:
    if not node_ids:
        return {}
    cutoff = timezone.now() - timedelta(days=7)
    try:
        rows = list(
            VPNRebalanceDecision.objects.filter(to_node_id__in=node_ids, created_at__gte=cutoff)
            .values("to_node_id")
            .annotate(total=Count("id"))
        )
    except (OperationalError, ProgrammingError):
        return {}
    return {int(row["to_node_id"]): int(row["total"]) for row in rows if row.get("to_node_id")}


def _pick_best_assignment_node_snapshot() -> tuple[dict[str, Any] | None, float | None, dict[str, float]]:
    candidates = _active_vpn_nodes_snapshot()
    if not candidates:
        return None, None, {}
    node_ids = [int(item["id"]) for item in candidates]
    snapshot_map = _latest_node_snapshots(node_ids)
    assignment_counts = _active_assignment_counts(node_ids)
    move_counts = _recent_move_counts(node_ids)

    best_node: dict[str, Any] | None = None
    best_score: float | None = None
    best_reasons: dict[str, float] = {}

    for item in candidates:
        node_id = int(item["id"])
        snapshot = snapshot_map.get(node_id)
        payload = dict(item)
        payload["active_assigned_subscriptions"] = assignment_counts.get(node_id, 0)
        payload["observed_enabled_clients"] = int(getattr(snapshot, "observed_enabled_clients", 0) or 0)
        payload["total_traffic_bytes"] = int(getattr(snapshot, "total_traffic_bytes", 0) or 0)
        payload["peak_concurrency"] = int(getattr(snapshot, "peak_concurrency", 0) or 0)
        payload["probe_latency_ms"] = int(getattr(snapshot, "probe_latency_ms", 0) or 0)
        payload["moves_in_week"] = move_counts.get(node_id, 0)
        scored = score_node(payload)
        if scored is None:
            continue
        if best_score is None or scored.score < best_score:
            best_node = payload
            best_score = scored.score
            best_reasons = scored.reasons
    return best_node, best_score, best_reasons


def _deterministic_sub_id(client_uuid: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"vxcloud:{client_uuid}").hex


async def _load_subscription_runtime(
    *,
    cluster_nodes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    async def read_node(base_url: str, username: str, password: str, inbound_id: int, label: str) -> dict[str, Any]:
        if not (base_url and username and password):
            raise RuntimeError(f"{label}: x-ui credentials are not configured")
        xui = XUIClient(
            base_url.rstrip("/"),
            username,
            password,
            total_timeout_seconds=float_env("BACKOFFICE_XUI_TIMEOUT_SECONDS", 6.0),
            max_retries=int_env("BACKOFFICE_XUI_MAX_RETRIES", 0),
        )
        try:
            await xui.start()
            inbound = await xui.get_inbound(inbound_id)
            reality = xui.parse_reality(inbound)
            return {
                "base_url": base_url.rstrip("/"),
                "inbound_id": int(inbound_id),
                "inbound_port": int(inbound["port"]),
                "reality": reality,
            }
        finally:
            await xui.close()

    if bool_env("VPN_CLUSTER_ENABLED", False):
        nodes = sorted(list(cluster_nodes or []), key=lambda item: int(item.get("id", 0) or 0))
        tasks: list[Any] = []
        for node in nodes:
            label = f"node#{int(node.get('id', 0) or 0)}"
            try:
                inbound_id = int(node.get("xui_inbound_id", None))
            except (TypeError, ValueError):
                continue
            tasks.append(
                read_node(
                    str(node.get("xui_base_url", "") or ""),
                    str(node.get("xui_username", "") or ""),
                    str(node.get("xui_password", "") or ""),
                    inbound_id,
                    label,
                )
            )
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if not isinstance(result, Exception):
                    return result
        raise RuntimeError("No active VPN node with readable inbound/reality settings")

    return await read_node(
        env_value("XUI_BASE_URL"),
        env_value("XUI_USERNAME"),
        env_value("XUI_PASSWORD"),
        int_env("XUI_INBOUND_ID", 1),
        "primary",
    )


async def _create_subscription_on_xui(
    *,
    client_uuid: str,
    client_email: str,
    display_name: str,
    expires_at,
    enabled: bool,
    cluster_nodes: list[dict[str, Any]] | None = None,
    xui_sub_id: str | None = None,
) -> list[dict[str, Any]]:
    limit_ip = backoffice_limit_ip()
    flow = env_value("VPN_FLOW", "xtls-rprx-vision")
    results: list[dict[str, Any]] = []

    async def apply_on_node(
        *,
        node_id: int,
        base_url: str,
        username: str,
        password: str,
        inbound_id: int,
        label: str,
    ) -> None:
        if not (base_url and username and password):
            results.append({"node_id": node_id, "ok": False, "error": f"{label}: x-ui credentials are not configured"})
            return
        xui = XUIClient(
            base_url.rstrip("/"),
            username,
            password,
            total_timeout_seconds=float_env("BACKOFFICE_XUI_TIMEOUT_SECONDS", 6.0),
            max_retries=int_env("BACKOFFICE_XUI_MAX_RETRIES", 0),
        )
        try:
            await xui.start()
            await xui.add_client(
                inbound_id,
                client_uuid,
                client_email,
                expires_at,
                limit_ip=limit_ip,
                flow=flow,
                comment=display_name,
                sub_id=xui_sub_id,
                enable=enabled,
            )
            sub_id = xui_sub_id or await xui.get_client_sub_id(inbound_id, client_uuid)
            results.append({"node_id": node_id, "ok": True, "xui_sub_id": sub_id})
        except Exception as exc:
            results.append({"node_id": node_id, "ok": False, "error": str(exc)})
        finally:
            await xui.close()

    if bool_env("VPN_CLUSTER_ENABLED", False):
        tasks: list[Any] = []
        for node in list(cluster_nodes or []):
            try:
                inbound_id = int(node.get("xui_inbound_id", None))
            except (TypeError, ValueError):
                results.append(
                    {
                        "node_id": int(node.get("id", 0) or 0),
                        "ok": False,
                        "error": "invalid x-ui inbound id",
                    }
                )
                continue
            tasks.append(
                apply_on_node(
                    node_id=int(node.get("id", 0) or 0),
                    base_url=str(node.get("xui_base_url", "") or ""),
                    username=str(node.get("xui_username", "") or ""),
                    password=str(node.get("xui_password", "") or ""),
                    inbound_id=inbound_id,
                    label=f"node#{int(node.get('id', 0) or 0)}",
                )
            )
        if tasks:
            await asyncio.gather(*tasks)
        return results

    await apply_on_node(
        node_id=0,
        base_url=env_value("XUI_BASE_URL"),
        username=env_value("XUI_USERNAME"),
        password=env_value("XUI_PASSWORD"),
        inbound_id=int_env("XUI_INBOUND_ID", 1),
        label="primary",
    )
    return results


def ensure_local_main_node() -> VPNNode | None:
    xui_base_url = env_value("XUI_BASE_URL")
    username = env_value("XUI_USERNAME")
    password = env_value("XUI_PASSWORD")
    if not xui_base_url or not username or not password:
        return None

    backend_host = env_value("VPN_NODE_BACKEND_HOST") or env_value("MAIN_NODE_BACKEND_HOST") or "127.0.0.1"
    backend_port = int_env(
        "VPN_NODE_BACKEND_PORT",
        int_env(
            "MAIN_NODE_BACKEND_PORT",
            int_env("XRAY_BACKEND_PORT", 29941),
        ),
    )
    inferred_name = env_value("MAIN_NODE_NAME") or "node-1-main"
    inferred_region = env_value("MAIN_NODE_REGION") or "Germany"
    try:
        existing = (
            VPNNode.objects.filter(
                Q(xui_base_url=xui_base_url)
                | Q(name=inferred_name)
                | (Q(backend_host=backend_host) & Q(backend_port=backend_port))
            )
            .order_by("id")
            .first()
        )
        if existing:
            return existing

        inbound_id = int_env("XUI_INBOUND_ID", 1)
        backend_weight = int_env("MAIN_NODE_BACKEND_WEIGHT", 100)
        now = timezone.now()

        return VPNNode.objects.create(
            name=inferred_name,
            region=inferred_region,
            xui_base_url=xui_base_url,
            xui_username=username,
            xui_password=password,
            xui_inbound_id=inbound_id,
            backend_host=backend_host,
            backend_port=backend_port,
            backend_weight=backend_weight,
            is_active=True,
            lb_enabled=bool_env("MAIN_NODE_LB_ENABLED", False),
            needs_backfill=False,
            created_at=now,
            updated_at=now,
        )
    except Exception:
        return None


class MetricsAgentInstallError(RuntimeError):
    pass


def _node_ssh_host(node: VPNNode) -> str:
    return str(
        getattr(node, "ssh_host", None)
        or getattr(node, "public_ip", None)
        or getattr(node, "backend_host", None)
        or ""
    ).strip()


def _node_metrics_agent_url(node: VPNNode, host: str) -> str:
    public_host = str(getattr(node, "public_ip", None) or getattr(node, "backend_host", None) or host).strip()
    return f"http://{public_host}:{VXNODE_METRICS_PORT}/metrics"


def _build_metrics_agent_install_script(agent_source: str, token: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root or configure passwordless sudo for the SSH user." >&2
  exit 1
fi

INSTALL_DIR="/opt/vxcloud-node-metrics"
ENV_FILE="/etc/vxnode-metrics-agent.env"
SERVICE_FILE="/etc/systemd/system/vxnode-metrics-agent.service"

if ! command -v python3 >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1; then
  apt-get update
  apt-get install -y --no-install-recommends python3 curl
fi
install -d -m 0755 "$INSTALL_DIR"

cat > "$INSTALL_DIR/vxnode_metrics_agent.py" <<'VXNODE_AGENT_PY'
{agent_source}
VXNODE_AGENT_PY
chmod 0755 "$INSTALL_DIR/vxnode_metrics_agent.py"

cat > "$ENV_FILE" <<'VXNODE_AGENT_ENV'
VXNODE_METRICS_BIND=0.0.0.0
VXNODE_METRICS_PORT={VXNODE_METRICS_PORT}
VXNODE_METRICS_TOKEN={token}
VXNODE_METRICS_DISK_PATH=/
VXNODE_METRICS_INTERFACE_PREFIXES=e,eth,en
VXNODE_AGENT_ENV
chmod 0600 "$ENV_FILE"

cat > "$SERVICE_FILE" <<'VXNODE_AGENT_SERVICE'
[Unit]
Description=VXcloud node metrics agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=/etc/vxnode-metrics-agent.env
ExecStart=/usr/bin/python3 /opt/vxcloud-node-metrics/vxnode_metrics_agent.py
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true

[Install]
WantedBy=multi-user.target
VXNODE_AGENT_SERVICE

systemctl daemon-reload
systemctl enable --now vxnode-metrics-agent
if command -v ufw >/dev/null 2>&1; then
  ufw allow {VXNODE_METRICS_PORT}/tcp >/dev/null || true
fi
curl -fsS -H "Authorization: Bearer {token}" "http://127.0.0.1:{VXNODE_METRICS_PORT}/metrics" >/dev/null
systemctl is-active --quiet vxnode-metrics-agent
echo "vxnode metrics agent installed"
"""


def install_metrics_agent_on_node(node: VPNNode) -> str:
    host = _node_ssh_host(node)
    if not host:
        raise MetricsAgentInstallError("Node has no SSH host, public IP, or backend host.")

    ssh_port = int(getattr(node, "ssh_port", None) or 22)
    ssh_user = str(getattr(node, "ssh_user", None) or "root").strip() or "root"
    ssh_password = str(getattr(node, "ssh_password", None) or "")
    if ssh_password and shutil.which("sshpass") is None:
        raise MetricsAgentInstallError("sshpass is not installed in the web container; rebuild the image first.")
    if not ssh_password and shutil.which("ssh") is None:
        raise MetricsAgentInstallError("ssh client is not installed in the web container; rebuild the image first.")
    if not VXNODE_METRICS_AGENT_PATH.exists():
        raise MetricsAgentInstallError(f"Agent source not found: {VXNODE_METRICS_AGENT_PATH}")

    token = str(getattr(node, "metrics_agent_token", None) or "").strip() or get_random_string(48)
    agent_source = VXNODE_METRICS_AGENT_PATH.read_text(encoding="utf-8")
    script = _build_metrics_agent_install_script(agent_source=agent_source, token=token)

    ssh_target = f"{ssh_user}@{host}"
    ssh_args = [
        "ssh",
        "-p",
        str(ssh_port),
        "-o",
        "BatchMode=no",
        "-o",
        "ConnectTimeout=12",
        "-o",
        "ServerAliveInterval=10",
        "-o",
        "ServerAliveCountMax=2",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "UserKnownHostsFile=/tmp/vxcloud_known_hosts",
        ssh_target,
        "bash -s",
    ]
    args = ssh_args
    env = os.environ.copy()
    if ssh_password:
        args = ["sshpass", "-e", *ssh_args]
        env["SSHPASS"] = ssh_password

    try:
        result = subprocess.run(
            args,
            input=script,
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise MetricsAgentInstallError("SSH install timed out after 90 seconds.") from exc
    if result.returncode != 0:
        error_text = (result.stderr or result.stdout or "").strip()
        if len(error_text) > 600:
            error_text = error_text[-600:]
        raise MetricsAgentInstallError(error_text or f"SSH install failed with exit code {result.returncode}.")

    now = timezone.now()
    node.ssh_host = str(getattr(node, "ssh_host", None) or host).strip()
    node.ssh_port = ssh_port
    node.ssh_user = ssh_user
    node.metrics_agent_enabled = True
    node.metrics_agent_url = _node_metrics_agent_url(node, host)
    node.metrics_agent_token = token
    node.updated_at = now
    node.save(
        update_fields=[
            "ssh_host",
            "ssh_port",
            "ssh_user",
            "metrics_agent_enabled",
            "metrics_agent_url",
            "metrics_agent_token",
            "updated_at",
        ]
    )
    output = (result.stdout or "").strip()
    return output.splitlines()[-1] if output else "vxnode metrics agent installed"


def _node_reality_signature(node: VPNNode) -> tuple[str, str, str, str]:
    return (
        str(getattr(node, "last_reality_public_key", "") or "").strip(),
        str(getattr(node, "last_reality_short_id", "") or "").strip(),
        str(getattr(node, "last_reality_sni", "") or "").strip(),
        str(getattr(node, "last_reality_fingerprint", "") or "").strip(),
    )


def _eligible_lb_nodes(nodes: list[VPNNode]) -> tuple[list[VPNNode], tuple[str, str, str, str] | None]:
    eligible = [
        node
        for node in nodes
        if bool(getattr(node, "lb_enabled", False))
        and bool(getattr(node, "is_active", False))
        and not bool(getattr(node, "needs_backfill", False))
        and getattr(node, "last_health_ok", None) is True
    ]
    if not eligible:
        return [], None

    signatures = [_node_reality_signature(node) for node in eligible]
    non_empty = [signature for signature in signatures if any(signature)]
    if not non_empty:
        return eligible, None

    baseline, _ = Counter(non_empty).most_common(1)[0]
    filtered = [node for node in eligible if _node_reality_signature(node) == baseline]
    return filtered, baseline


def _node_lb_reason(node: VPNNode, included_ids: set[int]) -> str:
    if node.id in included_ids:
        return "in pool"
    if not bool(getattr(node, "lb_enabled", False)):
        return "lb disabled"
    if not bool(getattr(node, "is_active", False)):
        return "node inactive"
    if bool(getattr(node, "needs_backfill", False)):
        return "backfill pending"
    if getattr(node, "last_health_ok", None) is False:
        return "health error"
    if getattr(node, "last_health_ok", None) is None:
        return "health unknown"
    return "reality mismatch"


def _haproxy_backend_preview(nodes: list[VPNNode]) -> str:
    lines: list[str] = []
    for node in nodes:
        safe_name = f"node_{int(node.id)}_{str(getattr(node, 'name', 'node') or 'node').replace(' ', '-').lower()}"
        lines.append(
            f"server {safe_name[:64]} {node.backend_host}:{int(node.backend_port)} check weight {max(1, int(getattr(node, 'backend_weight', 100) or 100))}"
        )
    if not lines:
        lines.append("# no eligible lb nodes")
        lines.append("server cluster_empty 127.0.0.1:65535 disabled")
    return "\n".join(lines)


def _render_local_haproxy_runtime() -> str | None:
    script_path = REPO_ROOT / "scripts" / "ops" / "render_haproxy_cfg.py"
    env_path = REPO_ROOT / ".env"
    command = [
        sys.executable,
        str(script_path),
        "--env-file",
        str(env_path),
        "--output-path",
        str(HAPROXY_RUNTIME_OUTPUT_PATH),
        "--skip-validate",
        "--skip-reload",
    ]
    result = subprocess.run(command, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    if result.returncode == 0:
        return None
    details = (result.stderr or result.stdout or "").strip()
    return details or f"render_haproxy_cfg failed with code {result.returncode}"


def _pick_edge_primary_candidate() -> EdgeServer | None:
    return safe_get(
        lambda: EdgeServer.objects.filter(is_active=True)
        .order_by("priority", "id")
        .first()
        or EdgeServer.objects.order_by("priority", "id").first(),
        None,
    )


def _normalize_edge_primary_state(preferred_edge: EdgeServer | None = None) -> EdgeServer | None:
    try:
        if preferred_edge is not None and bool(getattr(preferred_edge, "is_primary", False)):
            EdgeServer.objects.exclude(pk=preferred_edge.pk).update(is_primary=False)
            return preferred_edge

        primaries = list(EdgeServer.objects.filter(is_primary=True).order_by("priority", "id"))
        if primaries:
            keeper = primaries[0]
            EdgeServer.objects.filter(is_primary=True).exclude(pk=keeper.pk).update(is_primary=False)
            return keeper

        candidate = _pick_edge_primary_candidate()
        if candidate is None:
            return None
        EdgeServer.objects.filter(pk=candidate.pk).update(is_primary=True)
        candidate.is_primary = True
        return candidate
    except (OperationalError, ProgrammingError):
        return None


def _promote_replacement_primary_on_delete(deleted_edge_id: int) -> EdgeServer | None:
    try:
        candidate = (
            EdgeServer.objects.exclude(pk=deleted_edge_id)
            .filter(is_active=True)
            .order_by("priority", "id")
            .first()
            or EdgeServer.objects.exclude(pk=deleted_edge_id).order_by("priority", "id").first()
        )
        if candidate is None:
            return None
        EdgeServer.objects.exclude(pk=candidate.pk).update(is_primary=False)
        EdgeServer.objects.filter(pk=candidate.pk).update(is_primary=True)
        candidate.is_primary = True
        return candidate
    except (OperationalError, ProgrammingError):
        return None


def _current_primary_edge(edges: list[EdgeServer]) -> EdgeServer | None:
    primaries = [edge for edge in edges if bool(getattr(edge, "is_primary", False))]
    if primaries:
        primaries.sort(key=lambda item: (int(getattr(item, "priority", 100) or 100), int(item.id)))
        return primaries[0]
    active = [edge for edge in edges if bool(getattr(edge, "is_active", False))]
    if active:
        active.sort(key=lambda item: (int(getattr(item, "priority", 100) or 100), int(item.id)))
        return active[0]
    if edges:
        return sorted(edges, key=lambda item: (int(getattr(item, "priority", 100) or 100), int(item.id)))[0]
    return None


async def _push_subscription_expiry_to_xui(
    subscription: BotSubscription,
    expires_at,
    *,
    cluster_nodes: list[dict[str, Any]] | None = None,
) -> list[str]:
    desired_enabled = bool(
        getattr(subscription, "is_active", False)
        and expires_at > timezone.now()
        and getattr(subscription, "revoked_at", None) is None
    )
    limit_ip = backoffice_limit_ip()
    flow = env_value("VPN_FLOW", "xtls-rprx-vision")
    xui_timeout = float_env("BACKOFFICE_XUI_TIMEOUT_SECONDS", 6.0)
    xui_retries = int_env("BACKOFFICE_XUI_MAX_RETRIES", 0)
    errors: list[str] = []

    async def apply_on_node(base_url: str, username: str, password: str, inbound_id: int, label: str) -> None:
        if not (base_url and username and password):
            errors.append(f"{label}: x-ui credentials are not configured")
            return
        xui = XUIClient(
            base_url.rstrip("/"),
            username,
            password,
            total_timeout_seconds=xui_timeout,
            max_retries=xui_retries,
        )
        try:
            await xui.start()
            await xui.set_client_enabled(
                inbound_id,
                str(subscription.client_uuid),
                str(subscription.client_email),
                expires_at,
                enable=desired_enabled,
                limit_ip=limit_ip,
                flow=flow,
                comment=str(getattr(subscription, "display_name", "") or getattr(subscription, "client_email", "") or ""),
            )
        except Exception as exc:
            errors.append(f"{label}: {exc}")
        finally:
            await xui.close()

    if bool_env("VPN_CLUSTER_ENABLED", False):
        nodes = list(cluster_nodes or [])
        tasks: list[Any] = []
        for node in nodes:
            label = f"node#{int(node.get('id', 0) or 0)}"
            try:
                inbound_id = int(node.get("xui_inbound_id", None))
            except (TypeError, ValueError):
                errors.append(f"{label}: invalid x-ui inbound id")
                continue
            tasks.append(
                apply_on_node(
                    str(node.get("xui_base_url", "") or ""),
                    str(node.get("xui_username", "") or ""),
                    str(node.get("xui_password", "") or ""),
                    inbound_id,
                    label,
                )
            )
        if tasks:
            await asyncio.gather(*tasks)
        return errors

    try:
        inbound_id = int_env("XUI_INBOUND_ID", int(getattr(subscription, "inbound_id", 1) or 1))
    except (TypeError, ValueError):
        errors.append("primary: invalid x-ui inbound id")
        return errors

    await apply_on_node(
        env_value("XUI_BASE_URL"),
        env_value("XUI_USERNAME"),
        env_value("XUI_PASSWORD"),
        inbound_id,
        "primary",
    )
    return errors


async def _await_passthrough(awaitable):
    return await awaitable


def _run_async_from_sync(awaitable):
    return async_to_sync(_await_passthrough)(awaitable)


async def _build_rebalance_preview(settings_obj: Any) -> dict[str, Any]:
    app_settings = load_settings()
    db = DB(app_settings.database_url)
    try:
        await db.connect()
        return await preview_rebalance_plan(db, settings_obj)
    finally:
        await db.close()


async def _run_manual_rebalance(settings_obj: Any) -> dict[str, int]:
    app_settings = load_settings()
    db = DB(app_settings.database_url)
    try:
        await db.connect()
        return await manual_rebalance_tick(db, settings_obj)
    finally:
        await db.close()


async def _run_emergency_failover(
    settings_obj: Any,
    source_node_id: int,
    *,
    allow_healthy_source: bool = False,
) -> dict[str, int]:
    app_settings = load_settings()
    db = DB(app_settings.database_url)
    try:
        await db.connect()
        return await emergency_failover_node(
            db,
            settings_obj,
            source_node_id,
            allow_healthy_source=allow_healthy_source,
        )
    finally:
        await db.close()


def _update_node_client_sync_state(subscription_id: int, **fields: Any) -> None:
    try:
        VPNNodeClient.objects.filter(subscription_id=subscription_id).update(**fields)
    except (OperationalError, ProgrammingError):
        return


async def _delete_subscription_from_xui(
    subscription: BotSubscription,
    *,
    cluster_nodes: list[dict[str, Any]] | None = None,
) -> list[str]:
    limit_ip = backoffice_limit_ip()
    flow = env_value("VPN_FLOW", "xtls-rprx-vision")
    errors: list[str] = []

    async def apply_on_node(base_url: str, username: str, password: str, inbound_id: int, label: str) -> None:
        if not (base_url and username and password):
            errors.append(f"{label}: x-ui credentials are not configured")
            return

        xui = XUIClient(
            base_url.rstrip("/"),
            username,
            password,
            total_timeout_seconds=float_env("BACKOFFICE_XUI_TIMEOUT_SECONDS", 6.0),
            max_retries=int_env("BACKOFFICE_XUI_MAX_RETRIES", 0),
        )
        try:
            await xui.start()
            await xui.delete_client(
                inbound_id,
                str(subscription.client_uuid),
                email=str(subscription.client_email or "") or None,
                expiry=getattr(subscription, "expires_at", None),
                limit_ip=limit_ip,
                flow=flow,
                sub_id=(str(getattr(subscription, "xui_sub_id", "") or "") or None),
            )
        except Exception as exc:
            if "not found" in str(exc).lower():
                return
            errors.append(f"{label}: {exc}")
        finally:
            await xui.close()

    if bool_env("VPN_CLUSTER_ENABLED", False):
        nodes = list(cluster_nodes or [])
        tasks: list[Any] = []
        for node in nodes:
            label = f"node#{int(node.get('id', 0) or 0)}"
            try:
                inbound_id = int(node.get("xui_inbound_id", None))
            except (TypeError, ValueError):
                errors.append(f"{label}: invalid x-ui inbound id")
                continue
            tasks.append(
                apply_on_node(
                    str(node.get("xui_base_url", "") or ""),
                    str(node.get("xui_username", "") or ""),
                    str(node.get("xui_password", "") or ""),
                    inbound_id,
                    label,
                )
            )
        if tasks:
            await asyncio.gather(*tasks)
        return errors

    await apply_on_node(
        env_value("XUI_BASE_URL"),
        env_value("XUI_USERNAME"),
        env_value("XUI_PASSWORD"),
        int_env("XUI_INBOUND_ID", int(getattr(subscription, "inbound_id", 1) or 1)),
        "primary",
    )
    return errors


async def _delete_subscription_alias_from_dns(subscription: BotSubscription) -> str | None:
    alias_fqdn = str(getattr(subscription, "alias_fqdn", "") or "").strip()
    if not alias_fqdn:
        return None
    try:
        await delete_subscription_alias_record(
            settings=load_settings(),
            alias_fqdn=alias_fqdn,
            record_id=str(getattr(subscription, "dns_record_id", "") or "").strip() or None,
        )
    except Exception as exc:
        LOGGER.exception(
            "subscription_dns_alias_delete_failed",
            extra={"subscription_id": int(getattr(subscription, "id", 0) or 0), "alias_fqdn": alias_fqdn},
        )
        return str(exc)
    return None


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


def _bot_override_key(key: str) -> str:
    return f"{BOT_SITE_TEXT_PREFIX}{key}"


def _iter_bot_content_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for section in BOT_CONTENT_SECTIONS:
        items.extend(section["items"])
    return items


class BotContentEditorView(StaffRequiredMixin, LegacyContentContextMixin, TemplateView):
    template_name = "backoffice/bot_content.html"

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        updated = 0
        removed = 0
        for item in _iter_bot_content_items():
            key = str(item["key"])
            value = str(request.POST.get(key, "") or "").replace("\r\n", "\n").strip()
            db_key = _bot_override_key(key)
            if value:
                SiteText.objects.update_or_create(key=db_key, defaults={"value": value})
                updated += 1
            else:
                deleted, _ = SiteText.objects.filter(key=db_key).delete()
                if deleted:
                    removed += 1
        if updated or removed:
            messages.success(
                request,
                f"Bot content обновлён: сохранено {updated}, очищено {removed}. Бот подхватит изменения автоматически.",
            )
        else:
            messages.info(request, "Изменений не найдено.")
        return redirect("backoffice:bot_content_editor")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Bot Settings"
        ctx["subtitle"] = "Визуальное редактирование текстов, кнопок и inline-экранов Telegram-бота."

        overrides = {
            obj.key[len(BOT_SITE_TEXT_PREFIX) :]: obj.value
            for obj in SiteText.objects.filter(key__startswith=BOT_SITE_TEXT_PREFIX).order_by("key")
        }
        sections: list[dict[str, Any]] = []
        total_items = 0
        overridden_items = 0

        for section in BOT_CONTENT_SECTIONS:
            section_items: list[dict[str, Any]] = []
            for item in section["items"]:
                key = str(item["key"])
                current_value = overrides.get(key, "")
                has_override = key in overrides
                if has_override:
                    overridden_items += 1
                total_items += 1
                section_items.append(
                    {
                        "key": key,
                        "label": item["label"],
                        "kind": item.get("kind", "input"),
                        "help": item.get("help", ""),
                        "rows": item.get("rows", 3),
                        "default": item.get("default", ""),
                        "value": current_value,
                        "has_override": has_override,
                    }
                )
            sections.append({"title": section["title"], "items": section_items})

        ctx["sections"] = sections
        ctx["bot_content_stats"] = {
            "total": total_items,
            "overridden": overridden_items,
            "defaulted": max(total_items - overridden_items, 0),
        }
        ctx["notes"] = [
            "Пустое поле удаляет override и возвращает штатный текст или кнопку из кода.",
            "Изменения подхватываются ботом автоматически примерно в течение минуты.",
            "DB overrides из /ops/ являются единственным источником runtime overrides для bot content.",
            "Advanced JSON поля нужны только если вы хотите полностью переопределить layout inline-кнопок.",
        ]
        return self.add_wordpress_context(ctx)


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
            "edges_total": safe_count(EdgeServer.objects.all()),
            "edges_unhealthy": safe_count(
                EdgeServer.objects.filter(is_active=True).exclude(last_health_ok=True)
            ),
            "sync_errors": safe_count(VPNNodeClient.objects.exclude(sync_state="ok")),
        }
        edges = safe_list(lambda: EdgeServer.objects.order_by("priority", "id"))
        primary_edge = _current_primary_edge(edges)
        public_vpn_label = edge_endpoint(primary_edge) if primary_edge else f"{env_value('VPN_PUBLIC_HOST', '-')}:{env_value('VPN_PUBLIC_PORT', '-')}"
        public_vpn_meta = (
            f"primary edge {primary_edge.name}"
            if primary_edge
            else f"inbound #{env_value('XUI_INBOUND_ID', '-')}"
        )
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
            {"label": "HAProxy edges", "value": metrics["edges_total"]},
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
                "value": public_vpn_label,
                "meta": public_vpn_meta,
            },
            {
                "label": "Edge layer",
                "value": "Configured" if metrics["edges_total"] else "Env only",
                "meta": f"{metrics['edges_total']} total · {metrics['edges_unhealthy']} unhealthy",
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
        ctx["recent_edges"] = edges[:6]
        ctx["action_links"] = [
            {"label": "Тикеты", "url": reverse("backoffice:ticket_list")},
            {"label": "Заказы", "url": reverse("backoffice:bot_order_list")},
            {"label": "Пользователи", "url": reverse("backoffice:bot_user_list")},
            {"label": "Ноды", "url": reverse("backoffice:vpn_node_list")},
            {"label": "HAProxy edges", "url": reverse("backoffice:edge_server_list")},
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
        ctx["row_actions_enabled"] = any(row.get("actions") for row in ctx["rows"])
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
    template_name = "backoffice/bot_user_list.html"
    model = BotUser
    title = "Clients"
    subtitle = "Clients with subscriptions collapsed under each row."
    readonly = False
    add_url_name = "backoffice:bot_user_create"
    delete_url_name = "backoffice:bot_user_delete"
    columns = [
        ("client", "Client"),
        ("contact", "Contact"),
        ("source", "Source"),
        ("subscriptions", "Subscriptions"),
        ("created_at", "Created"),
    ]
    search_fields = [
        "telegram_id",
        "username",
        "first_name",
        "client_code",
        "botsubscription__display_name",
        "botsubscription__client_email",
        "botsubscription__alias_fqdn",
    ]

    def get_queryset(self):
        return super().get_queryset().distinct().order_by("-id")

    @staticmethod
    def _client_title(user: BotUser) -> str:
        return (
            str(getattr(user, "first_name", "") or "").strip()
            or str(getattr(user, "username", "") or "").strip()
            or str(getattr(user, "client_code", "") or "").strip()
            or f"Client #{int(getattr(user, 'id', 0) or 0)}"
        )

    @staticmethod
    def _subscription_row(subscription: BotSubscription) -> dict[str, Any]:
        is_active_now, status_label, status_tone = subscription_status_state(subscription)
        current_node = getattr(subscription, "current_node", None) or getattr(subscription, "assigned_node", None)
        desired_node = getattr(subscription, "desired_node", None)
        return {
            "obj": subscription,
            "id": int(getattr(subscription, "id", 0) or 0),
            "display_name": str(getattr(subscription, "display_name", "") or "").strip()
            or str(getattr(subscription, "client_email", "") or "").strip()
            or f"Subscription #{int(getattr(subscription, 'id', 0) or 0)}",
            "client_email": str(getattr(subscription, "client_email", "") or "").strip(),
            "alias_fqdn": str(getattr(subscription, "alias_fqdn", "") or "").strip(),
            "is_active_now": is_active_now,
            "status_badge": status_badge(status_label, status_tone),
            "expires_at": format_subscription_expires_at(getattr(subscription, "expires_at", None)),
            "node_label": str(getattr(current_node, "name", "") or "").strip() or "-",
            "desired_node_label": str(getattr(desired_node, "name", "") or "").strip(),
            "assignment_state": str(getattr(subscription, "assignment_state", "") or "").strip(),
            "updated_at": format_cell(getattr(subscription, "updated_at", None)),
            "edit_url": reverse("backoffice:bot_subscription_expiry_update", args=[subscription.pk]),
            "delete_url": reverse("backoffice:bot_subscription_delete", args=[subscription.pk]),
        }

    @staticmethod
    def _active_subscription_count(subscriptions: list[dict[str, Any]]) -> int:
        return sum(1 for subscription in subscriptions if bool(subscription.get("is_active_now")))

    def _subscriptions_by_user(self) -> dict[int, list[dict[str, Any]]]:
        user_ids = [int(item.id) for item in self.object_list]
        subscriptions_by_user: dict[int, list[dict[str, Any]]] = {user_id: [] for user_id in user_ids}
        if not user_ids:
            return subscriptions_by_user
        subscriptions = (
            BotSubscription.objects.select_related("assigned_node", "current_node", "desired_node")
            .filter(user_id__in=user_ids)
            .order_by("user_id", "-is_active", "-expires_at", "-id")
        )
        for subscription in subscriptions:
            subscriptions_by_user.setdefault(int(subscription.user_id), []).append(self._subscription_row(subscription))
        return subscriptions_by_user

    def get_table_rows(self) -> list[dict[str, Any]]:
        subscriptions_by_user = self._subscriptions_by_user()
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
        linked_auth_user_ids = {
            int(link.telegram_id): int(link.user_id)
            for link in LinkedAccount.objects.filter(telegram_id__in=telegram_ids).only("telegram_id", "user_id")
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
                auth_user_id = linked_auth_user_ids.get(telegram_id)
            elif abs(telegram_id) > WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET:
                site_user_id = abs(telegram_id) - WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET
                email = site_emails.get(int(site_user_id), "")
                auth_user_id = int(site_user_id)
            else:
                auth_user_id = None

            subscriptions = subscriptions_by_user.get(int(item.id), [])
            active_count = self._active_subscription_count(subscriptions)
            client_html = format_html(
                '<div class="bo-client-title">{}</div>'
                '<div class="bo-client-meta">ID {} / {}</div>'
                '{}',
                self._client_title(item),
                item.id,
                item.client_code or "-",
                format_html('<div class="bo-client-meta">@{}</div>', item.username) if item.username else "",
            )
            contact_html = format_html(
                "{}{}",
                format_html("<div>{}</div>", email) if email else format_html('<span class="text-muted">-</span>'),
                format_html('<div class="text-muted">{}</div>', item.first_name) if item.first_name else "",
            )
            rows.append(
                {
                    "obj": item,
                    "cells": [
                        client_html,
                        contact_html,
                        format_html(
                            '<div>{}</div><div class="bo-client-meta">{}</div>',
                            user_source_badge(item.telegram_id),
                            item.telegram_id,
                        ),
                        format_html(
                            '<span class="fw-semibold">{}</span> <span class="text-muted">total</span><br>'
                            '<span class="fw-semibold">{}</span> <span class="text-muted">active</span>',
                            len(subscriptions),
                            active_count,
                        ),
                        format_cell(item.created_at),
                    ],
                    "client_title": self._client_title(item),
                    "subscriptions": subscriptions,
                    "subscription_count": len(subscriptions),
                    "active_subscription_count": active_count,
                    "add_subscription_url": f"{reverse('backoffice:bot_subscription_create')}?user_id={int(item.id)}",
                    "password_url": reverse("backoffice:bot_user_password_reset", args=[item.pk]) if auth_user_id else None,
                }
            )
        return rows


def _site_auth_user_for_bot_user(bot_user: BotUser) -> User | None:
    telegram_id = int(getattr(bot_user, "telegram_id", 0) or 0)
    if telegram_id < 0 and abs(telegram_id) > WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET:
        site_user_id = int(abs(telegram_id) - WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET)
        return User.objects.filter(id=site_user_id).first()
    if telegram_id > 0:
        linked = LinkedAccount.objects.select_related("user").filter(telegram_id=telegram_id).first()
        if linked is not None:
            return linked.user
    return None


class BotUserCreateView(LegacyContentContextMixin, StaffRequiredMixin, TemplateView):
    template_name = "backoffice/form.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Новый пользователь"
        ctx["subtitle"] = "Создание site-only аккаунта сайта и placeholder пользователя в /ops."
        ctx["form"] = kwargs.get("form") or BackofficeUserCreateForm()
        return self.add_wordpress_context(ctx)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        form = BackofficeUserCreateForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        username = form.cleaned_data["username"]
        first_name = form.cleaned_data["first_name"]
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"] or generate_admin_password()

        with transaction.atomic():
            auth_user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
            )
            bot_user = BotUser.objects.create(
                telegram_id=-(WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET + int(auth_user.id)),
                client_code="",
                username=username,
                first_name=first_name or username,
                created_at=timezone.now(),
            )
            if not getattr(bot_user, "client_code", ""):
                bot_user.client_code = f"VX-{int(bot_user.id):06d}"
                bot_user.save(update_fields=["client_code"])

        messages.success(request, f"Пользователь создан. Логин: {username}. Пароль: {password}")
        return redirect("backoffice:bot_user_list")


class BotUserPasswordResetView(LegacyContentContextMixin, StaffRequiredMixin, TemplateView):
    template_name = "backoffice/form.html"

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = get_object_or_404(BotUser, pk=kwargs["pk"])
        self.auth_user = _site_auth_user_for_bot_user(self.object)
        if self.auth_user is None:
            messages.error(request, "У пользователя нет связанного аккаунта сайта, пароль менять некуда.")
            return redirect("backoffice:bot_user_list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        display_name = str(getattr(self.object, "first_name", "") or getattr(self.object, "username", "") or self.auth_user.username)
        ctx["title"] = f"Смена пароля: {display_name}"
        ctx["subtitle"] = f"Логин: {self.auth_user.username}"
        ctx["form"] = kwargs.get("form") or BackofficeUserPasswordResetForm()
        return self.add_wordpress_context(ctx)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        form = BackofficeUserPasswordResetForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        password = form.cleaned_data["password"] or generate_admin_password()
        self.auth_user.set_password(password)
        self.auth_user.save(update_fields=["password"])
        messages.success(request, f"Пароль обновлён для {self.auth_user.username}. Новый пароль: {password}")
        return redirect("backoffice:bot_user_list")


class BotUserDeleteView(LegacyContentContextMixin, StaffRequiredMixin, DeleteView):
    model = BotUser
    template_name = "backoffice/confirm_delete.html"
    success_url = reverse_lazy("backoffice:bot_user_list")

    def _related_counts(self, user: BotUser) -> dict[str, int]:
        subscriptions_qs = BotSubscription.objects.filter(user_id=user.id)
        subscriptions = list(subscriptions_qs)
        subscription_ids = [int(getattr(item, "id", 0) or 0) for item in subscriptions]
        telegram_id = int(getattr(user, "telegram_id", 0) or 0)
        return {
            "subscriptions": len(subscriptions),
            "active_subscriptions": sum(1 for item in subscriptions if subscription_status_state(item)[0]),
            "orders": safe_count(BotOrder.objects.filter(user_id=user.id)),
            "node_clients": safe_count(VPNNodeClient.objects.filter(subscription_id__in=subscription_ids)),
            "support_tickets": safe_count(SupportTicket.objects.filter(user_id=user.id)),
            "support_messages": safe_count(SupportMessage.objects.filter(sender_user_id=user.id)),
            "linked_accounts": safe_count(LinkedAccount.objects.filter(telegram_id=telegram_id)),
        }

    @staticmethod
    def _site_only_auth_user_id(user: BotUser) -> int | None:
        telegram_id = int(getattr(user, "telegram_id", 0) or 0)
        if telegram_id < 0 and abs(telegram_id) > WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET:
            return int(abs(telegram_id) - WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET)
        return None

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        counts = self._related_counts(self.object)
        delete_blocked = counts["active_subscriptions"] > 0
        ctx["title"] = "Удаление пользователя"
        ctx["delete_blocked"] = delete_blocked
        ctx["related_counts"] = counts
        if delete_blocked:
            ctx["delete_warning"] = (
                "У пользователя есть активные подписки. Сначала отключите их или дождитесь окончания срока, "
                "затем удаляйте пользователя."
            )
        else:
            ctx["delete_warning"] = (
                "Будут удалены связанные подписки, заказы и node sync записи. Тикеты и сообщения поддержки "
                "сохранятся, но отвяжутся от пользователя. Если Telegram аккаунт был привязан к сайту, "
                "связка LinkedAccount тоже будет удалена."
            )
        return self.add_wordpress_context(ctx)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object()
        counts = self._related_counts(self.object)
        if counts["active_subscriptions"] > 0:
            messages.error(request, "Нельзя удалить пользователя с активными подписками.")
            return self.render_to_response(self.get_context_data())

        telegram_id = int(getattr(self.object, "telegram_id", 0) or 0)
        site_auth_user_id = self._site_only_auth_user_id(self.object)
        subscriptions_qs = BotSubscription.objects.filter(user_id=self.object.id)
        subscriptions = list(subscriptions_qs)
        subscription_ids = list(subscriptions_qs.values_list("id", flat=True))
        cluster_nodes = _active_vpn_nodes_snapshot() if bool_env("VPN_CLUSTER_ENABLED", False) else None
        xui_errors: list[str] = []
        for subscription in subscriptions:
            xui_errors.extend(
                _run_async_from_sync(_delete_subscription_from_xui(subscription, cluster_nodes=cluster_nodes))
            )
        if xui_errors:
            messages.error(
                request,
                "Не удалось удалить клиента в 3x-ui. Пользователь не удалён: " + "; ".join(xui_errors[:3]),
            )
            return self.render_to_response(self.get_context_data())

        dns_errors = [
            error
            for subscription in subscriptions
            for error in [_run_async_from_sync(_delete_subscription_alias_from_dns(subscription))]
            if error
        ]
        if dns_errors:
            messages.warning(request, "Пользователь удаляется, но часть DNS aliases нужно проверить в Cloudflare.")

        with transaction.atomic():
            LinkedAccount.objects.filter(telegram_id=telegram_id).delete()
            SupportMessage.objects.filter(sender_user_id=self.object.id).update(sender_user_id=None)
            SupportTicket.objects.filter(user_id=self.object.id).update(user_id=None)
            if subscription_ids:
                VPNNodeClient.objects.filter(subscription_id__in=subscription_ids).delete()
            BotOrder.objects.filter(user_id=self.object.id).delete()
            subscriptions_qs.delete()
            if site_auth_user_id is not None:
                User.objects.filter(id=site_auth_user_id).delete()
            self.object.delete()

        messages.success(request, "Пользователь удалён")
        return redirect(self.success_url)


class BotSubscriptionListView(BaseListView):
    model = BotSubscription
    title = "Подписки"
    subtitle = "Текущие устройства, сроки, назначенные ноды и subscription-first delivery."
    readonly = False
    add_url_name = "backoffice:bot_subscription_create"
    edit_url_name = "backoffice:bot_subscription_expiry_update"
    delete_url_name = "backoffice:bot_subscription_delete"
    columns = [
        ("id", "ID"),
        ("user_id", "User ID"),
        ("display_name", "Имя"),
        ("client_email", "3x-ui name"),
        ("assigned_node", "Нода"),
        ("assignment_source", "Источник"),
        ("is_active", "Статус"),
        ("expires_at", "Истекает"),
        ("updated_at", "Обновлена"),
    ]
    search_fields = ["display_name", "client_email", "user__username", "user__client_code"]

    def get_queryset(self):
        return super().get_queryset().select_related("user", "assigned_node").order_by("-id")

    def get_table_rows(self) -> list[dict[str, Any]]:
        rows = []
        for item in self.object_list:
            _, status_label, status_tone = subscription_status_state(item)
            rows.append(
                {
                    "obj": item,
                    "cells": [
                        item.id,
                        item.user_id,
                        item.display_name,
                        item.client_email,
                        getattr(getattr(item, "assigned_node", None), "name", "") or "—",
                        item.assignment_source or "legacy",
                        status_badge(status_label, status_tone),
                        format_subscription_expires_at(item.expires_at),
                        format_cell(item.updated_at),
                    ],
                }
            )
        return rows


class BotSubscriptionCreateView(LegacyContentContextMixin, StaffRequiredMixin, TemplateView):
    template_name = "backoffice/subscription_create.html"

    @staticmethod
    def _session_key() -> str:
        return "backoffice_created_subscription_id"

    def _default_form(self) -> BackofficeSubscriptionCreateForm:
        initial = {"expires_at": ""}
        user_id = str(self.request.GET.get("user_id") or "").strip()
        if user_id.isdigit():
            initial["user_id"] = int(user_id)
        return BackofficeSubscriptionCreateForm(initial=initial)

    def _build_created_result(self, subscription: BotSubscription) -> dict[str, Any]:
        return build_subscription_result(subscription)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        form = kwargs.get("form") or self._default_form()
        created_result = kwargs.get("created_result")
        if created_result is None:
            created_subscription_id = self.request.session.pop(self._session_key(), None)
            if created_subscription_id:
                try:
                    subscription = BotSubscription.objects.get(pk=created_subscription_id)
                except BotSubscription.DoesNotExist:
                    subscription = None
                if subscription is not None:
                    created_result = self._build_created_result(subscription)
        ctx["title"] = "Новая подписка"
        ctx["form"] = form
        ctx["created_result"] = created_result
        return self.add_wordpress_context(ctx)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        form = BackofficeSubscriptionCreateForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        try:
            return self._post_impl(request, form)
        except Exception as exc:
            LOGGER.exception(
                "backoffice_subscription_create_failed",
                extra={"user_id": int(getattr(form.cleaned_data.get("user_id"), "id", 0) or 0)},
            )
            form.add_error(None, f"Не удалось создать подписку: {exc}")
            return self.render_to_response(self.get_context_data(form=form))

    def _post_impl(self, request: HttpRequest, form: BackofficeSubscriptionCreateForm) -> HttpResponse:
        user = form.cleaned_data["user_id"]
        user_id = int(user.id)
        display_name = str(form.cleaned_data["display_name"]).strip()
        expires_at = form.cleaned_data["expires_at"]
        infinite_expiry = expires_at is None
        if infinite_expiry:
            expires_at = NO_EXPIRY_SENTINEL
        elif timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone()).astimezone(dt_timezone.utc)
        else:
            expires_at = expires_at.astimezone(dt_timezone.utc)
        now = timezone.now()
        should_be_active = True if infinite_expiry else expires_at > now
        cluster_mode = bool_env("VPN_CLUSTER_ENABLED", False)
        alias_settings = _alias_runtime_settings()
        assigned_node_snapshot: dict[str, Any] | None = None
        assignment_score: float | None = None
        assignment_reasons: dict[str, float] = {}
        cluster_nodes = None
        if cluster_mode:
            assigned_node_snapshot, assignment_score, assignment_reasons = _pick_best_assignment_node_snapshot()
            if assigned_node_snapshot is None:
                form.add_error(None, "Нет здоровой VPN ноды, доступной для нового назначения.")
                return self.render_to_response(self.get_context_data(form=form))
            cluster_nodes = [assigned_node_snapshot]

        client_uuid = str(uuid.uuid4())
        client_email = build_xui_client_name(
            user_id=user_id,
            client_uuid=client_uuid,
            username=str(getattr(user, "username", "") or "") or None,
            first_name=str(getattr(user, "first_name", "") or "") or None,
            client_code=str(getattr(user, "client_code", "") or "") or None,
        )
        stored_display_name = display_name or client_email
        xui_sub_id = _deterministic_sub_id(client_uuid) if cluster_mode else None
        feed_token = get_random_string(43, allowed_chars="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        alias_fqdn = generate_subscription_alias(alias_settings) if cluster_mode else ""
        compatibility_pool = (
            str((assigned_node_snapshot or {}).get("compatibility_pool") or "").strip() or "default"
            if cluster_mode
            else ""
        )

        try:
            runtime = _run_async_from_sync(_load_subscription_runtime(cluster_nodes=cluster_nodes))
        except Exception as exc:
            form.add_error(None, f"Не удалось прочитать inbound/reality из 3x-ui: {exc}")
            return self.render_to_response(self.get_context_data(form=form))

        reality = runtime["reality"]
        if cluster_mode:
            vless_url = build_subscription_vless_url(
                settings=alias_settings,
                node=assigned_node_snapshot,
                client_uuid=client_uuid,
                reality=reality,
                subscription={"alias_fqdn": alias_fqdn},
            )
        else:
            vless_url = build_vless_url(
                uuid=client_uuid,
                host=str((assigned_node_snapshot or {}).get("backend_host") or env_value("VPN_PUBLIC_HOST")),
                port=int((assigned_node_snapshot or {}).get("backend_port") or int_env("VPN_PUBLIC_PORT", int(runtime["inbound_port"]))),
                tag=env_value("VPN_TAG", "VPN"),
                public_key=reality.public_key,
                short_id=reality.short_id,
                sni=reality.sni,
                fingerprint=reality.fingerprint,
                flow=env_value("VPN_FLOW", "xtls-rprx-vision"),
            )

        subscription = BotSubscription(
            user_id=user_id,
            inbound_id=int(runtime["inbound_id"]),
            client_uuid=client_uuid,
            client_email=client_email,
            xui_sub_id=xui_sub_id,
            display_name=stored_display_name,
            vless_url=vless_url,
            assigned_node_id=int((assigned_node_snapshot or {}).get("id") or 0) or None,
            current_node_id=int((assigned_node_snapshot or {}).get("id") or 0) or None,
            desired_node_id=None,
            alias_fqdn=(alias_fqdn or None),
            assignment_source="backoffice_alias" if cluster_mode else "backoffice_single_node",
            assigned_at=now,
            last_rebalanced_at=None,
            migration_state="ready" if cluster_mode else "single_node",
            assignment_state="steady" if cluster_mode else "single_node",
            ttl_seconds=int(getattr(alias_settings, "vpn_alias_default_ttl", 300)) if cluster_mode else 300,
            dns_provider=(alias_settings.vpn_alias_provider if cluster_mode else ""),
            compatibility_pool=(compatibility_pool or ""),
            feed_token=feed_token,
            expires_at=expires_at,
            is_active=should_be_active,
            revoked_at=None,
            created_at=now,
            updated_at=now,
        )
        try:
            subscription.save(force_insert=True)
        except Exception as exc:
            form.add_error(None, f"Не удалось сохранить подписку в базе: {exc}")
            return self.render_to_response(self.get_context_data(form=form))

        try:
            if cluster_mode and assigned_node_snapshot is not None:
                node_result = _run_async_from_sync(
                    create_client_on_node(
                        assigned_node_snapshot,
                        client_uuid,
                        client_email,
                        xui_sub_id,
                        expires_at,
                        backoffice_limit_ip(),
                        flow=env_value("VPN_FLOW", "xtls-rprx-vision"),
                    )
                )
                provision_results = [
                    {
                        "node_id": int(assigned_node_snapshot["id"]),
                        "ok": True,
                        "xui_sub_id": node_result.get("xui_sub_id"),
                    }
                ]
            else:
                provision_results = _run_async_from_sync(
                    _create_subscription_on_xui(
                        client_uuid=client_uuid,
                        client_email=client_email,
                        display_name=stored_display_name,
                        expires_at=None if infinite_expiry else expires_at,
                        enabled=should_be_active,
                        cluster_nodes=cluster_nodes,
                        xui_sub_id=xui_sub_id,
                    )
                )
        except Exception as exc:
            subscription.delete()
            form.add_error(None, f"Не удалось создать клиента в 3x-ui: {exc}")
            return self.render_to_response(self.get_context_data(form=form))

        successful = [item for item in provision_results if item.get("ok")]
        if not successful:
            subscription.delete()
            form.add_error(None, "Не удалось создать клиента ни на одной ноде 3x-ui.")
            return self.render_to_response(self.get_context_data(form=form))

        primary_sub_id = xui_sub_id or str(successful[0].get("xui_sub_id") or "").strip() or None
        if primary_sub_id != getattr(subscription, "xui_sub_id", None):
            try:
                subscription.xui_sub_id = primary_sub_id
                subscription.updated_at = timezone.now()
                subscription.save(update_fields=["xui_sub_id", "updated_at"])
            except Exception:
                LOGGER.exception(
                    "backoffice_subscription_create_update_sub_id_failed",
                extra={"subscription_id": int(getattr(subscription, "id", 0) or 0)},
                )

        sync_state_errors: list[str] = []
        if cluster_mode and assigned_node_snapshot is not None:
            try:
                alias_result = _run_async_from_sync(
                    ensure_subscription_alias_record(
                        settings=alias_settings,
                        alias_fqdn=alias_fqdn,
                        node=assigned_node_snapshot,
                        ttl=int(getattr(alias_settings, "vpn_alias_default_ttl", 300)),
                        record_id=None,
                    )
                )
                subscription.dns_record_id = alias_result.record_id or ""
                subscription.last_dns_change_id = alias_result.change_id or ""
                subscription.dns_provider = alias_result.provider or subscription.dns_provider
                subscription.ttl_seconds = alias_result.ttl
                subscription.updated_at = timezone.now()
                subscription.save(
                    update_fields=[
                        "dns_record_id",
                        "last_dns_change_id",
                        "dns_provider",
                        "ttl_seconds",
                        "updated_at",
                    ]
                )
            except Exception as exc:
                LOGGER.exception(
                    "backoffice_subscription_create_dns_alias_failed",
                    extra={"subscription_id": int(getattr(subscription, "id", 0) or 0)},
                )
                sync_state_errors.append(f"dns-alias: {exc}")
            try:
                sync_now = timezone.now()
                VPNNodeClient.objects.update_or_create(
                    node_id=int(assigned_node_snapshot["id"]),
                    subscription_id=subscription.id,
                    defaults={
                        "client_uuid": client_uuid,
                        "client_email": client_email,
                        "xui_sub_id": primary_sub_id,
                        "desired_enabled": should_be_active,
                        "desired_expires_at": expires_at,
                        "observed_enabled": should_be_active,
                        "observed_expires_at": expires_at,
                        "sync_state": "ok",
                        "last_synced_at": sync_now,
                        "last_error": None,
                        "updated_at": sync_now,
                        "created_at": sync_now,
                    },
                )
            except Exception as exc:
                LOGGER.exception(
                    "backoffice_subscription_create_sync_state_failed",
                    extra={"subscription_id": int(getattr(subscription, "id", 0) or 0)},
                )
                sync_state_errors.append(str(exc))

        failed = [item for item in provision_results if not item.get("ok")]
        if failed or sync_state_errors:
            problem_chunks: list[str] = []
            if failed:
                problem_chunks.append(
                    "; ".join(
                        f"node#{int(item.get('node_id', 0) or 0)}: {item.get('error')}" for item in failed[:3]
                    )
                )
            if sync_state_errors:
                problem_chunks.append(f"sync-state: {sync_state_errors[0]}")
            messages.warning(
                request,
                "Подписка создана, но есть проблемы синхронизации: " + " | ".join(problem_chunks),
            )
        else:
            messages.success(request, "Подписка создана")
        if cluster_mode and assigned_node_snapshot is not None and assignment_score is not None:
            messages.info(
                request,
                f"Новая подписка назначена на ноду {assigned_node_snapshot.get('name', assigned_node_snapshot['id'])} "
                f"(score {assignment_score:.2f}).",
            )
        created_subscription_id = int(getattr(subscription, "id", 0) or 0)
        if created_subscription_id:
            request.session[self._session_key()] = created_subscription_id
        return redirect("backoffice:bot_subscription_create")

class BotSubscriptionExpiryUpdateView(StaffRequiredMixin, TemplateView):
    template_name = "backoffice/subscription_edit.html"

    def _subscription(self) -> BotSubscription:
        return get_object_or_404(BotSubscription.objects.select_related("user"), pk=self.kwargs["pk"])

    def _initial(self, subscription: BotSubscription) -> dict[str, Any]:
        current = getattr(subscription, "expires_at", None) or timezone.now()
        if is_no_expiry(current):
            expires_at = ""
        else:
            expires_at = timezone.localtime(current).strftime("%d/%m/%Y %H:%M")
        return {
            "user_id": getattr(subscription, "user_id", None),
            "display_name": getattr(subscription, "display_name", "") or "",
            "expires_at": expires_at,
        }

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        subscription = self._subscription()
        form = kwargs.get("form") or BackofficeSubscriptionExpiryForm(initial=self._initial(subscription))
        title_name = subscription.display_name or subscription.client_email or f"#{subscription.id}"
        ctx["title"] = f"Изменить срок: {title_name}"
        ctx["form"] = form
        ctx["subscription_result"] = build_subscription_result(subscription)
        return ctx

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        subscription = self._subscription()
        form = BackofficeSubscriptionExpiryForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        new_user_id = int(form.cleaned_data["user_id"] or getattr(subscription, "user_id", 0) or 0)
        new_display_name = str(form.cleaned_data["display_name"] or getattr(subscription, "display_name", "") or "").strip()
        expires_at = form.cleaned_data["expires_at"]
        if expires_at is None:
            expires_at = NO_EXPIRY_SENTINEL
        elif timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone())
        expires_at = expires_at.astimezone(dt_timezone.utc)
        change_time = timezone.now()
        should_be_active = bool(expires_at > change_time and getattr(subscription, "revoked_at", None) is None)

        with transaction.atomic():
            subscription.user_id = new_user_id
            subscription.display_name = new_display_name or str(getattr(subscription, "client_email", "") or "")
            subscription.expires_at = expires_at
            subscription.is_active = should_be_active
            subscription.updated_at = change_time
            subscription.save(update_fields=["user_id", "display_name", "expires_at", "is_active", "updated_at"])
            _update_node_client_sync_state(
                subscription.id,
                desired_enabled=should_be_active,
                desired_expires_at=expires_at,
                sync_state="pending",
                last_error=None,
                updated_at=change_time,
            )

        cluster_nodes = _active_vpn_nodes_snapshot() if bool_env("VPN_CLUSTER_ENABLED", False) else None
        try:
            errors = _run_async_from_sync(
                _push_subscription_expiry_to_xui(subscription, expires_at, cluster_nodes=cluster_nodes)
            )
        except Exception:
            LOGGER.exception(
                "backoffice_subscription_expiry_push_failed",
                extra={"subscription_id": int(getattr(subscription, "id", 0) or 0)},
            )
            _update_node_client_sync_state(
                subscription.id,
                sync_state="error",
                last_error="backoffice expiry push failed",
                updated_at=timezone.now(),
            )
            messages.warning(
                request,
                "Срок обновлён в базе, но отправка изменения в 3x-ui завершилась ошибкой. Проверьте ноды вручную.",
            )
            return redirect("backoffice:bot_subscription_expiry_update", pk=subscription.id)
        if errors:
            _update_node_client_sync_state(
                subscription.id,
                sync_state="error",
                last_error="; ".join(errors[:3])[:1000],
                updated_at=timezone.now(),
            )
            messages.warning(request, "Срок обновлён в базе, но не везде применился в 3x-ui: " + "; ".join(errors[:3]))
        else:
            synced_at = timezone.now()
            _update_node_client_sync_state(
                subscription.id,
                observed_enabled=should_be_active,
                observed_expires_at=expires_at,
                sync_state="ok",
                last_error=None,
                last_synced_at=synced_at,
                updated_at=synced_at,
            )
            messages.success(request, "Срок подписки обновлён в базе и 3x-ui.")
        return redirect("backoffice:bot_subscription_expiry_update", pk=subscription.id)


class BotSubscriptionDeleteView(LegacyContentContextMixin, StaffRequiredMixin, DeleteView):
    model = BotSubscription
    template_name = "backoffice/confirm_delete.html"
    success_url = reverse_lazy("backoffice:bot_subscription_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        is_active, _, _ = subscription_status_state(self.object)
        title_name = self.object.display_name or self.object.client_email or f"#{self.object.id}"
        ctx["title"] = "Delete subscription"
        ctx["object_label"] = title_name
        ctx["delete_blocked"] = is_active
        if is_active:
            ctx["delete_warning"] = "Active subscriptions cannot be deleted. Expire or revoke it first."
        else:
            ctx["delete_warning"] = "VXcloud will delete the DB record, node sync rows, DNS alias, and best-effort 3x-ui client."
        return self.add_wordpress_context(ctx)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object()
        is_active, _, _ = subscription_status_state(self.object)
        if is_active:
            messages.error(request, "Cannot delete an active subscription. Expire or revoke it first.")
            return self.render_to_response(self.get_context_data())

        cluster_nodes = _active_vpn_nodes_snapshot() if bool_env("VPN_CLUSTER_ENABLED", False) else None
        try:
            xui_errors = _run_async_from_sync(_delete_subscription_from_xui(self.object, cluster_nodes=cluster_nodes))
        except Exception:
            LOGGER.exception(
                "backoffice_subscription_delete_xui_failed",
                extra={"subscription_id": int(getattr(self.object, "id", 0) or 0)},
            )
            messages.warning(
                request,
                "3x-ui cleanup failed, but VXcloud will delete the inactive subscription. Check the old node manually if needed.",
            )
            xui_errors = []
        if xui_errors:
            messages.warning(
                request,
                "VXcloud will delete the inactive subscription, but 3x-ui cleanup had warnings: " + "; ".join(xui_errors[:3]),
            )

        dns_error = _run_async_from_sync(_delete_subscription_alias_from_dns(self.object))
        if dns_error:
            messages.warning(request, "Subscription is being deleted, but DNS alias cleanup should be checked in Cloudflare.")

        with transaction.atomic():
            try:
                VPNNodeClient.objects.filter(subscription_id=self.object.id).delete()
            except (OperationalError, ProgrammingError):
                LOGGER.warning(
                    "backoffice_subscription_delete_node_client_cleanup_skipped",
                    extra={"subscription_id": int(getattr(self.object, "id", 0) or 0)},
                )
            self.object.delete()

        messages.success(request, "Subscription deleted.")
        return redirect(self.success_url)

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
    readonly = False
    add_url_name = "backoffice:vpn_node_create"
    edit_url_name = "backoffice:vpn_node_update"
    delete_url_name = "backoffice:vpn_node_delete"
    columns = [
        ("id", "ID"),
        ("name", "Нода"),
        ("region", "Регион"),
        ("backend", "Backend / endpoint"),
        ("pool", "Pool"),
        ("status", "Статус"),
        ("lb", "LB"),
        ("assigned", "Назначено"),
        ("score", "7d score"),
        ("rebalanced_at", "Rebalance"),
        ("sync", "Backfill"),
        ("updated_at", "Обновлена"),
    ]
    search_fields = ["name", "region", "backend_host", "xui_base_url"]

    def get_queryset(self):
        ensure_local_main_node()
        return super().get_queryset().order_by("name", "id")

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        action = str(request.POST.get("action") or "").strip()
        if action != "install_metrics_agent":
            messages.error(request, "Unknown node action.")
            return redirect("backoffice:vpn_node_list")

        node = get_object_or_404(VPNNode, pk=request.POST.get("node_id"))
        try:
            detail = install_metrics_agent_on_node(node)
        except MetricsAgentInstallError as exc:
            messages.error(request, f"Metrics agent install failed for {node.name}: {exc}")
        else:
            messages.success(request, f"Metrics agent installed on {node.name}: {detail}")
        return redirect("backoffice:vpn_node_list")

    def get_table_rows(self) -> list[dict[str, Any]]:
        node_ids = [int(item.id) for item in self.object_list]
        assignment_counts = _active_assignment_counts(node_ids)
        snapshot_map = _latest_node_snapshots(node_ids)
        rebalance_events = safe_list(
            lambda: VPNRebalanceDecision.objects.filter(Q(from_node_id__in=node_ids) | Q(to_node_id__in=node_ids)).order_by("-created_at")
        )
        last_rebalanced_at: dict[int, Any] = {}
        for decision in rebalance_events:
            from_node_id = int(decision.from_node_id or 0)
            to_node_id = int(decision.to_node_id or 0)
            if from_node_id > 0:
                last_rebalanced_at.setdefault(from_node_id, decision.created_at)
            if to_node_id > 0:
                last_rebalanced_at.setdefault(to_node_id, decision.created_at)

        rows = []
        for item in self.object_list:
            backfill_state = "needed" if item.needs_backfill else "ok"
            if item.last_backfill_error:
                backfill_state = "error"
            snapshot = snapshot_map.get(int(item.id))
            payload = {
                "id": int(item.id),
                "name": item.name,
                "is_active": bool(item.is_active),
                "lb_enabled": bool(item.lb_enabled),
                "needs_backfill": bool(item.needs_backfill),
                "last_health_ok": item.last_health_ok,
                "compatibility_pool": str(item.compatibility_pool or "default"),
                "last_reality_public_key": item.last_reality_public_key,
                "last_reality_short_id": item.last_reality_short_id,
                "last_reality_sni": item.last_reality_sni,
                "last_reality_fingerprint": item.last_reality_fingerprint,
                "backend_weight": int(item.backend_weight or 100),
                "bandwidth_capacity_mbps": int(item.bandwidth_capacity_mbps or 0),
                "connection_capacity": int(item.connection_capacity or 0),
                "active_assigned_subscriptions": assignment_counts.get(int(item.id), 0),
                "observed_enabled_clients": int(getattr(snapshot, "observed_enabled_clients", 0) or 0),
                "weekly_traffic_bytes": int(getattr(snapshot, "total_traffic_bytes", 0) or 0),
                "peak_concurrency": int(getattr(snapshot, "peak_concurrency", 0) or 0),
                "probe_latency_ms": int(getattr(snapshot, "probe_latency_ms", 0) or 0),
                "moves_in_week": 0,
            }
            issue = node_ineligibility_reason(payload, compatibility_pool=str(item.compatibility_pool or "default"))
            scored = score_node(payload, compatibility_pool=str(item.compatibility_pool or "default")) if issue is None else None
            score_label = "—" if scored is None else f"{float(scored.score):.2f}"
            backend_label = f"{item.backend_host}:{item.backend_port}"
            if item.node_fqdn or item.public_ip:
                endpoint_parts = [part for part in [item.node_fqdn, item.public_ip] if part]
                backend_label = f"{backend_label} → {' / '.join(endpoint_parts)}"
            lb_badge = boolean_badge(item.lb_enabled, "enabled", "off")
            if issue:
                lb_badge = format_html("{} {}", lb_badge, status_badge(issue, "secondary"))
            rows.append(
                {
                    "obj": item,
                    "actions": [
                        {
                            "action": "install_metrics_agent",
                            "label": "Install stats agent",
                            "style": "outline-dark",
                            "confirm": f"Install/update VXcloud stats agent on {item.name}?",
                        }
                    ],
                    "cells": [
                        item.id,
                        item.name,
                        item.region or "",
                        backend_label,
                        str(item.compatibility_pool or "default"),
                        health_badge(item),
                        lb_badge,
                        assignment_counts.get(int(item.id), 0),
                        score_label,
                        format_cell(last_rebalanced_at.get(int(item.id))),
                        sync_state_badge(backfill_state),
                        format_cell(item.updated_at),
                    ],
                }
            )
        return rows


class VPNNodeStatsView(LegacyContentContextMixin, StaffRequiredMixin, TemplateView):
    template_name = "backoffice/node_stats.html"
    title = "Statistics"
    subtitle = "Node telemetry, client usage, movement history, logs and projections."

    @staticmethod
    def _pct(used: Any, total: Any) -> float | None:
        try:
            used_float = float(used or 0)
            total_float = float(total or 0)
        except (TypeError, ValueError):
            return None
        if total_float <= 0:
            return None
        return max(0.0, min(100.0, used_float / total_float * 100.0))

    @staticmethod
    def _delta(values: list[int]) -> int:
        if len(values) < 2:
            return 0
        return max(max(values) - min(values), 0)

    @staticmethod
    def _compact_reason(value: Any) -> str:
        text = str(value or "").strip()
        return text if text else "-"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = self.title
        ctx["subtitle"] = self.subtitle

        now = timezone.now()
        since_24h = now - timedelta(hours=24)
        since_7d = now - timedelta(days=7)
        since_30d = now - timedelta(days=30)
        nodes = safe_list(lambda: VPNNode.objects.order_by("name", "id"))
        node_ids = [int(node.id) for node in nodes]
        latest_snapshots = _latest_node_snapshots(node_ids)
        active_assignments = _active_assignment_counts(node_ids)

        node_metric_rows = safe_list(
            lambda: VPNNodeMetricSample.objects.filter(node_id__in=node_ids, observed_at__gte=since_30d)
            .order_by("node_id", "-observed_at")
        )
        latest_node_metrics: dict[int, VPNNodeMetricSample] = {}
        metric_history: dict[int, list[VPNNodeMetricSample]] = {node_id: [] for node_id in node_ids}
        for sample in node_metric_rows:
            node_id = int(sample.node_id)
            latest_node_metrics.setdefault(node_id, sample)
            metric_history.setdefault(node_id, []).append(sample)
        for history in metric_history.values():
            history.sort(key=lambda item: item.observed_at)

        load_snapshot_stats = {
            int(row["node_id"]): row
            for row in safe_list(
                lambda: VPNNodeLoadSnapshot.objects.filter(node_id__in=node_ids, created_at__gte=since_7d)
                .values("node_id")
                .annotate(
                    sample_count=Count("id"),
                    healthy_samples=Count("id", filter=Q(health_ok=True)),
                    failed_samples=Count("id", filter=Q(health_ok=False)),
                    avg_peak_concurrency=Avg("peak_concurrency"),
                    max_peak_concurrency=Max("peak_concurrency"),
                    avg_probe_latency_ms=Avg("probe_latency_ms"),
                    max_probe_latency_ms=Max("probe_latency_ms"),
                    avg_score_hint=Avg("score_hint"),
                )
            )
            if row.get("node_id")
        }

        subscription_metric_rows = safe_list(
            lambda: VPNSubscriptionMetricSample.objects.select_related("subscription", "subscription__user", "node")
            .filter(observed_at__gte=since_30d)
            .order_by("subscription_id", "observed_at")
        )
        subscription_history: dict[int, list[VPNSubscriptionMetricSample]] = {}
        for sample in subscription_metric_rows:
            subscription_history.setdefault(int(sample.subscription_id), []).append(sample)

        subscriptions = safe_list(
            lambda: BotSubscription.objects.select_related("user", "current_node", "assigned_node")
            .filter(is_active=True, revoked_at__isnull=True)
            .order_by("user__first_name", "user__username", "id")
        )

        rows = []
        total_active_assignments = 0
        healthy_nodes = 0
        eligible_nodes = 0
        failed_metric_samples = 0
        fleet_traffic_30d = 0
        online_clients = 0

        for node in nodes:
            node_id = int(node.id)
            latest_load = latest_snapshots.get(node_id)
            latest_metric = latest_node_metrics.get(node_id)
            load_stats = load_snapshot_stats.get(node_id, {})
            history = metric_history.get(node_id, [])
            assigned_now = int(active_assignments.get(node_id, 0))
            capacity = int(getattr(node, "connection_capacity", 0) or 0)
            capacity_pct = self._pct(assigned_now, capacity)
            sample_count = int(load_stats.get("sample_count") or 0)
            healthy_sample_count = int(load_stats.get("healthy_samples") or 0)
            failed_sample_count = int(load_stats.get("failed_samples") or 0)
            failed_metric_samples += sum(1 for sample in history if sample.agent_error or sample.xui_error)
            health_pct = self._pct(healthy_sample_count, sample_count)
            memory_pct = self._pct(getattr(latest_metric, "memory_used_bytes", None), getattr(latest_metric, "memory_total_bytes", None))
            swap_pct = self._pct(getattr(latest_metric, "swap_used_bytes", None), getattr(latest_metric, "swap_total_bytes", None))
            disk_pct = self._pct(getattr(latest_metric, "disk_used_bytes", None), getattr(latest_metric, "disk_total_bytes", None))
            net_values = [int((sample.net_rx_bytes or 0) + (sample.net_tx_bytes or 0)) for sample in history]
            traffic_30d = self._delta(net_values)
            fleet_traffic_30d += traffic_30d

            latest_payload = {
                "id": node_id,
                "name": node.name,
                "is_active": bool(node.is_active),
                "lb_enabled": bool(node.lb_enabled),
                "needs_backfill": bool(node.needs_backfill),
                "last_health_ok": node.last_health_ok,
                "compatibility_pool": str(node.compatibility_pool or "default"),
                "last_reality_public_key": node.last_reality_public_key,
                "last_reality_short_id": node.last_reality_short_id,
                "last_reality_sni": node.last_reality_sni,
                "last_reality_fingerprint": node.last_reality_fingerprint,
                "backend_weight": int(node.backend_weight or 100),
                "bandwidth_capacity_mbps": int(node.bandwidth_capacity_mbps or 0),
                "connection_capacity": capacity,
                "active_assigned_subscriptions": assigned_now,
                "observed_enabled_clients": int(getattr(latest_load, "observed_enabled_clients", 0) or 0),
                "weekly_traffic_bytes": int(getattr(latest_load, "total_traffic_bytes", 0) or 0),
                "peak_concurrency": int(getattr(latest_load, "peak_concurrency", 0) or 0),
                "probe_latency_ms": int(getattr(latest_load, "probe_latency_ms", 0) or 0),
                "moves_in_week": 0,
            }
            issue = node_ineligibility_reason(latest_payload, compatibility_pool=str(node.compatibility_pool or "default"))
            scored = score_node(latest_payload, compatibility_pool=str(node.compatibility_pool or "default")) if issue is None else None

            total_active_assignments += assigned_now
            online_clients += int(getattr(latest_load, "observed_enabled_clients", 0) or 0)
            if node.last_health_ok is True:
                healthy_nodes += 1
            if issue is None:
                eligible_nodes += 1

            rows.append(
                {
                    "node": node,
                    "endpoint": f"{node.backend_host}:{node.backend_port}",
                    "public_endpoint": " / ".join(part for part in [node.node_fqdn, node.public_ip] if part) or "-",
                    "pool": str(node.compatibility_pool or "default"),
                    "agent": boolean_badge(bool(getattr(node, "metrics_agent_enabled", False)), "agent on", "agent off"),
                    "health": health_badge(node),
                    "eligibility": status_badge("eligible", "success") if issue is None else status_badge(issue, "secondary"),
                    "lb": boolean_badge(bool(node.lb_enabled), "enabled", "off"),
                    "backfill": sync_state_badge("needed" if node.needs_backfill else "ok"),
                    "assigned_now": assigned_now,
                    "observed_now": int(getattr(latest_load, "observed_enabled_clients", 0) or 0),
                    "peak_now": int(getattr(latest_load, "peak_concurrency", 0) or 0),
                    "peak_avg": format_number(load_stats.get("avg_peak_concurrency")),
                    "peak_max": int(load_stats.get("max_peak_concurrency") or 0),
                    "traffic_30d": format_bytes(traffic_30d),
                    "traffic_value": traffic_30d,
                    "traffic_latest": format_bytes(getattr(latest_load, "total_traffic_bytes", None)),
                    "latency_now": "-" if getattr(latest_load, "probe_latency_ms", None) is None else f"{int(getattr(latest_load, 'probe_latency_ms') or 0)} ms",
                    "latency_avg": "-" if load_stats.get("avg_probe_latency_ms") is None else f"{format_number(load_stats.get('avg_probe_latency_ms'), 0)} ms",
                    "latency_max": "-" if load_stats.get("max_probe_latency_ms") is None else f"{int(load_stats.get('max_probe_latency_ms') or 0)} ms",
                    "capacity": f"{capacity} conn" if capacity else "-",
                    "capacity_pct": format_percent(capacity_pct, 1),
                    "bandwidth": f"{int(node.bandwidth_capacity_mbps or 0)} Mbps" if node.bandwidth_capacity_mbps else "-",
                    "cpu_pct": format_percent(getattr(latest_metric, "cpu_percent", None), 1),
                    "cpu_value": float(getattr(latest_metric, "cpu_percent", 0) or 0),
                    "memory": f"{format_bytes(getattr(latest_metric, 'memory_used_bytes', None))} / {format_bytes(getattr(latest_metric, 'memory_total_bytes', None))}",
                    "memory_pct": format_percent(memory_pct, 1),
                    "memory_value": float(memory_pct or 0),
                    "swap": f"{format_bytes(getattr(latest_metric, 'swap_used_bytes', None))} / {format_bytes(getattr(latest_metric, 'swap_total_bytes', None))}",
                    "swap_pct": format_percent(swap_pct, 1),
                    "swap_value": float(swap_pct or 0),
                    "disk": f"{format_bytes(getattr(latest_metric, 'disk_used_bytes', None))} / {format_bytes(getattr(latest_metric, 'disk_total_bytes', None))}",
                    "disk_pct": format_percent(disk_pct, 1),
                    "disk_value": float(disk_pct or 0),
                    "load": "- / - / -"
                    if latest_metric is None
                    else f"{format_number(latest_metric.load1, 2)} / {format_number(latest_metric.load5, 2)} / {format_number(latest_metric.load15, 2)}",
                    "sockets": "-"
                    if latest_metric is None
                    else f"TCP {latest_metric.tcp_connections or 0} / UDP {latest_metric.udp_sockets or 0}",
                    "xray": str(getattr(latest_metric, "xray_state", "") or "-"),
                    "score_now": "-" if scored is None else f"{float(scored.score):.2f}",
                    "score_avg": format_number(load_stats.get("avg_score_hint")),
                    "score_reasons": ", ".join(f"{key}={float(value):.2f}" for key, value in sorted((getattr(scored, "reasons", None) or {}).items())) if scored else "",
                    "samples": sample_count,
                    "healthy_samples": healthy_sample_count,
                    "failed_samples": failed_sample_count,
                    "health_pct": format_percent(health_pct, 0),
                    "latest_snapshot_at": format_cell(getattr(latest_metric, "observed_at", None) or getattr(latest_load, "created_at", None)),
                    "last_error": self._compact_reason(getattr(latest_metric, "agent_error", None) or getattr(latest_metric, "xui_error", None)),
                }
            )

        user_rows = []
        total_client_traffic_30d = 0
        for sub in subscriptions:
            history = subscription_history.get(int(sub.id), [])
            all_time_values = [int(item.all_time_bytes or 0) for item in history]
            usage_delta = self._delta(all_time_values)
            total_client_traffic_30d += usage_delta
            latest_sub_sample = history[-1] if history else None
            user = sub.user
            user_label = str(getattr(user, "first_name", "") or getattr(user, "username", "") or f"User #{user.id}")
            node_name = (
                getattr(getattr(sub, "current_node", None), "name", None)
                or getattr(getattr(sub, "assigned_node", None), "name", None)
                or "-"
            )
            user_rows.append(
                {
                    "user": user_label,
                    "telegram_id": getattr(user, "telegram_id", ""),
                    "subscription": sub.display_name,
                    "subscription_id": int(sub.id),
                    "node": node_name,
                    "alias": sub.alias_fqdn or "-",
                    "traffic_30d": format_bytes(usage_delta),
                    "traffic_value": usage_delta,
                    "last_online": format_cell(getattr(latest_sub_sample, "last_online_at", None)) or "-",
                    "enabled": status_badge("enabled", "success") if getattr(latest_sub_sample, "enabled", None) else status_badge("unknown", "secondary"),
                    "latest_total": format_bytes(getattr(latest_sub_sample, "all_time_bytes", None)),
                }
            )

        user_rows.sort(key=lambda item: int(item["traffic_value"]), reverse=True)

        event_rows = [
            {
                "time": format_cell(event.created_at),
                "subscription": f"{event.subscription.display_name} #{event.subscription_id}",
                "event": event.event_kind,
                "from": getattr(event.from_node, "name", None) or "-",
                "to": getattr(event.to_node, "name", None) or "-",
                "reason": self._compact_reason(event.reason),
                "dns": event.dns_change_id or "-",
            }
            for event in safe_list(
                lambda: VPNSubscriptionEvent.objects.select_related("subscription", "from_node", "to_node")
                .order_by("-created_at")[:80]
            )
        ]
        if not event_rows:
            event_rows = [
                {
                    "time": format_cell(decision.created_at),
                    "subscription": f"{decision.subscription.display_name} #{decision.subscription_id}",
                    "event": decision.decision_kind,
                    "from": getattr(decision.from_node, "name", None) or "-",
                    "to": getattr(decision.to_node, "name", None) or "-",
                    "reason": self._compact_reason(decision.reason),
                    "dns": decision.dns_change_id or "-",
                }
                for decision in safe_list(
                    lambda: VPNRebalanceDecision.objects.select_related("subscription", "from_node", "to_node")
                    .order_by("-created_at")[:80]
                )
            ]

        log_rows = []
        for row in rows:
            if row["last_error"] != "-":
                log_rows.append({"source": row["node"].name, "kind": "metrics", "message": row["last_error"], "time": row["latest_snapshot_at"]})
        log_rows.extend(
            {
                "source": client.node.name,
                "kind": "sync",
                "message": client.last_error or "sync error",
                "time": format_cell(client.updated_at),
            }
            for client in safe_list(
                lambda: VPNNodeClient.objects.select_related("node")
                .exclude(Q(last_error__isnull=True) | Q(last_error=""))
                .order_by("-updated_at")[:40]
            )
        )

        projection_base = total_client_traffic_30d or fleet_traffic_30d
        projected_daily = projection_base / 30.0 if projection_base > 0 else 0.0
        projection_rows = [
            {"window": "30 days", "traffic": format_bytes(projected_daily * 30), "clients": total_active_assignments},
            {"window": "60 days", "traffic": format_bytes(projected_daily * 60), "clients": total_active_assignments},
            {"window": "90 days", "traffic": format_bytes(projected_daily * 90), "clients": total_active_assignments},
        ]

        chart_payload = {
            "nodes": [row["node"].name for row in rows],
            "cpu": [row["cpu_value"] for row in rows],
            "memory": [row["memory_value"] for row in rows],
            "disk": [row["disk_value"] for row in rows],
            "assigned": [row["assigned_now"] for row in rows],
            "traffic": [int(row["traffic_value"]) if "traffic_value" in row else 0 for row in rows],
            "users": [item["user"][:18] for item in user_rows[:10]],
            "userTraffic": [item["traffic_value"] for item in user_rows[:10]],
            "projections": {
                "labels": [item["window"] for item in projection_rows],
                "traffic": [projected_daily * days for days in (30, 60, 90)],
            },
            "nodeSeries": {
                row["node"].name: [
                    {
                        "t": format_cell(sample.observed_at),
                        "cpu": float(sample.cpu_percent or 0),
                        "memory": float(self._pct(sample.memory_used_bytes, sample.memory_total_bytes) or 0),
                        "disk": float(self._pct(sample.disk_used_bytes, sample.disk_total_bytes) or 0),
                    }
                    for sample in metric_history.get(int(row["node"].id), [])[-48:]
                ]
                for row in rows
            },
        }

        ctx["summary_cards"] = [
            {"label": "Nodes", "value": len(nodes), "hint": f"{healthy_nodes} healthy"},
            {"label": "Eligible for LB", "value": eligible_nodes, "hint": "healthy, compatible, backfilled"},
            {"label": "Active subs", "value": total_active_assignments, "hint": "currently assigned"},
            {"label": "Online clients", "value": online_clients, "hint": "from 3x-ui health"},
            {"label": "30d traffic", "value": format_bytes(total_client_traffic_30d or fleet_traffic_30d), "hint": "client counters preferred"},
            {"label": "Metric errors", "value": failed_metric_samples + len(log_rows), "hint": "last 30 days plus sync"},
        ]
        ctx["rows"] = rows
        ctx["user_rows"] = user_rows[:120]
        ctx["event_rows"] = event_rows
        ctx["log_rows"] = log_rows[:80]
        ctx["projection_rows"] = projection_rows
        ctx["chart_payload"] = chart_payload
        ctx["window_label"] = f"since {format_cell(since_30d)}"
        ctx["telemetry_notes"] = [
            "Server CPU/RAM/disk/network comes from the lightweight node agent when enabled; 3x-ui is used for VPN/client counters.",
            "Projection uses 30-day client traffic deltas when available, then falls back to node network deltas.",
            "Movement history is append-only from rebalance/failover decisions and subscription events.",
        ]
        return self.add_wordpress_context(ctx)


class VPNNodeCreateView(LegacyContentMutationGuardMixin, StaffRequiredMixin, CreateView):
    model = VPNNode
    form_class = BackofficeVPNNodeForm
    template_name = "backoffice/form.html"
    title_create = "Новая VPN нода"

    def get_success_url(self):
        return reverse("backoffice:vpn_node_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = self.title_create
        ctx["block_editor_asset_version"] = BLOCK_EDITOR_ASSET_VERSION
        return self.add_wordpress_context(ctx)

    def form_valid(self, form):
        now = timezone.now()
        form.instance.created_at = now
        form.instance.updated_at = now
        response = super().form_valid(form)
        messages.success(self.request, "Сохранено")
        render_error = _render_local_haproxy_runtime()
        if render_error:
            messages.warning(
                self.request,
                f"Нода сохранена, но runtime HAProxy config не обновлён автоматически: {render_error}",
            )
        return response


class VPNNodeUpdateView(LegacyContentMutationGuardMixin, StaffRequiredMixin, UpdateView):
    model = VPNNode
    form_class = BackofficeVPNNodeForm
    template_name = "backoffice/form.html"
    title_update = "Редактирование VPN ноды"

    def get_success_url(self):
        return reverse("backoffice:vpn_node_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = self.title_update
        ctx["block_editor_asset_version"] = BLOCK_EDITOR_ASSET_VERSION
        return self.add_wordpress_context(ctx)

    def form_valid(self, form):
        form.instance.updated_at = timezone.now()
        response = super().form_valid(form)
        messages.success(self.request, "Сохранено")
        render_error = _render_local_haproxy_runtime()
        if render_error:
            messages.warning(
                self.request,
                f"Нода сохранена, но runtime HAProxy config не обновлён автоматически: {render_error}",
            )
        return response


class VPNNodeDeleteView(LegacyContentContextMixin, StaffRequiredMixin, DeleteView):
    model = VPNNode
    template_name = "backoffice/confirm_delete.html"
    success_url = reverse_lazy("backoffice:vpn_node_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        related_count = safe_count(VPNNodeClient.objects.filter(node_id=self.object.id))
        ctx["title"] = "Удаление VPN ноды"
        ctx["delete_blocked"] = False
        ctx["related_counts"] = {
            "subscriptions": "—",
            "active_subscriptions": "—",
            "orders": "—",
            "node_clients": related_count,
            "support_tickets": "—",
            "support_messages": "—",
            "linked_accounts": "—",
        }
        if bool(getattr(self.object, "lb_enabled", False)):
            ctx["delete_warning"] = (
                "Нода сейчас включена в load balancer. Перед удалением лучше сначала выключить lb_enabled, "
                "убедиться, что новые подключения больше не идут на неё, и только потом удалять запись."
            )
        else:
            ctx["delete_warning"] = (
                "Будут удалены запись ноды и связанные node sync записи. Сами подписки пользователей удалены не будут."
            )
        return self.add_wordpress_context(ctx)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object()
        with transaction.atomic():
            VPNNodeClient.objects.filter(node_id=self.object.id).delete()
            self.object.delete()
        messages.success(request, "VPN нода удалена")
        render_error = _render_local_haproxy_runtime()
        if render_error:
            messages.warning(
                request,
                f"Нода удалена, но runtime HAProxy config не обновлён автоматически: {render_error}",
            )
        return redirect(self.success_url)


class EdgeServerListView(BaseListView):
    model = EdgeServer
    title = "HAProxy edges"
    subtitle = "Публичные edge-серверы для connect.vxcloud.ru и будущего edge failover."
    readonly = False
    add_url_name = "backoffice:edge_server_create"
    edit_url_name = "backoffice:edge_server_update"
    delete_url_name = "backoffice:edge_server_delete"
    columns = [
        ("id", "ID"),
        ("name", "Edge"),
        ("endpoint", "Публичный endpoint"),
        ("health", "Health"),
        ("role", "Role"),
        ("admission", "Новые клиенты"),
        ("updated_at", "Обновлён"),
    ]
    search_fields = ["name", "public_host", "public_ip", "notes"]

    def get_queryset(self):
        return super().get_queryset().order_by("priority", "name", "id")

    def get_table_rows(self) -> list[dict[str, Any]]:
        rows = []
        for item in self.object_list:
            rows.append(
                {
                    "obj": item,
                    "cells": [
                        item.id,
                        item.name,
                        edge_endpoint(item),
                        edge_health_badge(item),
                        edge_role_badge(item),
                        edge_admission_badge(item),
                        format_cell(item.updated_at),
                    ],
                }
            )
        return rows


class EdgeServerCreateView(LegacyContentMutationGuardMixin, StaffRequiredMixin, CreateView):
    model = EdgeServer
    form_class = BackofficeEdgeServerForm
    template_name = "backoffice/form.html"
    title_create = "Новый HAProxy edge"

    def get_success_url(self):
        return reverse("backoffice:edge_server_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = self.title_create
        ctx["block_editor_asset_version"] = BLOCK_EDITOR_ASSET_VERSION
        return self.add_wordpress_context(ctx)

    def form_valid(self, form):
        now = timezone.now()
        form.instance.created_at = now
        form.instance.updated_at = now
        response = super().form_valid(form)
        _normalize_edge_primary_state(self.object)
        messages.success(self.request, "Edge сохранён")
        render_error = _render_local_haproxy_runtime()
        if render_error:
            messages.warning(
                self.request,
                f"Edge сохранён, но runtime HAProxy config не обновлён автоматически: {render_error}",
            )
        return response


class EdgeServerUpdateView(LegacyContentMutationGuardMixin, StaffRequiredMixin, UpdateView):
    model = EdgeServer
    form_class = BackofficeEdgeServerForm
    template_name = "backoffice/form.html"
    title_update = "Редактирование HAProxy edge"

    def get_success_url(self):
        return reverse("backoffice:edge_server_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = self.title_update
        ctx["block_editor_asset_version"] = BLOCK_EDITOR_ASSET_VERSION
        return self.add_wordpress_context(ctx)

    def form_valid(self, form):
        form.instance.updated_at = timezone.now()
        response = super().form_valid(form)
        _normalize_edge_primary_state(self.object)
        messages.success(self.request, "Edge сохранён")
        render_error = _render_local_haproxy_runtime()
        if render_error:
            messages.warning(
                self.request,
                f"Edge сохранён, но runtime HAProxy config не обновлён автоматически: {render_error}",
            )
        return response


class EdgeServerDeleteView(LegacyContentContextMixin, StaffRequiredMixin, DeleteView):
    model = EdgeServer
    template_name = "backoffice/confirm_delete.html"
    success_url = reverse_lazy("backoffice:edge_server_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Удаление HAProxy edge"
        ctx["object_label"] = edge_endpoint(self.object)
        ctx["delete_blocked"] = False
        ctx["related_counts"] = None
        if bool(getattr(self.object, "is_primary", False)):
            ctx["delete_warning"] = (
                "Edge сейчас помечен как primary. После удаления нужно проверить, что в inventory остался другой готовый edge, "
                "и при необходимости сделать DNS cutover на него."
            )
        else:
            ctx["delete_warning"] = (
                "Будет удалена только inventory-запись edge. Сам DNS, standby edge и backend nodes удалены не будут."
            )
        return self.add_wordpress_context(ctx)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object()
        was_primary = bool(getattr(self.object, "is_primary", False))
        deleted_id = int(self.object.id)
        self.object.delete()
        replacement = _promote_replacement_primary_on_delete(deleted_id) if was_primary else _normalize_edge_primary_state()
        if was_primary and replacement is not None:
            messages.success(request, f"HAProxy edge удалён. Новый primary edge: {replacement.name}")
        else:
            messages.success(request, "HAProxy edge удалён")
        render_error = _render_local_haproxy_runtime()
        if render_error:
            messages.warning(
                request,
                f"Edge удалён, но runtime HAProxy config не обновлён автоматически: {render_error}",
            )
        return redirect(self.success_url)


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

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        action = str(request.POST.get("action") or "").strip()
        if action not in {"manual_rebalance", "emergency_failover", "force_failover"}:
            messages.error(request, "Неизвестная операция.")
            return redirect("backoffice:system_overview")
        if not bool_env("VPN_CLUSTER_ENABLED", False):
            messages.error(request, "Cluster mode выключен. Включите VPN_CLUSTER_ENABLED=1 перед ручным rebalance.")
            return redirect("backoffice:system_overview")
        runtime_settings = _cluster_runtime_settings()
        if action in {"emergency_failover", "force_failover"}:
            try:
                source_node_id = int(request.POST.get("node_id") or 0)
            except (TypeError, ValueError):
                source_node_id = 0
            if source_node_id <= 0:
                messages.error(request, "Choose a source node for emergency failover.")
                return redirect("backoffice:system_overview")
            allow_healthy_source = action == "force_failover"
            try:
                result = _run_async_from_sync(
                    _run_emergency_failover(
                        runtime_settings,
                        source_node_id,
                        allow_healthy_source=allow_healthy_source,
                    )
                )
            except Exception as exc:
                LOGGER.exception("Emergency failover failed")
                messages.error(request, f"Emergency failover failed: {exc}")
                return redirect("backoffice:system_overview")
            if int(result.get("source_node_healthy", 0)):
                messages.warning(request, "Emergency failover skipped: source node is still healthy.")
            else:
                failover_label = "Force failover finished: " if allow_healthy_source else "Emergency failover finished: "
                messages.success(
                    request,
                    failover_label
                    +
                    f"processed={int(result.get('processed', 0))}, "
                    f"moved={int(result.get('moved', 0))}, "
                    f"skipped={int(result.get('skipped', 0))}, "
                    f"failed={int(result.get('failed', 0))}.",
                )
            return redirect("backoffice:system_overview")
        try:
            result = _run_async_from_sync(_run_manual_rebalance(runtime_settings))
        except Exception as exc:
            LOGGER.exception("Manual rebalance failed")
            messages.error(request, f"Manual rebalance failed: {exc}")
            return redirect("backoffice:system_overview")
        messages.success(
            request,
            "Manual rebalance started: "
            f"planned={int(result.get('planned', 0))}, "
            f"presynced={int(result.get('presynced', 0))}, "
            f"cutover={int(result.get('cutover', 0))}, "
            f"cleaned={int(result.get('cleaned', 0))}.",
        )
        return redirect("backoffice:system_overview")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        runtime_settings = _cluster_runtime_settings()
        edges = safe_list(lambda: EdgeServer.objects.order_by("priority", "id"))
        primary_edge = _current_primary_edge(edges)
        ctx["title"] = "Cluster, edges & HAProxy"
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
                "title": "DNS alias layer",
                "items": [
                    ("Namespace", runtime_settings.vpn_alias_namespace),
                    ("Provider", runtime_settings.vpn_alias_provider),
                    ("Default TTL", f"{runtime_settings.vpn_alias_default_ttl} sec"),
                    ("Cutover TTL", f"{runtime_settings.vpn_alias_cutover_ttl} sec"),
                    ("Overlap window", f"{runtime_settings.vpn_alias_overlap_minutes} min"),
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
                "title": "Rebalance policy",
                "items": [
                    ("Workflow tick", f"{runtime_settings.vpn_rebalance_workflow_tick_seconds} sec"),
                    ("Planning interval", f"{runtime_settings.vpn_rebalance_interval_seconds} sec"),
                    ("Max moves / node", runtime_settings.vpn_rebalance_max_moves_per_node),
                    ("Move fraction", f"{runtime_settings.vpn_rebalance_move_fraction:.0%}"),
                    ("Cooldown", f"{runtime_settings.vpn_rebalance_cooldown_hours} h"),
                    ("Min score gap", f"{runtime_settings.vpn_rebalance_min_score_gap:.2f}"),
                ],
            },
            {
                "title": "Edge inventory",
                "items": [
                    ("Primary edge", primary_edge.name if primary_edge else "—"),
                    ("Primary endpoint", edge_endpoint(primary_edge) if primary_edge else "—"),
                    ("Primary IP", primary_edge.public_ip if primary_edge else "—"),
                    ("Total edges", len(edges)),
                    ("Healthy active edges", sum(1 for edge in edges if edge.is_active and edge.last_health_ok is True)),
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
            "python scripts/ops/render_haproxy_cfg.py --env-file .env --output-path ops/haproxy/runtime/haproxy.cfg",
            "python web/manage.py check_haproxy_edges",
        ]
        ctx["notes"] = [
            "Из /ops изменение ноды теперь автоматически перерисовывает runtime haproxy.cfg для containerized HAProxy. Контейнер HAProxy сам подхватывает изменения файла.",
            "Edge inventory в /ops — это control plane для DNS/floating-IP cutover. Сам DNS всё равно переключается отдельно.",
            "Primary edge должен совпадать с тем endpoint, на который реально смотрит connect.vxcloud.ru. Если не совпадает — сначала правьте DNS/env, потом inventory.",
            "Если cluster mode выключен, таблицы нод и sync всё равно полезны как inventory и health audit.",
            "Перед включением lb_enabled на новой ноде: задайте public_ip, node_fqdn, compatibility_pool, откройте firewall для inbound/backend порта и дождитесь health=healthy.",
            "Автобаланс смотрит не на raw client count, а на 7-дневные active assignments, weekly traffic, peak/p95 concurrency, probe latency, health failures и recent move penalty.",
            "Alias-based DNS rollout делает user-facing host стабильным: subscription URL и alias host не меняются, меняется только A-record alias → node IP.",
            "Для production rollout сначала проверяйте planner preview ниже: pool mismatch, reality_missing и backfill_pending должны быть устранены до включения новой ноды в rebalance.",
            "HAProxy template рассчитан на long-lived TCP sessions. При первом node-add или edge-cutover всё равно делайте dry-run render и ручной тест новым конфигом.",
        ]

        nodes = safe_list(lambda: VPNNode.objects.order_by("name", "id"))
        node_assignment_counts = _active_assignment_counts([int(node.id) for node in nodes])
        pool_nodes, majority_signature = _eligible_lb_nodes(nodes)
        pool_ids = {int(node.id) for node in pool_nodes}
        ctx["edge_rows"] = [
            {
                "name": edge.name,
                "endpoint": edge_endpoint(edge),
                "public_ip": edge.public_ip,
                "health": edge_health_badge(edge),
                "role": edge_role_badge(edge),
                "admission": edge_admission_badge(edge),
                "priority": int(getattr(edge, "priority", 100) or 100),
                "last_health_at": format_cell(edge.last_health_at),
                "last_health_error": getattr(edge, "last_health_error", "") or "—",
                "notes": getattr(edge, "notes", "") or "—",
            }
            for edge in edges
        ]
        ctx["lb_rows"] = [
            {
                "id": node.id,
                "name": node.name,
                "backend": f"{node.backend_host}:{node.backend_port}",
                "health": health_badge(node),
                "lb": boolean_badge(bool(getattr(node, "lb_enabled", False)), "enabled", "disabled"),
                "backfill": sync_state_badge("needed" if getattr(node, "needs_backfill", False) else "ok"),
                "reason": status_badge(
                    _node_lb_reason(node, pool_ids),
                    "success" if int(node.id) in pool_ids else ("warning" if getattr(node, "last_health_ok", None) is None else "secondary"),
                ),
                "updated_at": format_cell(node.updated_at),
            }
            for node in nodes
        ]
        ctx["haproxy_backend_preview"] = _haproxy_backend_preview(pool_nodes)
        if majority_signature and any(majority_signature):
            ctx["majority_reality"] = {
                "public_key": majority_signature[0][:24] + ("..." if len(majority_signature[0]) > 24 else ""),
                "short_id": majority_signature[1] or "—",
                "sni": majority_signature[2] or "—",
                "fingerprint": majority_signature[3] or "—",
            }
        else:
            ctx["majority_reality"] = None

        sync_errors = safe_get(
            lambda: VPNNodeClient.objects.select_related("node", "subscription")
            .exclude(last_error__isnull=True)
            .exclude(last_error="")
            .order_by("-updated_at", "-id")[:10],
            [],
        )
        ctx["sync_error_rows"] = [
            {
                "node": item.node.name if item.node_id else "—",
                "subscription": item.subscription_id,
                "client": item.client_email or "—",
                "state": sync_state_badge(item.sync_state),
                "error": str(item.last_error or "").strip(),
                "updated_at": format_cell(item.updated_at),
            }
            for item in sync_errors
        ]

        ctx["health_rows"] = [
            {
                "name": node.name,
                "id": int(node.id),
                "assigned": int(node_assignment_counts.get(int(node.id), 0)),
                "can_emergency_failover": bool(getattr(node, "last_health_ok", None) is False)
                and int(node_assignment_counts.get(int(node.id), 0)) > 0,
                "can_force_failover": bool(getattr(node, "last_health_ok", None) is not False)
                and int(node_assignment_counts.get(int(node.id), 0)) > 0,
                "health": health_badge(node),
                "last_health_at": format_cell(node.last_health_at),
                "last_health_error": getattr(node, "last_health_error", "") or "—",
                "public_key": (str(getattr(node, "last_reality_public_key", "") or "")[:24] + "...")
                if getattr(node, "last_reality_public_key", None)
                else "—",
                "short_id": getattr(node, "last_reality_short_id", None) or "—",
                "sni": getattr(node, "last_reality_sni", None) or "—",
                "fingerprint": getattr(node, "last_reality_fingerprint", None) or "—",
            }
            for node in nodes
        ]
        ctx["primary_edge"] = {
            "name": primary_edge.name,
            "endpoint": edge_endpoint(primary_edge),
            "public_ip": primary_edge.public_ip,
            "accepting": edge_admission_badge(primary_edge),
            "health": edge_health_badge(primary_edge),
            "priority": int(getattr(primary_edge, "priority", 100) or 100),
        } if primary_edge else None
        try:
            rebalance_preview = _run_async_from_sync(_build_rebalance_preview(runtime_settings))
        except Exception as exc:
            LOGGER.exception("Failed to build rebalance preview")
            rebalance_preview = {
                "generated_at": None,
                "nodes": [],
                "moves": [],
                "summary": {"eligible_nodes": 0, "planned_moves": 0, "compatible_pools": 0},
                "error": str(exc),
            }
        ctx["rebalance_preview_error"] = rebalance_preview.get("error", "")
        summary = dict(rebalance_preview.get("summary") or {})
        ctx["rebalance_preview_summary"] = {
            "generated_at": format_cell(rebalance_preview.get("generated_at")) if rebalance_preview.get("generated_at") else "—",
            "eligible_nodes": int(summary.get("eligible_nodes") or 0),
            "planned_moves": int(summary.get("planned_moves") or 0),
            "compatible_pools": int(summary.get("compatible_pools") or 0),
        }
        ctx["rebalance_node_rows"] = [
            {
                "name": row.get("name") or f"node-{int(row.get('id') or 0)}",
                "pool": row.get("pool") or "default",
                "score": "—" if row.get("score") is None else f"{float(row['score']):.2f}",
                "eligible": status_badge("eligible", "success") if row.get("eligible") else status_badge(str(row.get("issue") or "blocked"), "secondary"),
                "assigned": int(row.get("active_assigned_subscriptions") or 0),
                "observed": int(row.get("observed_enabled_clients") or 0),
                "weekly_traffic_gb": f"{(int(row.get('weekly_traffic_bytes') or 0) / (1024 ** 3)):.2f}",
                "peak_concurrency": int(row.get("peak_concurrency") or 0),
                "probe_latency_ms": "—" if row.get("p95_probe_latency_ms") is None else f"{float(row.get('p95_probe_latency_ms') or 0):.0f}",
                "capacity": f"{int(row.get('bandwidth_capacity_mbps') or 0)} Mbps / {int(row.get('connection_capacity') or 0)} conn",
                "reasons": ", ".join(f"{key}={float(value):.2f}" for key, value in sorted((row.get('reasons') or {}).items())),
            }
            for row in rebalance_preview.get("nodes", [])
        ]
        ctx["rebalance_move_rows"] = [
            {
                "subscription_id": int(row.get("subscription_id") or 0),
                "display_name": row.get("display_name") or f"sub-{int(row.get('subscription_id') or 0)}",
                "alias_fqdn": row.get("alias_fqdn") or "—",
                "from_node_id": int(row.get("from_node_id") or 0),
                "to_node_id": int(row.get("to_node_id") or 0),
                "pool": row.get("compatibility_pool") or "default",
                "score_gap": f"{float(row.get('score_gap') or 0):.2f}",
                "from_score": f"{float(row.get('from_score') or 0):.2f}",
                "to_score": f"{float(row.get('to_score') or 0):.2f}",
            }
            for row in rebalance_preview.get("moves", [])
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
