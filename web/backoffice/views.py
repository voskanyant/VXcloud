from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import timedelta, timezone as dt_timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.db import transaction
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
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.xui_client import XUIClient

from .forms import (
    BackofficeCategoryForm,
    BackofficePageForm,
    BackofficeSubscriptionExpiryForm,
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


async def _push_subscription_expiry_to_xui(subscription: BotSubscription, expires_at) -> list[str]:
    desired_enabled = bool(
        getattr(subscription, "is_active", False)
        and expires_at > timezone.now()
        and getattr(subscription, "revoked_at", None) is None
    )
    limit_ip = int_env("MAX_DEVICES_PER_SUB", 1)
    flow = env_value("VPN_FLOW", "xtls-rprx-vision")
    errors: list[str] = []

    async def apply_on_node(base_url: str, username: str, password: str, inbound_id: int, label: str) -> None:
        xui = XUIClient(base_url.rstrip("/"), username, password)
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
            )
        except Exception as exc:
            errors.append(f"{label}: {exc}")
        finally:
            await xui.close()

    if bool_env("VPN_CLUSTER_ENABLED", False):
        nodes = list(VPNNode.objects.filter(is_active=True).order_by("id"))
        for node in nodes:
            await apply_on_node(
                str(node.xui_base_url),
                str(node.xui_username),
                str(node.xui_password),
                int(node.xui_inbound_id),
                f"node#{int(node.id)}",
            )
        return errors

    await apply_on_node(
        env_value("XUI_BASE_URL"),
        env_value("XUI_USERNAME"),
        env_value("XUI_PASSWORD"),
        int_env("XUI_INBOUND_ID", int(getattr(subscription, "inbound_id", 1) or 1)),
        "primary",
    )
    return errors


async def _delete_subscription_from_xui(subscription: BotSubscription) -> list[str]:
    limit_ip = int_env("MAX_DEVICES_PER_SUB", 1)
    flow = env_value("VPN_FLOW", "xtls-rprx-vision")
    errors: list[str] = []

    async def apply_on_node(base_url: str, username: str, password: str, inbound_id: int, label: str) -> None:
        if not (base_url and username and password):
            errors.append(f"{label}: x-ui credentials are not configured")
            return

        xui = XUIClient(base_url.rstrip("/"), username, password)
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
            errors.append(f"{label}: {exc}")
        finally:
            await xui.close()

    if bool_env("VPN_CLUSTER_ENABLED", False):
        nodes = list(VPNNode.objects.filter(is_active=True).order_by("id"))
        for node in nodes:
            await apply_on_node(
                str(node.xui_base_url),
                str(node.xui_username),
                str(node.xui_password),
                int(node.xui_inbound_id),
                f"node#{int(node.id)}",
            )
        return errors

    await apply_on_node(
        env_value("XUI_BASE_URL"),
        env_value("XUI_USERNAME"),
        env_value("XUI_PASSWORD"),
        int_env("XUI_INBOUND_ID", int(getattr(subscription, "inbound_id", 1) or 1)),
        "primary",
    )
    return errors


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
        cms_base_url = str(getattr(settings, "CMS_BASE_URL", "") or "").strip()
        cms_token = str(getattr(settings, "CMS_TOKEN", "") or "").strip()
        ctx["directus_enabled"] = bool(cms_base_url and cms_token)
        ctx["notes"] = [
            "Пустое поле удаляет override и возвращает штатный текст или кнопку из кода.",
            "Изменения подхватываются ботом автоматически примерно в течение минуты.",
            "DB overrides из /ops/ имеют приоритет над legacy Directus.",
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
    readonly = False
    delete_url_name = "backoffice:bot_user_delete"
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
        subscriptions_qs = BotSubscription.objects.filter(user_id=self.object.id)
        subscriptions = list(subscriptions_qs)
        subscription_ids = list(subscriptions_qs.values_list("id", flat=True))
        xui_errors: list[str] = []
        for subscription in subscriptions:
            xui_errors.extend(asyncio.run(_delete_subscription_from_xui(subscription)))
        if xui_errors:
            messages.error(
                request,
                "Не удалось удалить клиента в 3x-ui. Пользователь не удалён: " + "; ".join(xui_errors[:3]),
            )
            return self.render_to_response(self.get_context_data())

        with transaction.atomic():
            LinkedAccount.objects.filter(telegram_id=telegram_id).delete()
            SupportMessage.objects.filter(sender_user_id=self.object.id).update(sender_user_id=None)
            SupportTicket.objects.filter(user_id=self.object.id).update(user_id=None)
            if subscription_ids:
                VPNNodeClient.objects.filter(subscription_id__in=subscription_ids).delete()
            BotOrder.objects.filter(user_id=self.object.id).delete()
            subscriptions_qs.delete()
            self.object.delete()

        messages.success(request, "Пользователь удалён")
        return redirect(self.success_url)


class BotSubscriptionListView(BaseListView):
    model = BotSubscription
    title = "Подписки"
    subtitle = "Текущие устройства, сроки и импортные конфиги."
    readonly = False
    edit_url_name = "backoffice:bot_subscription_expiry_update"
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
            _, status_label, status_tone = subscription_status_state(item)
            rows.append(
                {
                    "obj": item,
                    "cells": [
                        item.id,
                        item.user_id,
                        item.display_name,
                        item.client_email,
                        status_badge(status_label, status_tone),
                        format_cell(item.expires_at),
                        format_cell(item.updated_at),
                    ],
                }
            )
        return rows


class BotSubscriptionExpiryUpdateView(StaffRequiredMixin, TemplateView):
    template_name = "backoffice/form.html"

    def _subscription(self) -> BotSubscription:
        return get_object_or_404(BotSubscription.objects.select_related("user"), pk=self.kwargs["pk"])

    def _initial(self, subscription: BotSubscription) -> dict[str, Any]:
        current = getattr(subscription, "expires_at", None) or timezone.now()
        return {"expires_at": timezone.localtime(current).strftime("%Y-%m-%dT%H:%M")}

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        subscription = self._subscription()
        form = kwargs.get("form") or BackofficeSubscriptionExpiryForm(initial=self._initial(subscription))
        title_name = subscription.display_name or subscription.client_email or f"#{subscription.id}"
        ctx["title"] = f"Изменить срок: {title_name}"
        ctx["form"] = form
        return ctx

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        subscription = self._subscription()
        form = BackofficeSubscriptionExpiryForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        expires_at = form.cleaned_data["expires_at"]
        if timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone())
        expires_at = expires_at.astimezone(dt_timezone.utc)
        should_be_active = bool(expires_at > timezone.now() and getattr(subscription, "revoked_at", None) is None)

        with transaction.atomic():
            subscription.expires_at = expires_at
            subscription.is_active = should_be_active
            subscription.updated_at = timezone.now()
            subscription.save(update_fields=["expires_at", "is_active", "updated_at"])

        errors = asyncio.run(_push_subscription_expiry_to_xui(subscription, expires_at))
        if errors:
            messages.warning(request, "Срок обновлён в базе, но не везде применился в 3x-ui: " + "; ".join(errors[:3]))
        else:
            messages.success(request, "Срок подписки обновлён в базе и 3x-ui.")
        return redirect("backoffice:bot_subscription_list")


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
