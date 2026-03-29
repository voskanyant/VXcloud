from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import qrcode
from PIL import Image
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, LabeledPrice, Message, ReplyKeyboardMarkup, Update, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from .config import Settings
from .cms import DirectusCMS
from .db import DB
from .domain.subscriptions import activate_subscription
from .vless import build_vless_url
from .xui_client import XUIClient


LOGGER = logging.getLogger(__name__)
STREISAND_APPSTORE_URL = "https://apps.apple.com/us/app/streisand/id6450534064"
V2BOX_PLAYSTORE_URL = "https://play.google.com/store/search?q=V2Box&c=apps"
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
EMAIL_RE = re.compile(r"(?:email|user)[:=]\s*([^\s,\]]+)", re.IGNORECASE)
BRACKET_RE = re.compile(r"\[([^\[\]\s]+)\]")


def _log_payment_event(
    *,
    order_id: int,
    client_code: str | None,
    provider: str,
    event_id: str | None,
    provision_state: str,
) -> None:
    LOGGER.info(
        json.dumps(
            {
                "event": "payment_flow",
                "order_id": order_id,
                "client_code": client_code or "",
                "provider": provider,
                "event_id": event_id or "",
                "provision_state": provision_state,
            },
            ensure_ascii=False,
        )
    )


class VPNBot:
    def __init__(
        self,
        app: Application,
        settings: Settings,
        db: DB,
        xui: XUIClient,
        cms: DirectusCMS | None = None,
    ) -> None:
        self.app = app
        self.settings = settings
        self.db = db
        self.xui = xui
        self.cms = cms
        self._pending_profiles: dict[str, dict[str, str]] = {}
        self._copy_links: dict[str, str] = {}
        self._cms_content: dict[str, str] = {}
        self._cms_buttons: dict[str, str] = {}
        self._cms_loaded_at: float = 0.0
        self._cms_lock = asyncio.Lock()
        self._provision_locks: dict[int, asyncio.Lock] = {}
        self._provision_locks_guard = asyncio.Lock()
        self._xray_log_offset: int = 0
        self._recent_email_ips: dict[str, dict[str, float]] = {}
        self._single_ip_block_until: dict[str, float] = {}
        self._single_ip_notified_blocked: set[str] = set()

    def register(self) -> None:
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("menu", self.start))
        self.app.add_handler(CommandHandler("buy", self.buy))
        self.app.add_handler(CommandHandler("mysub", self.mysub))
        self.app.add_handler(CommandHandler("myvpn", self.myvpn))
        self.app.add_handler(CommandHandler("renew", self.renew))
        self.app.add_handler(CommandHandler("reply", self.reply_support))
        self.app.add_handler(CommandHandler("tickets", self.admin_tickets))
        self.app.add_handler(CommandHandler("ticket", self.admin_ticket))
        self.app.add_handler(CommandHandler("reply_ticket", self.admin_reply_ticket))
        self.app.add_handler(CommandHandler("close", self.admin_close_ticket))
        self.app.add_handler(CommandHandler("admin_reload", self.admin_reload))
        self.app.add_handler(PreCheckoutQueryHandler(self.precheckout))
        self.app.add_handler(CallbackQueryHandler(self.inline_callback))
        self.app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, self.successful_payment))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.menu_click))

    def _menu_keyboard(self, has_active_subscription: bool = False) -> ReplyKeyboardMarkup:
        buttons = self._menu_buttons(has_active_subscription=has_active_subscription)
        rows: list[list[KeyboardButton]] = []
        row: list[KeyboardButton] = []
        for key, label in buttons:
            if key == "menu_site":
                row.append(KeyboardButton(label, web_app=WebAppInfo(url=self._site_url())))
            else:
                row.append(KeyboardButton(label))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        return ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)

    def _content_text(self, key: str, default: str) -> str:
        value = self._cms_content.get(key)
        return value if value else default

    def _button_label(self, key: str, default: str) -> str:
        value = self._cms_buttons.get(key)
        return value if value else default

    async def _has_active_subscription(self, user_id: int) -> bool:
        return await self.db.get_active_subscription(user_id) is not None

    async def _menu_keyboard_for_user(self, user_id: int) -> ReplyKeyboardMarkup:
        return self._menu_keyboard(has_active_subscription=await self._has_active_subscription(user_id))

    def _display_tz(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.settings.timezone)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")

    def _format_local_dt(self, dt: datetime) -> str:
        return dt.astimezone(self._display_tz()).strftime("%d/%m/%Y %H:%M")

    @staticmethod
    def _format_payment_method(method: str | None) -> str:
        if not method:
            return "не указан"
        normalized = method.strip().lower()
        if normalized == "card":
            return "карта"
        if normalized == "stars":
            return "telegram stars"
        return normalized

    def _menu_buttons(self, has_active_subscription: bool = False) -> list[tuple[str, str]]:
        buttons: list[tuple[str, str]] = [
            ("menu_trial", self._button_label("menu_trial", "\U0001f381 \u0411\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e 7\u0434").strip() or "\U0001f381 \u0411\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e 7\u0434"),
            ("menu_buy", self._button_label("menu_buy", "\U0001f4b3 \u041a\u0443\u043f\u0438\u0442\u044c \u043d\u043e\u0432\u044b\u0439 \u043a\u043e\u043d\u0444\u0438\u0433").strip() or "\U0001f4b3 \u041a\u0443\u043f\u0438\u0442\u044c \u043d\u043e\u0432\u044b\u0439 \u043a\u043e\u043d\u0444\u0438\u0433"),
            ("menu_mysub", self._button_label("menu_mysub", "\U0001f4ca \u041c\u043e\u044f \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0430").strip() or "\U0001f4ca \u041c\u043e\u044f \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0430"),
            (
                "menu_instructions",
                self._button_label("menu_instructions", "\U0001f4ac \u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f").strip() or "\U0001f4ac \u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f",
            ),
            (
                "menu_support",
                self._button_label("menu_support", "\U0001f198 \u041f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430").strip() or "\U0001f198 \u041f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430",
            ),
            (
                "menu_site",
                self._button_label("menu_site", "\U0001f310 VXcloud.ru").strip() or "\U0001f310 VXcloud.ru",
            ),
        ]
        if has_active_subscription:
            buttons.insert(2, ("menu_renew", self._button_label("menu_renew", "\U0001f504 \u041f\u0440\u043e\u0434\u043b\u0438\u0442\u044c \u0442\u0435\u043a\u0443\u0449\u0438\u0439").strip() or "\U0001f504 \u041f\u0440\u043e\u0434\u043b\u0438\u0442\u044c \u0442\u0435\u043a\u0443\u0449\u0438\u0439"))
        return buttons

    def _site_url(self) -> str:
        return self._content_text("site_url", "https://vxcloud.ru").strip() or "https://vxcloud.ru"

    async def _account_url(self, user_id: int | None) -> str:
        explicit = self._content_text("account_page_url", "").strip()
        if explicit:
            return explicit
        site_url = self._site_url().rstrip("/")
        fallback = f"{site_url}/account/"
        if user_id is None:
            return fallback

        shared_secret = (self.settings.magic_link_shared_secret or "").strip()
        if not shared_secret:
            return fallback

        endpoint = f"{site_url}/api/auth/magic-link"
        telegram_user_id = await self.db.get_user_telegram_id(user_id)
        try:
            magic_url = await asyncio.to_thread(
                self._request_magic_link_url,
                endpoint,
                shared_secret,
                telegram_user_id,
                user_id,
                self.settings.magic_link_api_timeout_seconds,
            )
            return magic_url or fallback
        except Exception:
            LOGGER.exception("Failed to generate magic link for user_id=%s", user_id)
            return fallback

    @staticmethod
    def _request_magic_link_url(
        endpoint: str,
        shared_secret: str,
        telegram_user_id: int | None,
        bot_user_id: int,
        timeout_seconds: int,
    ) -> str | None:
        payload_obj: dict[str, int] = {"bot_user_id": bot_user_id}
        if telegram_user_id is not None:
            payload_obj["telegram_id"] = telegram_user_id
        payload = json.dumps(payload_obj).encode("utf-8")
        req = Request(
            endpoint,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Shared-Secret": shared_secret,
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=max(1, timeout_seconds)) as resp:
                body = resp.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError):
            return None

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return None
        url = parsed.get("url")
        if isinstance(url, str) and url.strip():
            return url.strip()
        return None

    def _open_app_url(self, config_url: str) -> str:
        return f"{self._site_url().rstrip('/')}/open-app/?u={quote(config_url, safe='')}"

    def _node_response_text(self, node_key: str) -> str:
        response_key = f"{node_key}_response"
        legacy_key = f"{node_key.removeprefix('menu_')}_response"
        if node_key == "menu_instructions":
            default = (
                "Короткая инструкция:\n"
                "1) Установите приложение\n"
                "2) Нажмите «Моя подписка» и скопируйте ссылку\n"
                "3) Импортируйте ссылку в приложение\n\n"
                "Выберите платформу кнопками ниже."
            )
            return self._content_text(response_key, self._content_text(legacy_key, default))
        return self._content_text(
            response_key,
            self._content_text(
                legacy_key,
                self._content_text("menu_unknown_message", "\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 \u043a\u043d\u043e\u043f\u043a\u0438 \u043c\u0435\u043d\u044e."),
            ),
        )

    def _node_inline_keyboard(self, node_key: str, parent_key: str | None = None) -> InlineKeyboardMarkup | None:
        raw = self._cms_content.get(f"{node_key}_buttons")
        if not raw:
            if node_key == "menu_instructions":
                return InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton(text="🍏 iOS (Streisand)", url=STREISAND_APPSTORE_URL)],
                        [InlineKeyboardButton(text="🤖 Android (V2Box)", url=V2BOX_PLAYSTORE_URL)],
                        [InlineKeyboardButton(text="💻 Сайт VXcloud", url=f"{self._site_url().rstrip('/')}")],
                    ]
                )
            return None

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            LOGGER.warning("Invalid JSON in content key '%s_buttons'", node_key)
            return None

        rows: list[list[InlineKeyboardButton]] = []
        if isinstance(parsed, list):
            if parsed and all(isinstance(r, list) for r in parsed):
                source_rows = parsed
            else:
                source_rows = [parsed]
            for row in source_rows:
                if not isinstance(row, list):
                    continue
                row_buttons: list[InlineKeyboardButton] = []
                for item in row:
                    if not isinstance(item, dict):
                        continue
                    text = str(item.get("text", "")).strip()
                    if not text:
                        continue
                    url = item.get("url")
                    submenu = item.get("submenu")
                    response = item.get("response")
                    if isinstance(url, str) and url.strip():
                        row_buttons.append(InlineKeyboardButton(text=text, url=url.strip()))
                    elif isinstance(submenu, str) and submenu.strip():
                        submenu_key = submenu.strip()
                        row_buttons.append(
                            InlineKeyboardButton(
                                text=text,
                                callback_data=f"nav|{submenu_key}|{node_key}",
                            )
                        )
                    elif isinstance(response, str) and response.strip():
                        response_key = response.strip()
                        row_buttons.append(
                            InlineKeyboardButton(
                                text=text,
                                callback_data=f"msg|{response_key}|{node_key}",
                            )
                        )
                    else:
                        action = item.get("action")
                        if isinstance(action, str) and action.strip():
                            action_key = action.strip()
                            row_buttons.append(
                                InlineKeyboardButton(
                                    text=text,
                                    callback_data=f"act|{action_key}|{node_key}",
                                )
                            )
                if row_buttons:
                    rows.append(row_buttons)

        if parent_key:
            rows.append([InlineKeyboardButton(text="â¬…ï¸ Back", callback_data=f"nav|{parent_key}|_")])

        if not rows:
            return None
        return InlineKeyboardMarkup(rows)

    def _start_inline_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text="🎁 Попробовать 7 дней", callback_data="act|start_trial|_"),
                    InlineKeyboardButton(text="💳 Купить доступ", callback_data="act|buy_new|_"),
                ],
                [
                    InlineKeyboardButton(text="💬 Как подключить", callback_data="nav|menu_instructions|_"),
                    InlineKeyboardButton(text="🌐 Открыть сайт", url=self._site_url().rstrip("/")),
                ],
            ]
        )

    @staticmethod
    def _start_message_text() -> str:
        return (
            "Добро пожаловать в VXcloud\n\n"
            "Здесь вы можете получить стабильный доступ к интернету для работы, общения и повседневных задач.\n\n"
            "Начните с пробного периода или сразу оформите доступ.\n\n"
            "Для подключения понадобится специальное приложение.\n"
            "Если его нет в российском App Store, может потребоваться сменить регион в App Store.\n"
            "Мы покажем всё по шагам."
        )

    async def _send_start_screen(self, message: Message, user_id: int) -> None:
        menu_keyboard = await self._menu_keyboard_for_user(user_id)
        sent = await message.reply_text(self._start_message_text(), reply_markup=menu_keyboard)
        try:
            await sent.edit_reply_markup(reply_markup=self._start_inline_keyboard())
        except Exception:
            await message.reply_text("Выберите действие:", reply_markup=self._start_inline_keyboard())

    def _trial_offer_markup(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text="🎁 Активировать 7 дней", callback_data="act|trial_activate|_")],
                [
                    InlineKeyboardButton(text="💬 Как это работает", callback_data="nav|menu_instructions|_"),
                    InlineKeyboardButton(text="🔙 Назад", callback_data="act|start_back|_"),
                ],
            ]
        )

    def _trial_used_markup(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text="💳 Купить доступ", callback_data="act|buy_new|_")],
                [
                    InlineKeyboardButton(text="💬 Как подключить", callback_data="nav|menu_instructions|_"),
                    InlineKeyboardButton(text="🔙 Назад", callback_data="act|start_back|_"),
                ],
            ]
        )

    def _trial_success_markup(self, subscription_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text="📲 Открыть доступ", callback_data=f"act|cfg_open:{subscription_id}|_"),
                    InlineKeyboardButton(text="📷 Показать QR", callback_data=f"act|cfg_qr:{subscription_id}|_"),
                ],
                [
                    InlineKeyboardButton(text="💬 Инструкция", callback_data="nav|menu_instructions|_"),
                    InlineKeyboardButton(text="📦 Моя подписка", callback_data="act|start_mysub|_"),
                ],
            ]
        )

    async def _show_trial_offer(self, message: Message, user_id: int) -> None:
        if await self.db.has_any_subscription(user_id):
            await message.reply_text(
                "Пробный доступ уже был использован\n\n"
                "Вы можете сразу оформить платный доступ.",
                reply_markup=self._trial_used_markup(),
            )
            return

        await message.reply_text(
            "Пробный доступ на 7 дней\n\n"
            "Подойдёт, если вы хотите сначала всё проверить.\n\n"
            "Что вы получите:\n"
            "• доступ на 7 дней\n"
            "• ссылку для подключения\n"
            "• QR-код для быстрого входа\n"
            "• инструкцию по шагам\n\n"
            "Пробный доступ можно активировать один раз.",
            reply_markup=self._trial_offer_markup(),
        )

    async def _send_mysub_for_message(self, message: Message, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        subscriptions = await self.db.list_subscriptions(user_id)
        if not subscriptions:
            paid_order = await self.db.get_latest_paid_order(user_id)
            if paid_order:
                await message.reply_text(
                    self._content_text(
                        "recovering_subscription_message",
                        "ÐÐ°Ð¹Ð´ÐµÐ½ Ð¾Ð¿Ð»Ð°Ñ‡ÐµÐ½Ð½Ñ‹Ð¹ Ð·Ð°ÐºÐ°Ð·. ÐŸÑ€Ð¾Ð±ÑƒÑŽ Ð²Ð¾ÑÑÑ‚Ð°Ð½Ð¾Ð²Ð¸Ñ‚ÑŒ Ð¿Ð¾Ð´Ð¿Ð¸ÑÐºÑƒ...",
                    )
                )
                try:
                    await asyncio.wait_for(
                        self._run_user_provision(
                            user_id,
                            lambda: self._activate_order_and_send_config(update=None, order_id=int(paid_order["id"]), message=message),
                        ),
                        timeout=45,
                    )
                    return
                except Exception:
                    LOGGER.exception(
                        "Failed to recover subscription for user_id=%s from paid order_id=%s",
                        user_id,
                        paid_order.get("id"),
                    )
                    await message.reply_text(
                        self._content_text(
                            "recover_failed_message",
                            "ÐÐµ ÑƒÐ´Ð°Ð»Ð¾ÑÑŒ Ð°Ð²Ñ‚Ð¾Ð¼Ð°Ñ‚Ð¸Ñ‡ÐµÑÐºÐ¸ Ð²Ð¾ÑÑÑ‚Ð°Ð½Ð¾Ð²Ð¸Ñ‚ÑŒ Ð¿Ð¾Ð´Ð¿Ð¸ÑÐºÑƒ. ÐŸÐ¾Ð´Ð´ÐµÑ€Ð¶ÐºÐ° ÑƒÐ¶Ðµ ÑƒÐ²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð°, Ð¿Ð¾Ð¶Ð°Ð»ÑƒÐ¹ÑÑ‚Ð° Ð¿Ð¾Ð´Ð¾Ð¶Ð´Ð¸Ñ‚Ðµ.",
                        )
                    )
                    if self.settings.telegram_admin_id:
                        try:
                            await self.app.bot.send_message(
                                chat_id=self.settings.telegram_admin_id,
                                text=(
                                    "âš ï¸ ÐžÑˆÐ¸Ð±ÐºÐ° Ð²Ð¾ÑÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ñ Ð¿Ð¾Ð´Ð¿Ð¸ÑÐºÐ¸.\n"
                                    f"user_id={user_id} paid_order_id={paid_order.get('id')}"
                                ),
                            )
                        except Exception:
                            LOGGER.exception("Failed to notify admin about recovery issue")
                    return
        client_code = await self.db.get_user_client_code(user_id) or f"VX-{user_id:06d}"
        await message.reply_text(
            text=self._configs_list_text(client_code=client_code, subscriptions=subscriptions),
            reply_markup=self._configs_list_markup(subscriptions),
        )

    async def _send_menu_node(
        self,
        update: Update,
        node_key: str,
        parent_key: str | None = None,
    ) -> None:
        assert update.message is not None
        text = self._node_response_text(node_key)
        markup = self._node_inline_keyboard(node_key, parent_key=parent_key)
        await update.message.reply_text(text=text, reply_markup=markup)

    async def _refresh_cms(self, force: bool = False) -> None:
        if self.cms is None:
            return

        now = time.monotonic()
        ttl = max(self.settings.cms_cache_ttl_seconds, 5)
        if not force and (now - self._cms_loaded_at) < ttl:
            return

        async with self._cms_lock:
            if not force and (time.monotonic() - self._cms_loaded_at) < ttl:
                return
            try:
                self._cms_content = await self.cms.fetch_content()
                self._cms_buttons = await self.cms.fetch_buttons()
                self._cms_loaded_at = time.monotonic()
            except Exception:
                LOGGER.exception("Failed to refresh CMS content")

    async def _get_provision_lock(self, user_id: int) -> asyncio.Lock:
        async with self._provision_locks_guard:
            lock = self._provision_locks.get(user_id)
            if lock is None:
                lock = asyncio.Lock()
                self._provision_locks[user_id] = lock
            return lock

    async def _run_user_provision(
        self,
        user_id: int,
        action: Callable[[], Awaitable[None]],
    ) -> None:
        lock = await self._get_provision_lock(user_id)
        async with lock:
            await action()

    @staticmethod
    def _normalize_phone(value: str) -> str:
        raw = value.strip()
        if not raw:
            raise ValueError("empty")
        if raw.startswith("+"):
            digits = re.sub(r"\D", "", raw)
            normalized = f"+{digits}"
        else:
            digits = re.sub(r"\D", "", raw)
            if digits.startswith("00"):
                digits = digits[2:]
            if len(digits) == 11 and digits.startswith("8"):
                digits = f"7{digits[1:]}"
            elif len(digits) == 10:
                digits = f"7{digits}"
            normalized = f"+{digits}"
        digits_only = normalized[1:]
        if len(digits_only) < 10 or len(digits_only) > 15:
            raise ValueError("bad-length")
        return normalized

    @staticmethod
    def _phone_for_email(normalized_phone: str, user_id: int) -> str:
        digits = re.sub(r"\D", "", normalized_phone)
        return f"tel{digits}_tg{user_id}"

    @staticmethod
    def _subscription_name(sub: dict[str, object]) -> str:
        display_name = str(sub.get("display_name") or "").strip()
        if display_name:
            return display_name
        client_email = str(sub.get("client_email") or "").strip()
        if client_email:
            return client_email
        return f"Config #{sub.get('id')}"

    @staticmethod
    def _subscription_status(sub: dict[str, object], now: datetime) -> str:
        if sub.get("revoked_at") is not None:
            return "отозван"
        expires_at = sub.get("expires_at")
        if not isinstance(expires_at, datetime):
            return "неизвестно"
        if not bool(sub.get("is_active")):
            return "истек" if expires_at <= now else "неактивен"
        return "активен" if expires_at > now else "истек"

    async def _start_buy_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        context.user_data.pop("buy_wait_phone", None)
        context.user_data.pop("buy_wait_name", None)
        context.user_data.pop("buy_phone", None)
        user_id = await self._ensure_user(update)
        message = update.message or (update.callback_query.message if update.callback_query else None)
        if message is None:
            return
        await self._send_stars_invoice_for_message(message, user_id=user_id, mode="buynew")

    async def _resolve_subscription_links(self, user_id: int, sub: dict[str, object]) -> tuple[str, str | None]:
        vless_url = str(sub["vless_url"])
        client_uuid = str(sub["client_uuid"])
        inbound_id = int(sub["inbound_id"])
        sub_id = await self.xui.get_client_sub_id(inbound_id, client_uuid)

        expires_at = sub.get("expires_at")
        is_active = bool(sub.get("is_active"))
        is_revoked = sub.get("revoked_at") is not None
        now = datetime.now(timezone.utc)
        if not sub_id and is_active and not is_revoked and isinstance(expires_at, datetime) and expires_at > now:
            restored = await self._restore_xui_profile_for_subscription(user_id, sub)
            if restored is not None:
                vless_url, sub_id = restored

        sub_url = (
            f"https://{self.settings.vpn_public_host}:{self.settings.xui_sub_port}/sub/{sub_id}"
            if sub_id
            else None
        )
        return vless_url, sub_url

    def _configs_list_text(
        self,
        *,
        client_code: str,
        subscriptions: list[dict[str, object]],
    ) -> str:
        now = datetime.now(timezone.utc)
        item_template = self._content_text(
            "my_configs_item_template",
            "{index}. {name}\n   До: {expires_at}\n   Статус: {status}",
        )
        items: list[str] = []
        if not subscriptions:
            return self._content_text(
                "my_configs_empty_message",
                "📚 Мои конфиги\nClient code: {client_code}\n\nКонфигов пока нет.",
            ).replace("{client_code}", client_code)

        for idx, sub in enumerate(subscriptions, start=1):
            expires_at = sub.get("expires_at")
            expires_text = self._format_local_dt(expires_at) if isinstance(expires_at, datetime) else "—"
            items.append(
                item_template
                .replace("{index}", str(idx))
                .replace("{name}", self._subscription_name(sub))
                .replace("{expires_at}", expires_text)
                .replace("{status}", self._subscription_status(sub, now))
            )

        return self._content_text(
            "my_configs_list_template",
            "📚 Мои конфиги\nClient code: {client_code}\n\n{items}",
        ).replace("{client_code}", client_code).replace("{items}", "\n".join(items))

    def _configs_list_markup(self, subscriptions: list[dict[str, object]]) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = []
        for idx, sub in enumerate(subscriptions, start=1):
            sub_id = int(sub["id"])
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"{idx}. {self._subscription_name(sub)}",
                        callback_data=f"act|cfg_open:{sub_id}|_",
                    )
                ]
            )
        rows.append(
            [
                InlineKeyboardButton(
                    text=self._button_label("buy_new_config_button", "➕ Купить новый конфиг"),
                    callback_data="act|buy_new|_",
                )
            ]
        )
        return InlineKeyboardMarkup(rows)

    def _config_card_markup(self, subscription_id: int, open_app_url: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text="📋 Copy", callback_data=f"act|cfg_copy:{subscription_id}|_"),
                    InlineKeyboardButton(text="🧾 QR", callback_data=f"act|cfg_qr:{subscription_id}|_"),
                ],
                [
                    InlineKeyboardButton(text="🚀 Open in app", url=open_app_url),
                    InlineKeyboardButton(text="🔄 Renew", callback_data=f"act|cfg_renew:{subscription_id}|_"),
                ],
                [
                    InlineKeyboardButton(text="✏️ Rename", callback_data=f"act|cfg_rename:{subscription_id}|_"),
                    InlineKeyboardButton(text="⛔ Revoke", callback_data=f"act|cfg_revoke:{subscription_id}|_"),
                ],
                [InlineKeyboardButton(text="⬅️ Back", callback_data="act|cfg_back|_")],
            ]
        )

    async def _config_card_text(self, user_id: int, sub: dict[str, object], *, client_code: str) -> tuple[str, str, str | None]:
        vless_url, sub_url = await self._resolve_subscription_links(user_id, sub)
        last_payment_method = await self.db.get_latest_payment_method(user_id)
        expires_at = sub.get("expires_at")
        expires_text = self._format_local_dt(expires_at) if isinstance(expires_at, datetime) else "—"
        status_text = self._subscription_status(sub, datetime.now(timezone.utc))
        text = (
            f"⚙️ {self._subscription_name(sub)}\n"
            f"ID: {sub['id']}\n"
            f"Client code: {client_code}\n"
            f"Статус: {status_text}\n"
            f"Действует до: {expires_text}\n"
            f"Способ оплаты: {self._format_payment_method(last_payment_method)}"
        )
        return text, vless_url, sub_url

    async def _ensure_user(self, update: Update) -> int:
        assert update.effective_user is not None
        u = update.effective_user
        return await self.db.upsert_user(u.id, u.username, u.first_name)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = await self._ensure_user(update)
        await self._refresh_cms()
        start_arg = (context.args[0].strip() if context.args else "")
        if start_arg.startswith("link_"):
            link_code = start_arg.removeprefix("link_")
            status = await self.db.consume_telegram_link_code(link_code, update.effective_user.id)
            if status == "ok":
                await update.message.reply_text(
                    self._content_text(
                        "link_success_message",
                        "Ð“Ð¾Ñ‚Ð¾Ð²Ð¾! Telegram ÑƒÑÐ¿ÐµÑˆÐ½Ð¾ Ð¿Ñ€Ð¸Ð²ÑÐ·Ð°Ð½ Ðº Ð²Ð°ÑˆÐµÐ¼Ñƒ Ð°ÐºÐºÐ°ÑƒÐ½Ñ‚Ñƒ Ð½Ð° ÑÐ°Ð¹Ñ‚Ðµ.",
                    ),
                    reply_markup=await self._menu_keyboard_for_user(user_id),
                )
                return
            if status == "used":
                await update.message.reply_text(
                    self._content_text(
                        "link_used_message",
                        "Ð­Ñ‚Ð¾Ñ‚ ÐºÐ¾Ð´ ÑƒÐ¶Ðµ Ð¸ÑÐ¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ð½. Ð¡Ð³ÐµÐ½ÐµÑ€Ð¸Ñ€ÑƒÐ¹Ñ‚Ðµ Ð½Ð¾Ð²Ñ‹Ð¹ ÐºÐ¾Ð´ Ð½Ð° ÑÐ°Ð¹Ñ‚Ðµ.",
                    ),
                    reply_markup=await self._menu_keyboard_for_user(user_id),
                )
                return
            if status == "expired":
                await update.message.reply_text(
                    self._content_text(
                        "link_expired_message",
                        "ÐšÐ¾Ð´ Ð¿Ñ€Ð¸Ð²ÑÐ·ÐºÐ¸ Ð¸ÑÑ‚ÐµÐº. Ð¡Ð³ÐµÐ½ÐµÑ€Ð¸Ñ€ÑƒÐ¹Ñ‚Ðµ Ð½Ð¾Ð²Ñ‹Ð¹ ÐºÐ¾Ð´ Ð½Ð° ÑÐ°Ð¹Ñ‚Ðµ.",
                    ),
                    reply_markup=await self._menu_keyboard_for_user(user_id),
                )
                return
            await update.message.reply_text(
                self._content_text(
                    "link_invalid_message",
                    "ÐÐµÐ²ÐµÑ€Ð½Ñ‹Ð¹ ÐºÐ¾Ð´ Ð¿Ñ€Ð¸Ð²ÑÐ·ÐºÐ¸. ÐŸÑ€Ð¾Ð²ÐµÑ€ÑŒÑ‚Ðµ ÐºÐ¾Ð´ Ð¸ Ð¿Ð¾Ð¿Ñ€Ð¾Ð±ÑƒÐ¹Ñ‚Ðµ ÑÐ½Ð¾Ð²Ð°.",
                ),
                reply_markup=await self._menu_keyboard_for_user(user_id),
            )
            return

        await self._send_start_screen(update.message, user_id)

    async def menu_click(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._refresh_cms()
        raw_text = (update.message.text or "").strip()
        text = raw_text.lower()
        cancel_label = self._button_label("contact_cancel", "\u041e\u0442\u043c\u0435\u043d\u0430").strip().lower()
        user_id = await self._ensure_user(update)
        menu_keyboard = await self._menu_keyboard_for_user(user_id)

        if text in {"cancel", "\u043e\u0442\u043c\u0435\u043d\u0430", cancel_label}:
            context.user_data.pop("buy_wait_phone", None)
            context.user_data.pop("buy_wait_name", None)
            context.user_data.pop("buy_phone", None)
            context.user_data.pop("support_wait_message", None)
            await update.message.reply_text(
                self._content_text("cancel_message", "\u041e\u043f\u0435\u0440\u0430\u0446\u0438\u044f \u043e\u0442\u043c\u0435\u043d\u0435\u043d\u0430."),
                reply_markup=menu_keyboard,
            )
            return

        if context.user_data.get("support_wait_message"):
            context.user_data.pop("support_wait_message", None)
            text_value = raw_text.strip()
            if not text_value:
                await update.message.reply_text(
                    self._content_text(
                        "support_empty_message",
                        "Текст обращения пустой. Нажмите «Поддержка» и попробуйте снова.",
                    ),
                    reply_markup=menu_keyboard,
                )
                return

            ticket_subject = self._content_text("support_default_subject", "Запрос из Telegram-бота")
            ticket_id = await self.db.create_ticket(user_id=user_id, subject=ticket_subject)
            await self.db.add_message(
                ticket_id=ticket_id,
                sender_role="user",
                sender_user_id=user_id,
                message_text=text_value,
            )

            if self.settings.telegram_admin_id:
                try:
                    client_code = await self.db.get_user_client_code(user_id)
                    header = self._content_text(
                        "support_admin_new_ticket_header",
                        "🆘 Новый тикет поддержки",
                    )
                    await self.app.bot.send_message(
                        chat_id=self.settings.telegram_admin_id,
                        text=(
                            f"{header}\n"
                            f"ticket_id={ticket_id}\n"
                            f"user_id={user_id}\n"
                            f"client_code={client_code or '-'}\n\n"
                            f"{text_value}"
                        ),
                    )
                except Exception:
                    LOGGER.exception("Failed to notify admin about support ticket_id=%s", ticket_id)

            await update.message.reply_text(
                self._content_text(
                    "support_received_message",
                    "✅ Обращение отправлено в поддержку. Мы ответим вам в ближайшее время.",
                ).replace("{ticket_id}", str(ticket_id)),
                reply_markup=menu_keyboard,
            )
            return

        rename_sub_id_raw = context.user_data.get("rename_wait_subscription_id")
        if rename_sub_id_raw is not None:
            context.user_data.pop("rename_wait_subscription_id", None)
            new_name = raw_text.strip()
            if not new_name:
                await update.message.reply_text(
                    "Имя не должно быть пустым. Операция отменена.",
                    reply_markup=menu_keyboard,
                )
                return
            try:
                subscription_id = int(rename_sub_id_raw)
            except (TypeError, ValueError):
                await update.message.reply_text(
                    "Не удалось определить конфиг для переименования.",
                    reply_markup=menu_keyboard,
                )
                return
            renamed = await self.db.rename_subscription(
                user_id=user_id,
                subscription_id=subscription_id,
                display_name=new_name[:80],
            )
            if not renamed:
                await update.message.reply_text(
                    "Не удалось переименовать конфиг.",
                    reply_markup=menu_keyboard,
                )
                return
            await update.message.reply_text(
                f"Имя конфига обновлено: {new_name[:80]}",
                reply_markup=menu_keyboard,
            )
            await self.mysub(update, context)
            return

        menu_buttons = self._menu_buttons(has_active_subscription=await self._has_active_subscription(user_id))
        label_to_key = {label.strip().lower(): key for key, label in menu_buttons}
        selected_menu_key = label_to_key.get(text)

        if selected_menu_key == "menu_buy":
            await self.buy(update, context)
            return
        if selected_menu_key == "menu_renew":
            await self.renew(update, context)
            return
        if selected_menu_key == "menu_mysub":
            await self.mysub(update, context)
            return
        if selected_menu_key == "menu_trial":
            await self.trial(update, context)
            return
        if selected_menu_key == "menu_instructions":
            await self._send_menu_node(update, selected_menu_key)
            return
        if selected_menu_key == "menu_site":
            return

        if selected_menu_key:
            await self._send_menu_node(update, selected_menu_key)
            return
        await update.message.reply_text(
            self._content_text("menu_unknown_message", "\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 \u043a\u043d\u043e\u043f\u043a\u0438 \u043c\u0435\u043d\u044e \u043d\u0438\u0436\u0435."),
            reply_markup=menu_keyboard,
        )

    async def buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._refresh_cms()
        await self._start_buy_flow(update, context)

    async def trial(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._refresh_cms()
        message = update.message or (update.callback_query.message if update.callback_query else None)
        if message is None:
            return
        user_id = await self._ensure_user(update)
        await self._show_trial_offer(message, user_id)

    async def renew(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = await self._ensure_user(update)
        selected_id = context.user_data.get("selected_subscription_id")
        target_subscription_id: int | None = None
        if isinstance(selected_id, int):
            target_subscription_id = selected_id
        elif isinstance(selected_id, str) and selected_id.isdigit():
            target_subscription_id = int(selected_id)
        else:
            active_sub = await self.db.get_active_subscription(user_id)
            if active_sub:
                target_subscription_id = int(active_sub["id"])
                context.user_data["selected_subscription_id"] = target_subscription_id
        await self._send_stars_invoice(update, user_id, mode="renew", target_subscription_id=target_subscription_id)

    async def admin_reload(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.cms is None:
            await update.message.reply_text("CMS is not configured.")
            return
        if not update.effective_user or update.effective_user.id != self.settings.telegram_admin_id:
            await update.message.reply_text("Access denied.")
            return
        await self._refresh_cms(force=True)
        await update.message.reply_text("CMS content reloaded.")

    def _is_admin(self, update: Update) -> bool:
        user = update.effective_user
        return bool(user and user.id == self.settings.telegram_admin_id)

    @staticmethod
    def _ticket_preview(text: str, limit: int = 90) -> str:
        normalized = " ".join((text or "").split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: max(0, limit - 1)] + "…"

    @staticmethod
    def _parse_ticket_id(args: list[str]) -> int | None:
        if not args:
            return None
        raw = (args[0] or "").strip()
        if not raw.isdigit():
            return None
        return int(raw)

    async def admin_tickets(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_admin(update):
            assert update.message is not None
            await update.message.reply_text("Access denied.")
            return
        assert update.message is not None

        tickets = await self.db.list_open_tickets_for_admin(limit=50)
        if not tickets:
            await update.message.reply_text("Открытых тикетов нет.")
            return

        lines: list[str] = ["🧾 Открытые тикеты:"]
        for ticket in tickets:
            ticket_id = int(ticket["id"])
            updated_at = ticket.get("updated_at")
            updated_text = self._format_local_dt(updated_at) if isinstance(updated_at, datetime) else "—"
            client_code = str(ticket.get("client_code") or "-")
            preview = self._ticket_preview(str(ticket.get("last_message_text") or ""))
            lines.append(
                f"#{ticket_id} | {client_code} | {updated_text}\n"
                f"{preview or '(без сообщений)'}"
            )

        await update.message.reply_text("\n\n".join(lines))

    async def admin_ticket(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_admin(update):
            assert update.message is not None
            await update.message.reply_text("Access denied.")
            return
        assert update.message is not None

        ticket_id = self._parse_ticket_id(context.args)
        if ticket_id is None:
            await update.message.reply_text("Usage: /ticket <id>")
            return

        ticket = await self.db.get_ticket_for_admin(ticket_id)
        if not ticket:
            await update.message.reply_text(f"Тикет #{ticket_id} не найден.")
            return

        messages = await self.db.list_ticket_messages(ticket_id=ticket_id, limit=10)
        header = (
            f"Тикет #{ticket_id}\n"
            f"Статус: {ticket.get('status')}\n"
            f"Client code: {ticket.get('client_code') or '-'}"
        )
        if not messages:
            await update.message.reply_text(f"{header}\n\nСообщений пока нет.")
            return

        lines = [header, "", "Последние сообщения (новые сверху):"]
        for msg in messages:
            created_at = msg.get("created_at")
            at_text = self._format_local_dt(created_at) if isinstance(created_at, datetime) else "—"
            role = str(msg.get("sender_role") or "unknown")
            body = self._ticket_preview(str(msg.get("message_text") or ""), limit=220)
            lines.append(f"[{at_text}] {role}: {body}")

        await update.message.reply_text("\n".join(lines))

    async def admin_reply_ticket(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_admin(update):
            assert update.message is not None
            await update.message.reply_text("Access denied.")
            return
        assert update.message is not None

        ticket_id = self._parse_ticket_id(context.args)
        if ticket_id is None or len(context.args) < 2:
            await update.message.reply_text("Usage: /reply_ticket <id> <text>")
            return
        reply_text = " ".join(context.args[1:]).strip()
        if not reply_text:
            await update.message.reply_text("Usage: /reply_ticket <id> <text>")
            return

        ticket = await self.db.get_ticket_for_admin(ticket_id)
        if not ticket:
            await update.message.reply_text(f"Тикет #{ticket_id} не найден.")
            return
        if str(ticket.get("status") or "").lower() == "closed":
            await update.message.reply_text(f"Тикет #{ticket_id} уже закрыт.")
            return

        telegram_id = ticket.get("telegram_id")
        if telegram_id is None:
            await update.message.reply_text(
                f"Тикет #{ticket_id} не привязан к Telegram-пользователю."
            )
            return

        await self.db.add_message(
            ticket_id=ticket_id,
            sender_role="admin",
            sender_user_id=None,
            message_text=reply_text,
        )

        try:
            await self.app.bot.send_message(
                chat_id=int(telegram_id),
                text=self._content_text(
                    "support_admin_reply_prefix",
                    "💬 Ответ поддержки:\n\n{message}",
                ).replace("{message}", reply_text),
            )
        except Exception:
            LOGGER.exception(
                "Failed to send admin reply to ticket_id=%s telegram_id=%s",
                ticket_id,
                telegram_id,
            )
            await update.message.reply_text(
                f"Тикет #{ticket_id}: ответ сохранен, но не удалось отправить пользователю."
            )
            return

        await update.message.reply_text(f"Ответ отправлен (ticket #{ticket_id}).")

    async def admin_close_ticket(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_admin(update):
            assert update.message is not None
            await update.message.reply_text("Access denied.")
            return
        assert update.message is not None

        ticket_id = self._parse_ticket_id(context.args)
        if ticket_id is None:
            await update.message.reply_text("Usage: /close <id>")
            return

        ticket = await self.db.get_ticket_for_admin(ticket_id)
        if not ticket:
            await update.message.reply_text(f"Тикет #{ticket_id} не найден.")
            return

        closed = await self.db.close_ticket(ticket_id)
        if not closed:
            await update.message.reply_text(f"Тикет #{ticket_id} уже закрыт.")
            return
        await update.message.reply_text(f"Тикет #{ticket_id} закрыт.")

    async def reply_support(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_admin(update):
            await update.message.reply_text("Access denied.")
            return
        if not context.args or len(context.args) < 2:
            await update.message.reply_text("Usage: /reply <client_code> <text>")
            return

        client_code = context.args[0].strip()
        reply_text = " ".join(context.args[1:]).strip()
        if not client_code or not reply_text:
            await update.message.reply_text("Usage: /reply <client_code> <text>")
            return

        user = await self.db.get_user_by_client_code(client_code)
        if not user:
            await update.message.reply_text(f"User not found for client_code={client_code}")
            return

        user_id = int(user["id"])
        telegram_id = int(user["telegram_id"])
        normalized_client_code = str(user.get("client_code") or client_code).upper()

        ticket = await self.db.get_latest_open_ticket_for_user(user_id)
        if ticket:
            ticket_id = int(ticket["id"])
        else:
            ticket_id = await self.db.create_ticket(
                user_id=user_id,
                subject=self._content_text("support_admin_reply_subject", "Ответ поддержки"),
            )

        await self.db.add_message(
            ticket_id=ticket_id,
            sender_role="admin",
            sender_user_id=None,
            message_text=reply_text,
        )

        try:
            await self.app.bot.send_message(
                chat_id=telegram_id,
                text=(
                    self._content_text(
                        "support_admin_reply_prefix",
                        "💬 Ответ поддержки:\n\n{message}",
                    ).replace("{message}", reply_text)
                ),
            )
        except Exception:
            LOGGER.exception(
                "Failed to deliver support reply ticket_id=%s user_id=%s telegram_id=%s",
                ticket_id,
                user_id,
                telegram_id,
            )
            await update.message.reply_text(
                f"Ticket #{ticket_id}: message logged, but failed to deliver to Telegram user {telegram_id}."
            )
            return

        await update.message.reply_text(
            f"Sent to {normalized_client_code} (ticket #{ticket_id})."
        )

    async def inline_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._refresh_cms()
        query = update.callback_query
        if query is None:
            return
        data = query.data or ""
        parts = data.split("|")
        if len(parts) != 3:
            await query.answer()
            return

        kind, target, parent = parts
        if kind == "nav":
            text = self._node_response_text(target)
            parent_key = None if parent == "_" else parent
            markup = self._node_inline_keyboard(target, parent_key=parent_key)
            await query.edit_message_text(text=text, reply_markup=markup)
            await query.answer()
            return

        if kind == "msg":
            response = self._content_text(target, self._content_text("menu_unknown_message", "\u041a\u043e\u043d\u0442\u0435\u043d\u0442 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d."))
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(response)
            return

        if kind == "act":
            if target == "start_trial":
                await query.answer()
                if query.message is not None:
                    user_id = await self._ensure_user(update)
                    await self._show_trial_offer(query.message, user_id)
                return
            if target == "trial_activate":
                await query.answer()
                if query.message is not None:
                    user_id = await self._ensure_user(update)
                    if await self.db.has_any_subscription(user_id):
                        await query.message.reply_text(
                            "Пробный доступ уже был использован\n\n"
                            "Вы можете сразу оформить платный доступ.",
                            reply_markup=self._trial_used_markup(),
                        )
                    else:
                        await query.message.reply_text("Активирую пробный доступ...")
                        await self._run_user_provision(
                            user_id,
                            lambda: self._create_trial_for_user(update, user_id=user_id, days=7),
                        )
                return
            if target == "start_back":
                await query.answer()
                if query.message is not None:
                    user_id = await self._ensure_user(update)
                    await self._send_start_screen(query.message, user_id)
                return
            if target == "start_mysub":
                await query.answer()
                if query.message is not None:
                    user_id = await self._ensure_user(update)
                    await self._send_mysub_for_message(query.message, user_id, context)
                return
            if target == "support_start":
                context.user_data["support_wait_message"] = True
                await query.answer()
                if query.message is not None:
                    await query.message.reply_text(
                        self._content_text(
                            "support_start_message",
                            "Опишите проблему одним сообщением. Мы создадим тикет и передадим его в поддержку.",
                        )
                    )
                return
            if target == "buy_new":
                await query.answer()
                if query.message is not None:
                    await self._start_buy_flow(update, context)
                return
            if target == "cfg_back":
                user_id = await self._ensure_user(update)
                subscriptions = await self.db.list_subscriptions(user_id)
                client_code = await self.db.get_user_client_code(user_id) or f"VX-{user_id:06d}"
                await query.answer()
                await query.edit_message_text(
                    text=self._configs_list_text(client_code=client_code, subscriptions=subscriptions),
                    reply_markup=self._configs_list_markup(subscriptions),
                )
                return
            if target.startswith("cfg_open:"):
                user_id = await self._ensure_user(update)
                try:
                    subscription_id = int(target.split(":", 1)[1])
                except (IndexError, ValueError):
                    await query.answer("Некорректный конфиг", show_alert=True)
                    return
                sub = await self.db.get_subscription(user_id, subscription_id)
                if not sub:
                    await query.answer("Конфиг не найден", show_alert=True)
                    return
                context.user_data["selected_subscription_id"] = subscription_id
                client_code = await self.db.get_user_client_code(user_id) or f"VX-{user_id:06d}"
                text, vless_url, sub_url = await self._config_card_text(user_id, sub, client_code=client_code)
                open_app_link = self._open_app_url(sub_url or vless_url)
                await query.answer()
                await query.edit_message_text(
                    text=text,
                    reply_markup=self._config_card_markup(subscription_id, open_app_link),
                )
                return
            if target.startswith("cfg_copy:"):
                user_id = await self._ensure_user(update)
                try:
                    subscription_id = int(target.split(":", 1)[1])
                except (IndexError, ValueError):
                    await query.answer("Некорректный конфиг", show_alert=True)
                    return
                sub = await self.db.get_subscription(user_id, subscription_id)
                if not sub:
                    await query.answer("Конфиг не найден", show_alert=True)
                    return
                _, vless_url, sub_url = await self._config_card_text(
                    user_id,
                    sub,
                    client_code=(await self.db.get_user_client_code(user_id) or f"VX-{user_id:06d}"),
                )
                await query.answer("Ссылку отправил в чат")
                if query.message is not None:
                    await query.message.reply_text(f"Скопируйте ссылку:\n{sub_url or vless_url}")
                return
            if target.startswith("cfg_qr:"):
                user_id = await self._ensure_user(update)
                try:
                    subscription_id = int(target.split(":", 1)[1])
                except (IndexError, ValueError):
                    await query.answer("Некорректный конфиг", show_alert=True)
                    return
                sub = await self.db.get_subscription(user_id, subscription_id)
                if not sub:
                    await query.answer("Конфиг не найден", show_alert=True)
                    return
                text, vless_url, sub_url = await self._config_card_text(
                    user_id,
                    sub,
                    client_code=(await self.db.get_user_client_code(user_id) or f"VX-{user_id:06d}"),
                )
                qr_payload = sub_url or vless_url
                qr_img = self._build_styled_qr(qr_payload, "Subscription QR")
                qr_buff = io.BytesIO()
                qr_img.save(qr_buff, format="PNG")
                qr_buff.seek(0)
                await query.answer("QR отправлен")
                if query.message is not None:
                    await query.message.reply_photo(photo=qr_buff, caption=text)
                return
            if target.startswith("cfg_renew:"):
                user_id = await self._ensure_user(update)
                try:
                    subscription_id = int(target.split(":", 1)[1])
                except (IndexError, ValueError):
                    await query.answer("Некорректный конфиг", show_alert=True)
                    return
                sub = await self.db.get_subscription(user_id, subscription_id)
                if not sub:
                    await query.answer("Конфиг не найден", show_alert=True)
                    return
                context.user_data["selected_subscription_id"] = subscription_id
                await query.answer()
                if query.message is not None:
                    await self._send_stars_invoice_for_message(
                        query.message,
                        user_id,
                        mode="renew",
                        target_subscription_id=subscription_id,
                    )
                return
            if target.startswith("cfg_rename:"):
                try:
                    subscription_id = int(target.split(":", 1)[1])
                except (IndexError, ValueError):
                    await query.answer("Некорректный конфиг", show_alert=True)
                    return
                context.user_data["rename_wait_subscription_id"] = subscription_id
                await query.answer()
                if query.message is not None:
                    await query.message.reply_text("Отправьте новое имя конфига одним сообщением.")
                return
            if target.startswith("cfg_revoke:"):
                user_id = await self._ensure_user(update)
                try:
                    subscription_id = int(target.split(":", 1)[1])
                except (IndexError, ValueError):
                    await query.answer("Некорректный конфиг", show_alert=True)
                    return
                sub = await self.db.get_subscription(user_id, subscription_id)
                if not sub:
                    await query.answer("Конфиг не найден", show_alert=True)
                    return
                revoked = await self.db.revoke_subscription(user_id, subscription_id)
                if revoked:
                    try:
                        await self.xui.set_client_enabled(
                            int(sub["inbound_id"]),
                            str(sub["client_uuid"]),
                            str(sub["client_email"]),
                            sub["expires_at"],
                            enable=False,
                            limit_ip=self.settings.max_devices_per_sub,
                        )
                    except Exception:
                        LOGGER.exception("Failed to disable revoked config in x-ui subscription_id=%s", subscription_id)
                await query.answer("Конфиг отозван" if revoked else "Не удалось отозвать конфиг")
                subscriptions = await self.db.list_subscriptions(user_id)
                client_code = await self.db.get_user_client_code(user_id) or f"VX-{user_id:06d}"
                await query.edit_message_text(
                    text=self._configs_list_text(client_code=client_code, subscriptions=subscriptions),
                    reply_markup=self._configs_list_markup(subscriptions),
                )
                return
            await query.answer()
            return

        if kind == "copy":
            link = self._copy_links.get(target)
            await query.answer()
            if query.message is not None:
                if link:
                    await query.message.reply_text(f"\u0421\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443 \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0438:\\n{link}")
                else:
                    await query.message.reply_text("\u0421\u0441\u044b\u043b\u043a\u0430 \u0443\u0441\u0442\u0430\u0440\u0435\u043b\u0430. \u041d\u0430\u0436\u043c\u0438\u0442\u0435 \xab\u041c\u043e\u044f \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0430\xbb \u0435\u0449\u0435 \u0440\u0430\u0437.")
            return

        await query.answer()


    async def mysub(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._refresh_cms()
        message = update.message or (update.callback_query.message if update.callback_query else None)
        if message is None:
            return
        user_id = await self._ensure_user(update)
        await self._send_mysub_for_message(message, user_id, context)

    async def _restore_xui_profile_for_subscription(
        self,
        user_id: int,
        sub: dict[str, object],
    ) -> tuple[str, str | None] | None:
        inbound_id = int(sub["inbound_id"])
        client_uuid = str(sub["client_uuid"])
        client_email = str(sub["client_email"])
        expires_at = sub["expires_at"]
        assert isinstance(expires_at, datetime)

        try:
            inbound = await self.xui.get_inbound(inbound_id)
            reality = self.xui.parse_reality(inbound)
            inbound_port = int(inbound["port"])

            try:
                await self.xui.add_client(
                    inbound_id,
                    client_uuid,
                    client_email,
                    expires_at,
                    limit_ip=self.settings.max_devices_per_sub,
                )
            except Exception:
                LOGGER.exception(
                    "add_client failed while restoring XUI profile (user_id=%s, subscription_id=%s), trying update_client",
                    user_id,
                    sub.get("id"),
                )
                await self.xui.update_client(
                    inbound_id,
                    client_uuid,
                    client_email,
                    expires_at,
                    limit_ip=self.settings.max_devices_per_sub,
                )

            sub_id = await self.xui.get_client_sub_id(inbound_id, client_uuid)
            await self.db.update_subscription_xui_sub_id(int(sub["id"]), sub_id)

            vless_url = build_vless_url(
                uuid=client_uuid,
                host=self.settings.vpn_public_host,
                port=self.settings.vpn_public_port or inbound_port,
                tag=self.settings.vpn_tag,
                public_key=reality.public_key,
                short_id=reality.short_id,
                sni=reality.sni,
                fingerprint=reality.fingerprint,
            )
            await self.db.extend_subscription(int(sub["id"]), expires_at, vless_url)
            return vless_url, sub_id
        except Exception:
            LOGGER.exception(
                "Failed to restore XUI profile for user_id=%s subscription_id=%s",
                user_id,
                sub.get("id"),
            )
            return None

    async def _send_stars_invoice(
        self,
        update: Update,
        user_id: int,
        phone: str | None = None,
        customer_name: str | None = None,
        mode: str = "buynew",
        target_subscription_id: int | None = None,
    ) -> None:
        assert update.message is not None
        await self._send_stars_invoice_for_message(
            update.message,
            user_id=user_id,
            phone=phone,
            customer_name=customer_name,
            mode=mode,
            target_subscription_id=target_subscription_id,
        )

    async def _send_stars_invoice_for_message(
        self,
        message: Message,
        user_id: int,
        phone: str | None = None,
        customer_name: str | None = None,
        mode: str = "buynew",
        target_subscription_id: int | None = None,
    ) -> None:
        await self._refresh_cms()
        await message.reply_text(
            self._content_text(
                "stars_only_notice",
                "Оплата в боте доступна только через Telegram Stars ⭐\nДля iPhone обычно используется способ оплаты через мобильный баланс МТС.",
            )
        )
        mode_prefix = "renew" if mode == "renew" else "buynew"
        timestamp = int(datetime.now(timezone.utc).timestamp())
        rand = uuid.uuid4().hex[:6]
        if mode_prefix == "renew":
            payload = f"{mode_prefix}:{user_id}:{int(target_subscription_id or 0)}:{timestamp}:{rand}"
        else:
            payload = f"{mode_prefix}:{user_id}:{timestamp}:{rand}"
        await self.db.create_order(user_id=user_id, amount_stars=self.settings.plan_price_stars, payload=payload)
        if phone:
            self._pending_profiles[payload] = {"phone": phone, "name": (customer_name or "").strip()}
        price_label = self._content_text("invoice_price_label", "Оплата в Stars")
        prices = [LabeledPrice(label=price_label, amount=self.settings.plan_price_stars)]
        title = self._content_text("invoice_title", "Оплата VXcloud через Stars")
        description = self._content_text(
            "invoice_description",
            "Оплата подписки выполняется только Telegram Stars. Для iPhone чаще всего — через мобильный баланс МТС.",
        )
        await message.reply_invoice(
            title=title,
            description=description,
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices,
        )

    async def precheckout(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.pre_checkout_query
        order = await self.db.get_order_by_payload(query.invoice_payload)
        if not order:
            await query.answer(ok=False, error_message="Ð—Ð°ÐºÐ°Ð· Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½. ÐŸÐ¾Ð¿Ñ€Ð¾Ð±ÑƒÐ¹Ñ‚Ðµ ÑÐ½Ð¾Ð²Ð°.")
            return
        if order["status"] != "pending":
            await query.answer(ok=False, error_message="Ð—Ð°ÐºÐ°Ð· ÑƒÐ¶Ðµ Ð¾Ð±Ñ€Ð°Ð±Ð¾Ñ‚Ð°Ð½.")
            return
        if int(query.total_amount) != int(order["amount_stars"]):
            await query.answer(ok=False, error_message="Ð¡ÑƒÐ¼Ð¼Ð° Ð½Ðµ ÑÐ¾Ð²Ð¿Ð°Ð´Ð°ÐµÑ‚. ÐŸÐ¾Ð¿Ñ€Ð¾Ð±ÑƒÐ¹Ñ‚Ðµ ÑÐ½Ð¾Ð²Ð°.")
            return
        await query.answer(ok=True)


    async def successful_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        assert update.message is not None
        payment = update.message.successful_payment
        order = await self.db.get_order_by_payload(payment.invoice_payload)
        if not order:
            await update.message.reply_text("ÐžÐ¿Ð»Ð°Ñ‚Ð° Ð¿Ð¾Ð»ÑƒÑ‡ÐµÐ½Ð°, Ð½Ð¾ Ð·Ð°ÐºÐ°Ð· Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½. ÐžÐ±Ñ€Ð°Ñ‚Ð¸Ñ‚ÐµÑÑŒ Ð² Ð¿Ð¾Ð´Ð´ÐµÑ€Ð¶ÐºÑƒ.")
            return

        charge_id = payment.telegram_payment_charge_id
        order_id = int(order["id"])
        user_id = int(order["user_id"])
        provider = "stars"
        client_code = await self.db.get_user_client_code(user_id)
        _log_payment_event(
            order_id=order_id,
            client_code=client_code,
            provider=provider,
            event_id=charge_id,
            provision_state="payment_received",
        )
        if await self.db.is_charge_processed(charge_id):
            # Recover path for duplicate callbacks: try to return config immediately.
            _log_payment_event(
                order_id=order_id,
                client_code=client_code,
                provider=provider,
                event_id=charge_id,
                provision_state="duplicate_charge_ignored",
            )
            await update.message.reply_text(
                self._content_text(
                    "payment_already_processed_message",
                    "ÐŸÐ»Ð°Ñ‚ÐµÐ¶ ÑƒÐ¶Ðµ Ð¾Ð±Ñ€Ð°Ð±Ð¾Ñ‚Ð°Ð½. ÐžÑ‚Ð¿Ñ€Ð°Ð²Ð»ÑÑŽ Ð²Ð°ÑˆÑƒ Ð¿Ð¾Ð´Ð¿Ð¸ÑÐºÑƒ...",
                )
            )
            await self.mysub(update, context)
            return

        marked = await self.db.mark_order_paid_if_pending(
            order_id=order_id,
            telegram_payment_charge_id=charge_id,
            provider_payment_charge_id=payment.provider_payment_charge_id,
        )
        if not marked:
            _log_payment_event(
                order_id=order_id,
                client_code=client_code,
                provider=provider,
                event_id=charge_id,
                provision_state="already_paid_or_processing",
            )
            await update.message.reply_text(
                self._content_text(
                    "payment_already_processed_message",
                    "Платеж уже обработан. Отправляю вашу подписку...",
                )
            )
            await self.mysub(update, context)
            return
        _log_payment_event(
            order_id=order_id,
            client_code=client_code,
            provider=provider,
            event_id=charge_id,
            provision_state="paid_marked",
        )

        self._pending_profiles.pop(payment.invoice_payload, None)
        await update.message.reply_text("ÐžÐ¿Ð»Ð°Ñ‚Ð° Ð¿Ñ€Ð¾ÑˆÐ»Ð° ÑƒÑÐ¿ÐµÑˆÐ½Ð¾. ÐÐºÑ‚Ð¸Ð²Ð¸Ñ€ÑƒÑŽ Ð²Ð°Ñˆ VPN...")

        try:
            await asyncio.wait_for(
                self._run_user_provision(
                    user_id,
                    lambda: self._activate_order_and_send_config(update, order_id),
                ),
                timeout=45,
            )
        except Exception:
            _log_payment_event(
                order_id=order_id,
                client_code=client_code,
                provider=provider,
                event_id=charge_id,
                provision_state="provision_failed",
            )
            LOGGER.exception("Post-payment provisioning failed for user_id=%s order_id=%s", order["user_id"], order["id"])
            await update.message.reply_text(
                self._content_text(
                    "provision_delay_message",
                    "ÐŸÐ»Ð°Ñ‚ÐµÐ¶ Ð¿Ð¾Ð»ÑƒÑ‡ÐµÐ½, Ð½Ð¾ Ð°ÐºÑ‚Ð¸Ð²Ð°Ñ†Ð¸Ñ Ð·Ð°Ð´ÐµÑ€Ð¶Ð¸Ð²Ð°ÐµÑ‚ÑÑ. ÐÐ°Ð¶Ð¼Ð¸Ñ‚Ðµ Â«ÐœÐ¾Ñ Ð¿Ð¾Ð´Ð¿Ð¸ÑÐºÐ°Â» Ñ‡ÐµÑ€ÐµÐ· 10-20 ÑÐµÐºÑƒÐ½Ð´. Ð•ÑÐ»Ð¸ Ð½Ðµ Ð¿Ð¾ÑÐ²Ð¸Ñ‚ÑÑ, Ð½Ð°Ð¿Ð¸ÑˆÐ¸Ñ‚Ðµ Ð² Ð¿Ð¾Ð´Ð´ÐµÑ€Ð¶ÐºÑƒ.",
                )
            )
            if self.settings.telegram_admin_id:
                try:
                    await self.app.bot.send_message(
                        chat_id=self.settings.telegram_admin_id,
                        text=(
                            "âš ï¸ ÐžÑˆÐ¸Ð±ÐºÐ° Ð°ÐºÑ‚Ð¸Ð²Ð°Ñ†Ð¸Ð¸ Ð¿Ð¾ÑÐ»Ðµ Ð¾Ð¿Ð»Ð°Ñ‚Ñ‹.\n"
                            f"user_id={order['user_id']} order_id={order['id']}"
                        ),
                    )
                except Exception:
                    LOGGER.exception("Failed to notify admin about provisioning issue")

    async def _activate_order_and_send_config(self, update: Update | None, order_id: int, message: Message | None = None) -> None:
        result = await activate_subscription(
            order_id,
            db=self.db,
            xui=self.xui,
            settings=self.settings,
        )
        client_code = await self.db.get_user_client_code(result.user_id)
        _log_payment_event(
            order_id=order_id,
            client_code=client_code,
            provider="stars",
            event_id="",
            provision_state="provision_ready",
        )
        last_payment_method = await self.db.get_latest_payment_method(result.user_id)
        sub_url = (
            f"https://{self.settings.vpn_public_host}:{self.settings.xui_sub_port}/sub/{result.xui_sub_id}"
            if result.xui_sub_id
            else None
        )
        await self._send_config(
            update,
            result.vless_url,
            result.expires_at,
            sub_url,
            client_code=client_code,
            user_id=result.user_id,
            last_payment_method=last_payment_method,
            message=message,
        )

    async def myvpn(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = await self._ensure_user(update)
        sub = await self.db.get_active_subscription(user_id)
        if not sub:
            await update.message.reply_text("ÐŸÐ¾Ð´Ð¿Ð¸ÑÐºÐ° Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð°. Ð˜ÑÐ¿Ð¾Ð»ÑŒÐ·ÑƒÐ¹Ñ‚Ðµ /buy.")
            return
        client_uuid = str(sub["client_uuid"])
        sub_id = await self.xui.get_client_sub_id(self.settings.xui_inbound_id, client_uuid)
        sub_url = (
            f"https://{self.settings.vpn_public_host}:{self.settings.xui_sub_port}/sub/{sub_id}"
            if sub_id
            else None
        )
        client_code = await self.db.get_user_client_code(user_id)
        last_payment_method = await self.db.get_latest_payment_method(user_id)
        await self._send_config(
            update,
            sub["vless_url"],
            sub["expires_at"],
            sub_url,
            client_code=client_code,
            user_id=user_id,
            last_payment_method=last_payment_method,
        )

    async def _create_trial_for_user(self, update: Update, user_id: int, days: int) -> None:
        now = datetime.now(timezone.utc)
        inbound = await self.xui.get_inbound(self.settings.xui_inbound_id)
        reality = self.xui.parse_reality(inbound)
        inbound_port = int(inbound["port"])

        client_uuid = str(uuid.uuid4())
        client_email = f"trial_{user_id}_{int(now.timestamp())}"
        new_exp = now + timedelta(days=days)
        await self.xui.add_client(
            self.settings.xui_inbound_id,
            client_uuid,
            client_email,
            new_exp,
            limit_ip=self.settings.max_devices_per_sub,
            comment="trial",
        )

        vless_url = build_vless_url(
            uuid=client_uuid,
            host=self.settings.vpn_public_host,
            port=self.settings.vpn_public_port or inbound_port,
            tag=self.settings.vpn_tag,
            public_key=reality.public_key,
            short_id=reality.short_id,
            sni=reality.sni,
            fingerprint=reality.fingerprint,
        )
        await self.db.create_subscription(
            user_id=user_id,
            inbound_id=self.settings.xui_inbound_id,
            client_uuid=client_uuid,
            client_email=client_email,
            vless_url=vless_url,
            expires_at=new_exp,
        )
        sub_id = await self.xui.get_client_sub_id(self.settings.xui_inbound_id, client_uuid)
        sub_url = (
            f"https://{self.settings.vpn_public_host}:{self.settings.xui_sub_port}/sub/{sub_id}"
            if sub_id
            else None
        )
        sub_row = await self.db.get_active_subscription(user_id)
        subscription_id = int(sub_row["id"]) if sub_row else 0
        message = update.message or (update.callback_query.message if update.callback_query else None)
        if message is not None:
            await message.reply_text(
                "Пробный доступ активирован\n\n"
                "Срок действия: 7 дней\n\n"
                "Ниже вы можете сразу открыть доступ, показать QR-код\n"
                "или перейти к инструкции по подключению.",
                reply_markup=self._trial_success_markup(subscription_id) if subscription_id else None,
            )

    async def _create_or_extend_for_user(
        self,
        update: Update,
        user_id: int,
        phone: str | None = None,
        customer_name: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        sub = await self.db.get_active_subscription(user_id)

        inbound = await self.xui.get_inbound(self.settings.xui_inbound_id)
        reality = self.xui.parse_reality(inbound)
        inbound_port = int(inbound["port"])

        if sub is None:
            client_uuid = str(uuid.uuid4())
            client_email = self._phone_for_email(phone, user_id) if phone else f"tg_{user_id}_{int(now.timestamp())}"
            new_exp = now + timedelta(days=self.settings.plan_days)
            await self.xui.add_client(
                self.settings.xui_inbound_id,
                client_uuid,
                client_email,
                new_exp,
                limit_ip=self.settings.max_devices_per_sub,
                comment=customer_name,
            )

            vless_url = build_vless_url(
                uuid=client_uuid,
                host=self.settings.vpn_public_host,
                port=self.settings.vpn_public_port or inbound_port,
                tag=self.settings.vpn_tag,
                public_key=reality.public_key,
                short_id=reality.short_id,
                sni=reality.sni,
                fingerprint=reality.fingerprint,
            )
            await self.db.create_subscription(
                user_id=user_id,
                inbound_id=self.settings.xui_inbound_id,
                client_uuid=client_uuid,
                client_email=client_email,
                vless_url=vless_url,
                expires_at=new_exp,
            )
            sub_id = await self.xui.get_client_sub_id(self.settings.xui_inbound_id, client_uuid)
            sub_url = (
                f"https://{self.settings.vpn_public_host}:{self.settings.xui_sub_port}/sub/{sub_id}"
                if sub_id
                else None
            )
            last_payment_method = await self.db.get_latest_payment_method(user_id)
            await self._send_config(
                update,
                vless_url,
                new_exp,
                sub_url,
                user_id=user_id,
                last_payment_method=last_payment_method,
            )
            return

        base = sub["expires_at"] if sub["expires_at"] > now else now
        new_exp = base + timedelta(days=self.settings.plan_days)
        client_uuid = str(sub["client_uuid"])
        client_email = sub["client_email"]
        await self.xui.update_client(
            self.settings.xui_inbound_id,
            client_uuid,
            client_email,
            new_exp,
            limit_ip=self.settings.max_devices_per_sub,
        )

        vless_url = build_vless_url(
            uuid=client_uuid,
            host=self.settings.vpn_public_host,
            port=self.settings.vpn_public_port or inbound_port,
            tag=self.settings.vpn_tag,
            public_key=reality.public_key,
            short_id=reality.short_id,
            sni=reality.sni,
            fingerprint=reality.fingerprint,
        )
        await self.db.extend_subscription(sub["id"], new_exp, vless_url)
        sub_id = await self.xui.get_client_sub_id(self.settings.xui_inbound_id, client_uuid)
        sub_url = (
            f"https://{self.settings.vpn_public_host}:{self.settings.xui_sub_port}/sub/{sub_id}"
            if sub_id
            else None
        )
        last_payment_method = await self.db.get_latest_payment_method(user_id)
        await self._send_config(
            update,
            vless_url,
            new_exp,
            sub_url,
            user_id=user_id,
            last_payment_method=last_payment_method,
        )

    async def _send_config(
        self,
        update: Update | None,
        vless_url: str,
        expires_at: datetime,
        subscription_url: str | None = None,
        client_code: str | None = None,
        user_id: int | None = None,
        last_payment_method: str | None = None,
        message: Message | None = None,
    ) -> None:
        if message is None and update is not None:
            message = update.message or (update.callback_query.message if update.callback_query else None)
        if message is None:
            return
        action_markup: InlineKeyboardMarkup | None = None
        link_for_copy = subscription_url or vless_url
        qr_payload = subscription_url or vless_url
        qr_title = "Subscription QR" if subscription_url else "Direct VLESS QR"

        account_url = await self._account_url(user_id)

        buttons: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton(
                    text=self._button_label("config_button", "⚙️ Конфиг"),
                    url=self._open_app_url(vless_url),
                ),
                InlineKeyboardButton(
                    text="\U0001f4cb \u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443",
                    api_kwargs={"copy_text": {"text": link_for_copy}},
                ),
            ],
        ]
        buttons.append(
            [
                InlineKeyboardButton(
                    text=self._button_label("pay_card_button", "💳 Оплатить картой"),
                    url=f"{self._site_url().rstrip('/')}/account/renew/",
                )
            ]
        )
        if subscription_url:
            buttons.insert(0, [InlineKeyboardButton(text="\U0001f517 \u041e\u0442\u043a\u0440\u044b\u0442\u044c \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0443", url=subscription_url)])
        buttons.append(
            [
                InlineKeyboardButton(
                    text=self._button_label("open_instructions", "📘 Инструкция"),
                    callback_data="nav|menu_instructions|_",
                )
            ]
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text=self._button_label("open_account", "\U0001f464 \u041b\u0438\u0447\u043d\u044b\u0439 \u043a\u0430\u0431\u0438\u043d\u0435\u0442 \u043d\u0430 VXcloud"),
                    url=account_url,
                )
            ]
        )
        action_markup = InlineKeyboardMarkup(buttons)

        qr_img = self._build_styled_qr(qr_payload, qr_title)
        qr_buff = io.BytesIO()
        qr_img.save(qr_buff, format="PNG")
        qr_buff.seek(0)

        resolved_client_code = client_code or (f"VX-{user_id}" if user_id is not None else "")
        text = self._content_text(
            "menu_mysub_response",
            "\u041f\u043e\u0434\u043f\u0438\u0441\u043a\u0430 \u0430\u043a\u0442\u0438\u0432\u043d\u0430 \u0434\u043e: {expires_at}\nClient code: {client_code}",
        )
        text = (
            text.replace("{expires_at}", self._format_local_dt(expires_at))
            .replace("{client_code}", resolved_client_code)
            .replace("{payment_method}", self._format_payment_method(last_payment_method))
            .replace("{subscription_url}", subscription_url or "")
            .replace("{vless_url}", vless_url)
            .replace("{user_id}", str(user_id) if user_id is not None else "")
        )
        if "Способ оплаты:" not in text:
            text += f"\nСпособ оплаты: {self._format_payment_method(last_payment_method)}"
        if subscription_url:
            text += f"\n\n\u0421\u0441\u044b\u043b\u043a\u0430 \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0438:\n{subscription_url}"
        copy_link_hint = self._content_text(
            "copy_link_hint",
            "Нажмите «Скопировать ссылку», затем откройте Streisand, нажмите + и выберите Import from Clipboard.",
        ).replace("\\n", "\n").replace("/n", "\n")
        single_device_warning = self._content_text(
            "single_device_warning",
            "⚠️ Один конфиг нельзя использовать одновременно на двух устройствах.",
        ).replace("\\n", "\n").replace("/n", "\n")
        text += "\n\n" + copy_link_hint
        text += "\n\n" + single_device_warning

        await message.reply_photo(photo=qr_buff)
        await message.reply_text(text, reply_markup=action_markup)

    @staticmethod
    def _build_styled_qr(data: str, title: str) -> Image.Image:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=1,
            border=1,
        )
        qr.add_data(data)
        qr.make(fit=True)
        modules = max(1, qr.modules_count)
        # Keep QR sharp and close to bottom-button width by sizing modules before render.
        target_width_px = 320
        qr.box_size = max(3, min(8, target_width_px // (modules + 2)))
        return qr.make_image(fill_color="#111111", back_color="white").convert("RGB")

    @staticmethod
    def _extract_email_and_ip_from_access_line(line: str) -> tuple[str, str] | None:
        line_lower = line.lower()
        if "from " not in line_lower:
            return None
        from_match = re.search(r"\bfrom\s+((?:\d{1,3}\.){3}\d{1,3})", line, re.IGNORECASE)
        if not from_match:
            return None
        ip = from_match.group(1)
        email_match = EMAIL_RE.search(line)
        email = email_match.group(1).strip() if email_match else ""
        if not email:
            for candidate in BRACKET_RE.findall(line):
                if "." in candidate or ":" in candidate:
                    continue
                if len(candidate) < 3:
                    continue
                email = candidate.strip()
                break
        if not email:
            return None
        return email, ip

    def _read_new_xray_access_lines(self) -> list[str]:
        path = self.settings.xray_access_log_path
        try:
            if not os.path.exists(path):
                return []
            size = os.path.getsize(path)
            if self._xray_log_offset > size:
                self._xray_log_offset = 0
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                fh.seek(self._xray_log_offset)
                lines = fh.readlines()
                self._xray_log_offset = fh.tell()
            return lines
        except Exception:
            LOGGER.exception("Failed to read xray access log: %s", path)
            return []

    async def single_ip_tick(self) -> None:
        if not self.settings.enforce_single_ip:
            return

        now = time.time()
        lines = await asyncio.to_thread(self._read_new_xray_access_lines)

        for line in lines:
            parsed = self._extract_email_and_ip_from_access_line(line)
            if not parsed:
                continue
            email, ip = parsed
            email_map = self._recent_email_ips.setdefault(email, {})
            email_map[ip] = now

        window = max(15, self.settings.single_ip_window_seconds)
        cutoff = now - window
        stale_emails: list[str] = []
        for email, ip_map in self._recent_email_ips.items():
            stale_ips = [ip for ip, ts in ip_map.items() if ts < cutoff]
            for ip in stale_ips:
                ip_map.pop(ip, None)
            if not ip_map:
                stale_emails.append(email)
        for email in stale_emails:
            self._recent_email_ips.pop(email, None)
            self._single_ip_notified_blocked.discard(email)

        active_subs = await self.db.list_active_subscriptions()
        block_seconds = max(30, self.settings.single_ip_block_seconds)

        for sub in active_subs:
            email = str(sub["client_email"])
            client_uuid = str(sub["client_uuid"])
            inbound_id = int(sub["inbound_id"])
            expires_at = sub["expires_at"]
            assert isinstance(expires_at, datetime)
            ip_count = len(self._recent_email_ips.get(email, {}))
            blocked_until = self._single_ip_block_until.get(email, 0.0)

            if blocked_until > now:
                # Keep disabled during penalty window.
                await self.xui.set_client_enabled(
                    inbound_id,
                    client_uuid,
                    email,
                    expires_at,
                    enable=False,
                    limit_ip=self.settings.max_devices_per_sub,
                )
                continue

            if ip_count > 1:
                self._single_ip_block_until[email] = now + block_seconds
                await self.xui.set_client_enabled(
                    inbound_id,
                    client_uuid,
                    email,
                    expires_at,
                    enable=False,
                    limit_ip=self.settings.max_devices_per_sub,
                )
                if email not in self._single_ip_notified_blocked:
                    self._single_ip_notified_blocked.add(email)
                    user_id = int(sub["user_id"])
                    tg_id = await self.db.get_user_telegram_id(user_id)
                    if tg_id:
                        try:
                            await self.app.bot.send_message(
                                chat_id=tg_id,
                                text=(
                                    "Обнаружено одновременное подключение с нескольких IP. "
                                    f"Доступ временно приостановлен на {block_seconds} сек."
                                ),
                            )
                        except Exception:
                            LOGGER.exception("Failed to notify user about single-ip block (user_id=%s)", user_id)
                continue

            if blocked_until and blocked_until <= now:
                self._single_ip_block_until.pop(email, None)
                self._single_ip_notified_blocked.discard(email)
                await self.xui.set_client_enabled(
                    inbound_id,
                    client_uuid,
                    email,
                    expires_at,
                    enable=True,
                    limit_ip=self.settings.max_devices_per_sub,
                )

    async def reminder_tick(self) -> None:
        items = await self.db.due_reminders()
        now = datetime.now(timezone.utc)
        for item in items:
            expires_at = item["expires_at"]
            tg_id = int(item["telegram_id"])
            sub_id = int(item["id"])
            if expires_at <= now:
                msg = "Ð’Ð°ÑˆÐ° Ð¿Ð¾Ð´Ð¿Ð¸ÑÐºÐ° VXcloud Ð¸ÑÑ‚ÐµÐºÐ»Ð°. Ð˜ÑÐ¿Ð¾Ð»ÑŒÐ·ÑƒÐ¹Ñ‚Ðµ /buy Ð´Ð»Ñ Ð¿Ñ€Ð¾Ð´Ð»ÐµÐ½Ð¸Ñ."
                tag = "expired"
            elif expires_at <= now + timedelta(days=1):
                msg = f"ÐÐ°Ð¿Ð¾Ð¼Ð¸Ð½Ð°Ð½Ð¸Ðµ: Ð¿Ð¾Ð´Ð¿Ð¸ÑÐºÐ° VXcloud Ð¸ÑÑ‚ÐµÐºÐ°ÐµÑ‚ Ð¼ÐµÐ½ÐµÐµ Ñ‡ÐµÐ¼ Ñ‡ÐµÑ€ÐµÐ· 24 Ñ‡Ð°ÑÐ° ({self._format_local_dt(expires_at)})."
                tag = "1d"
            else:
                msg = f"ÐÐ°Ð¿Ð¾Ð¼Ð¸Ð½Ð°Ð½Ð¸Ðµ: Ð¿Ð¾Ð´Ð¿Ð¸ÑÐºÐ° VXcloud Ð¸ÑÑ‚ÐµÐºÐ°ÐµÑ‚ Ð¼ÐµÐ½ÐµÐµ Ñ‡ÐµÐ¼ Ñ‡ÐµÑ€ÐµÐ· 3 Ð´Ð½Ñ ({self._format_local_dt(expires_at)})."
                tag = "3d"

            try:
                await self.app.bot.send_message(chat_id=tg_id, text=msg)
                await self.db.log_reminder(sub_id, tag)
            except Exception:
                LOGGER.exception("Failed to send reminder to telegram_id=%s", tg_id)
