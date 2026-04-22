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
from urllib.parse import parse_qsl
from urllib.parse import quote
from urllib.parse import urlencode
from urllib.parse import urlsplit
from urllib.parse import urlunsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import qrcode
from PIL import Image
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, LabeledPrice, Message, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from .cluster.provisioner import create_client_on_node
from .cluster.rebalance import pick_best_node
from .config import Settings
from .client_naming import build_xui_client_name
from .cms import DirectusCMS
from .db import DB
from .dns_alias import ensure_subscription_alias_record, generate_subscription_alias
from .domain.subscriptions import activate_subscription
from .subscription_links import build_bot_feed_url, build_subscription_vless_url
from .vless import build_vless_url
from .xui_client import InboundRealityInfo, XUIClient


LOGGER = logging.getLogger(__name__)
STREISAND_APPSTORE_URL = "https://apps.apple.com/us/app/streisand/id6450534064"
V2BOX_PLAYSTORE_URL = "https://play.google.com/store/search?q=V2Box&c=apps"
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
EMAIL_RE = re.compile(r"(?:email|user)[:=]\s*([^\s,\]]+)", re.IGNORECASE)
BRACKET_RE = re.compile(r"\[([^\[\]\s]+)\]")


def _node_reality_info(node: dict[str, object]) -> InboundRealityInfo | None:
    public_key = str(node.get("last_reality_public_key") or "").strip()
    short_id = str(node.get("last_reality_short_id") or "").strip()
    sni = str(node.get("last_reality_sni") or "").strip()
    fingerprint = str(node.get("last_reality_fingerprint") or "chrome").strip() or "chrome"
    if not (public_key and short_id and sni):
        return None
    return InboundRealityInfo(
        public_key=public_key,
        short_id=short_id,
        sni=sni,
        fingerprint=fingerprint,
    )


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
            row.append(KeyboardButton(label))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        return ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)

    def _content_text(self, key: str, default: str) -> str:
        value = self._cms_content.get(key)
        if not value:
            return default
        normalized = value.strip()
        if not normalized:
            return default
        # Guard against mojibake/placeholder content like "?????"
        if normalized.count("?") >= max(4, len(normalized) // 4):
            return default
        return value

    def _button_label(self, key: str, default: str) -> str:
        value = self._cms_buttons.get(key)
        if not value:
            return default
        normalized = value.strip()
        if not normalized:
            return default
        if normalized.count("?") >= max(2, len(normalized) // 3):
            return default
        return value

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
            return "звёзды Telegram"
        return normalized

    def _card_price_label(self) -> str:
        value = int(self.settings.card_payment_amount_minor or 0)
        major = value // 100
        minor = value % 100
        amount = f"{major}" if minor == 0 else f"{major}.{minor:02d}"
        currency = (self.settings.card_payment_currency or "RUB").upper()
        return f"{amount} {currency}"

    def _with_card_price(self, label: str) -> str:
        normalized = label.lower()
        if "rub" in normalized or "₽" in label:
            return label
        return f"{label} · {self._card_price_label()}"

    def _menu_buttons(self, has_active_subscription: bool = False) -> list[tuple[str, str]]:
        buttons: list[tuple[str, str]] = [
            ("menu_trial", self._button_label("menu_trial", "\U0001f381 \u0411\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e 7\u0434").strip() or "\U0001f381 \u0411\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e 7\u0434"),
            ("menu_buy", self._button_label("menu_buy", "⭐ Купить новый доступ").strip() or "⭐ Купить новый доступ"),
            ("menu_mysub", self._button_label("menu_mysub", "\U0001f4ca \u041c\u043e\u0439 \u0434\u043e\u0441\u0442\u0443\u043f").strip() or "\U0001f4ca \u041c\u043e\u0439 \u0434\u043e\u0441\u0442\u0443\u043f"),
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
                self._button_label("menu_site", "🌐 Личный кабинет на сайте").strip() or "🌐 Личный кабинет на сайте",
            ),
        ]
        if has_active_subscription:
            buttons.insert(2, ("menu_renew", self._button_label("menu_renew", "🔄 Продлить").strip() or "🔄 Продлить"))
        return buttons

    def _site_url(self) -> str:
        return self._content_text("site_url", "https://vxcloud.ru").strip() or "https://vxcloud.ru"

    def _account_fallback_url(self) -> str:
        return f"{self._site_url().rstrip('/')}/account/"

    async def _subscription_feed_url(self, subscription_id: int, feed_token: str | None = None) -> str | None:
        token = (feed_token or "").strip()
        if not token:
            token = (await self.db.ensure_subscription_feed_token(int(subscription_id)) or "").strip()
        if not token:
            return None
        return build_bot_feed_url(site_url=self._site_url(), feed_token=token)

    @staticmethod
    def _append_next_param(url: str, next_path: str | None) -> str:
        next_value = (next_path or "").strip()
        if not next_value:
            return url
        split = urlsplit(url)
        params = [(key, value) for key, value in parse_qsl(split.query, keep_blank_values=True) if key != "next"]
        params.append(("next", next_value))
        return urlunsplit((split.scheme, split.netloc, split.path, urlencode(params), split.fragment))

    async def _account_url(self, user_id: int | None, next_path: str | None = None) -> str:
        explicit = self._content_text("account_page_url", "").strip()
        if explicit:
            return self._append_next_param(explicit, next_path)
        site_url = self._site_url().rstrip("/")
        fallback = self._account_fallback_url()
        if user_id is None:
            return self._append_next_param(fallback, next_path)

        shared_secret = (self.settings.magic_link_shared_secret or "").strip()
        if not shared_secret:
            return self._append_next_param(fallback, next_path)

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
            return self._append_next_param(magic_url or fallback, next_path)
        except Exception:
            LOGGER.exception("Failed to generate magic link for user_id=%s", user_id)
            return self._append_next_param(fallback, next_path)

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
                "Как подключиться\n\n"
                "Чтобы всё заработало, нужно сделать два шага:\n\n"
                "1. Установить приложение\n"
                "2. Оплатить доступ\n\n"
                "Мы покажем всё по шагам ниже."
            )
            return self._content_text(response_key, self._content_text(legacy_key, default))
        if node_key == "instructions_install":
            default = (
                "Как установить приложение\n\n"
                "Если вы используете iPhone в России, нужного приложения может не быть в App Store.\n\n"
                "Это нормально — просто нужно временно сменить регион.\n\n"
                "Сначала:\n"
                "• смените регион App Store (на любую другую страну)\n\n"
                "Затем:\n"
                "• установите приложение для подключения\n\n"
                "После установки:\n"
                "• можно вернуть регион обратно на Россию\n\n"
                "Ниже есть подробная инструкция и видео — мы покажем всё по шагам."
            )
            return self._content_text(response_key, self._content_text(legacy_key, default))
        if node_key == "site_about":
            default = (
                "Что можно делать на сайте\n\n"
                "В личном кабинете вы можете:\n\n"
                "• увидеть все свои устройства\n"
                "• открыть доступ для подключения\n"
                "• показать QR-код\n"
                "• оплатить новый доступ или продление картой\n"
                "• открыть подробные инструкции и видео\n\n"
                "Сайт и бот работают вместе — ваши данные будут одинаковыми везде."
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
        if node_key == "menu_instructions":
            return InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=self._button_label("instructions_install_button", "📱 Установить приложение"),
                            callback_data="nav|instructions_install|menu_instructions",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=self._button_label("instructions_access_button", "📊 Мой доступ"),
                            callback_data="act|start_mysub|_",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text=self._button_label("instructions_support_button", "🆘 Поддержка"),
                            callback_data="act|support_hub|_",
                        )
                    ],
                ]
            )
        if node_key == "instructions_install":
            install_help_url = "https://vxcloud.ru/2026/04/06/kak-podklyuchitsya-k-vpn-vxcloud-polnyj-poshagovyj-gajd/"
            return InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton(text=self._button_label("instructions_full_guide_button", "📖 Подробная инструкция"), url=install_help_url)],
                    [InlineKeyboardButton(text=self._button_label("instructions_video_button", "🎬 Видео-инструкция"), url=install_help_url)],
                    [InlineKeyboardButton(text=self._button_label("back_button", "⬅️ Назад"), callback_data="nav|menu_instructions|_")],
                ]
            )
        raw = self._cms_content.get(f"{node_key}_buttons")
        if not raw:
            if node_key == "menu_instructions":
                return InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton(text="🍏 Айфон", url=STREISAND_APPSTORE_URL)],
                        [InlineKeyboardButton(text="🤖 Андроид", url=V2BOX_PLAYSTORE_URL)],
                        [InlineKeyboardButton(text="🌐 Личный кабинет на сайте", url=self._account_fallback_url())],
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
            rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"nav|{parent_key}|_")])

        if not rows:
            return None
        return InlineKeyboardMarkup(rows)

    def _start_inline_keyboard(self, account_url: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text="🎁 Попробовать 7 дней", callback_data="act|start_trial|_"),
                    InlineKeyboardButton(text="⭐ Купить новый доступ", callback_data="act|buy_new|_"),
                ],
                [
                    InlineKeyboardButton(text="💬 Как подключить", callback_data="nav|menu_instructions|_"),
                    InlineKeyboardButton(text="🌐 Личный кабинет на сайте", url=account_url),
                ],
            ]
        )

    async def _replace_or_reply(
        self,
        message: Message,
        text: str,
        *,
        reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | None = None,
    ) -> None:
        try:
            await message.edit_text(text=text, reply_markup=reply_markup)
        except Exception:
            await message.reply_text(text, reply_markup=reply_markup)

    @staticmethod
    def _start_message_text() -> str:
        return (
            "Добро пожаловать в VXcloud\n\n"
            "Здесь можно быстро получить доступ к VPN для работы, общения и повседневных задач.\n\n"
            "Что дальше:\n"
            "• попробуйте 7 дней бесплатно\n"
            "• купите новый доступ\n"
            "• откройте личный кабинет на сайте\n\n"
            "Если для подключения нужно приложение, нажмите «Как подключить»."
        )

    async def _send_start_screen(self, message: Message, user_id: int) -> None:
        await self._menu_keyboard_for_user(user_id)
        account_url = await self._account_url(user_id)
        await self._replace_or_reply(
            message,
            self._start_message_text(),
            reply_markup=self._start_inline_keyboard(account_url),
        )

    def _trial_offer_markup(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text="🎁 Активировать 7 дней", callback_data="act|trial_activate|_")],
                [
                    InlineKeyboardButton(text="💬 Как это работает", callback_data="nav|menu_instructions|_"),
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="act|start_back|_"),
                ],
            ]
        )

    def _trial_used_markup(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text="⭐ Купить новый доступ", callback_data="act|buy_new|_")],
                [
                    InlineKeyboardButton(text="💬 Как подключить", callback_data="nav|menu_instructions|_"),
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="act|start_back|_"),
                ],
            ]
        )

    def _trial_success_markup(self, subscription_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text="🚀 Открыть", callback_data=f"act|cfg_open:{subscription_id}|_"),
                    InlineKeyboardButton(text="📷 QR-код", callback_data=f"act|cfg_qr:{subscription_id}|_"),
                ],
                [
                    InlineKeyboardButton(text="💬 Инструкция", callback_data="nav|menu_instructions|_"),
                    InlineKeyboardButton(text="📊 Мой доступ", callback_data="act|start_mysub|_"),
                ],
            ]
        )

    async def _buy_offer_markup(self, user_id: int | None) -> InlineKeyboardMarkup:
        pay_url = await self._account_url(user_id, "/account/buy/")
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text=self._with_card_price("💳 Оплатить картой"), url=pay_url)],
                [InlineKeyboardButton(text="⭐ Оплатить через Stars", callback_data="act|buy_stars_continue|_")],
                [
                    InlineKeyboardButton(text="💬 Как подключить", callback_data="nav|menu_instructions|_"),
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="act|start_back|_"),
                ],
            ]
        )

    def _buy_card_markup(self, pay_url: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text=self._with_card_price("💳 Перейти к оплате"), url=pay_url)],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="act|buy_card_back|_")],
            ]
        )

    def _renew_card_markup(self, pay_url: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text=self._with_card_price("💳 Перейти к оплате"), url=pay_url)],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="act|renew_card_back|_")],
            ]
        )

    def _post_payment_ready_markup(self, subscription_id: int, account_url: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text="🚀 Открыть", callback_data=f"act|cfg_open:{subscription_id}|_"),
                    InlineKeyboardButton(text="📷 QR-код", callback_data=f"act|cfg_qr:{subscription_id}|_"),
                ],
                [
                    InlineKeyboardButton(text="📊 Мой доступ", callback_data="act|start_mysub|_"),
                    InlineKeyboardButton(text="🌐 Личный кабинет на сайте", url=account_url),
                ],
            ]
        )

    async def _renew_offer_markup(self, user_id: int | None, subscription_id: int | None = None) -> InlineKeyboardMarkup:
        next_path = "/account/renew/"
        if isinstance(subscription_id, int) and subscription_id > 0:
            next_path = f"{next_path}?subscription_id={subscription_id}"
        pay_url = await self._account_url(user_id, next_path)
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text=self._with_card_price("💳 Продлить картой"), url=pay_url)],
                [InlineKeyboardButton(text="⭐ Продлить через Stars", callback_data="act|renew_stars_continue|_")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="act|renew_back|_")],
            ]
        )

    def _buy_existing_access_markup(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text="🔄 Продлить текущий доступ", callback_data="act|buy_existing_renew|_")],
                [InlineKeyboardButton(text="➕ Купить дополнительный доступ", callback_data="act|buy_existing_continue|_")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="act|start_back|_")],
            ]
        )

    def _support_hub_markup(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text="✍️ Написать в поддержку", callback_data="act|support_start|_")],
                [
                    InlineKeyboardButton(text="📦 Моя подписка", callback_data="act|start_mysub|_"),
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="act|start_back|_"),
                ],
            ]
        )

    def _support_sent_markup(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text="📦 Моя подписка", callback_data="act|start_mysub|_")],
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="act|start_back|_")],
            ]
        )

    async def _show_support_hub(self, message: Message, user_id: int) -> None:
        client_code = await self.db.get_user_client_code(user_id) or f"VX-{user_id:06d}"
        await self._replace_or_reply(
            message,
            "Поддержка VXcloud\n\n"
            "Если что-то не работает или возник вопрос, напишите нам одним сообщением.\n\n"
            "Лучше сразу указать:\n"
            "• что именно не получается\n"
            "• на каком устройстве\n"
            "• что уже пробовали\n\n"
            "Ваш ID:\n"
            f"{client_code}",
            reply_markup=self._support_hub_markup(),
        )

    def _renew_no_active_markup(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text="⭐ Купить новый доступ", callback_data="act|buy_new|_")],
                [
                    InlineKeyboardButton(text="🎁 Бесплатно 7д", callback_data="act|start_trial|_"),
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="act|renew_back|_"),
                ],
            ]
        )

    def _renew_success_markup(self, subscription_id: int, account_url: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text="🚀 Открыть", callback_data=f"act|cfg_open:{subscription_id}|_"),
                    InlineKeyboardButton(text="📷 QR-код", callback_data=f"act|cfg_qr:{subscription_id}|_"),
                ],
                [
                    InlineKeyboardButton(text="📊 Мой доступ", callback_data="act|start_mysub|_"),
                    InlineKeyboardButton(text="🌐 Личный кабинет на сайте", url=account_url),
                ],
            ]
        )

    async def _resolve_renew_target(
        self, user_id: int, context: ContextTypes.DEFAULT_TYPE
    ) -> tuple[int | None, dict[str, object] | None]:
        selected_id = context.user_data.get("selected_subscription_id")
        if isinstance(selected_id, str) and selected_id.isdigit():
            selected_id = int(selected_id)
        if isinstance(selected_id, int):
            selected_sub = await self.db.get_subscription(user_id, selected_id)
            if selected_sub:
                return selected_id, selected_sub

        active_sub = await self.db.get_active_subscription(user_id)
        if not active_sub:
            return None, None
        target_id = int(active_sub["id"])
        context.user_data["selected_subscription_id"] = target_id
        return target_id, active_sub

    async def _show_renew_offer(
        self,
        message: Message,
        user_id: int,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        target_subscription_id, target_sub = await self._resolve_renew_target(user_id, context)
        if not target_subscription_id or not target_sub:
            await message.reply_text(
                "Сейчас у вас нет активного доступа для продления.\n\n"
                "Вы можете оформить новый доступ.",
                reply_markup=self._renew_no_active_markup(),
            )
            return

        expires_at = target_sub.get("expires_at")
        expires_text = self._format_local_dt(expires_at) if isinstance(expires_at, datetime) else "—"
        await self._replace_or_reply(
            message,
            "Продление доступа\n\n"
            f"Текущее устройство: {self._subscription_name(target_sub)}\n"
            f"Действует до: {expires_text}\n\n"
            f"Рекомендуем оплату картой на сайте · {self._card_price_label()}.\n"
            "После оплаты срок доступа продлится автоматически.",
            reply_markup=await self._renew_offer_markup(user_id, target_subscription_id),
        )

    async def _show_renew_card_info(self, message: Message) -> None:
        pay_url = await self._account_url(None, "/account/renew/")
        await message.edit_reply_markup(reply_markup=self._renew_card_markup(pay_url))

    async def _show_buy_checkout_options(self, message: Message, user_id: int | None = None) -> None:
        await self._replace_or_reply(
            message,
            "Оформление доступа\n\n"
            f"Рекомендуем оплату картой на сайте · {self._card_price_label()}.\n\n"
            "Подходит, если вы хотите:\n"
            "• подключить ещё одно устройство\n"
            "• получить отдельный доступ\n"
            "• купить доступ после пробного периода\n\n"
            "После оплаты вы сразу получите ссылку для подключения и QR-код.",
            reply_markup=await self._buy_offer_markup(user_id),
        )

    async def _show_buy_offer(self, message: Message, user_id: int) -> None:
        active_sub = await self.db.get_active_subscription(user_id)
        if active_sub:
            await self._replace_or_reply(
                message,
                "У вас уже есть активный доступ.\n\n"
                "Что хотите сделать дальше?\n"
                "• продлить текущий доступ\n"
                "• купить дополнительный доступ",
                reply_markup=self._buy_existing_access_markup(),
            )
            return
        await self._show_buy_checkout_options(message, user_id)

    async def _show_buy_card_info(self, message: Message) -> None:
        pay_url = await self._account_url(None, "/account/buy/")
        await message.edit_reply_markup(reply_markup=self._buy_card_markup(pay_url))

    async def _show_trial_offer(self, message: Message, user_id: int) -> None:
        if await self.db.has_any_subscription(user_id):
            await message.reply_text(
                "Пробный доступ уже был использован\n\n"
                "Вы можете сразу оформить платный доступ.",
                reply_markup=self._trial_used_markup(),
            )
            return

        await self._replace_or_reply(
            message,
            "Пробный доступ на 7 дней\n\n"
            "Подходит, если хотите сначала всё проверить.\n\n"
            "Что получите:\n"
            "• доступ на 7 дней\n"
            "• ссылку для подключения\n"
            "• QR-код\n"
            "• пошаговую инструкцию\n\n"
            "Пробный период можно активировать один раз.",
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
                        "Найден оплаченный заказ. Пробую восстановить доступ...",
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
                            "Не удалось автоматически восстановить доступ. Поддержка уже уведомлена, пожалуйста подождите.",
                        )
                    )
                    if self.settings.telegram_admin_id:
                        try:
                            await self.app.bot.send_message(
                                chat_id=self.settings.telegram_admin_id,
                                text=(
                                    "⚠️ Ошибка восстановления доступа.\n"
                                    f"user_id={user_id} paid_order_id={paid_order.get('id')}"
                                ),
                            )
                        except Exception:
                            LOGGER.exception("Failed to notify admin about recovery issue")
                    return
        client_code = await self.db.get_user_client_code(user_id) or f"VX-{user_id:06d}"
        text = self._configs_list_text(client_code=client_code, subscriptions=subscriptions)
        if subscriptions:
            text = f"{text}\n\nНажмите на устройство ниже, чтобы открыть его."
        await self._replace_or_reply(
            message,
            text,
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
        now = time.monotonic()
        ttl = max(self.settings.cms_cache_ttl_seconds, 5)
        if not force and (now - self._cms_loaded_at) < ttl:
            return

        async with self._cms_lock:
            if not force and (time.monotonic() - self._cms_loaded_at) < ttl:
                return
            content: dict[str, str] = {}
            buttons: dict[str, str] = {}
            try:
                if self.cms is not None:
                    content = await self.cms.fetch_content()
                    buttons = await self.cms.fetch_buttons()
            except Exception:
                LOGGER.exception("Failed to refresh CMS content")
            try:
                overrides = await self.db.fetch_bot_site_text_overrides()
            except Exception:
                LOGGER.exception("Failed to refresh bot text overrides from DB")
                overrides = {}

            self._cms_content = dict(content)
            self._cms_buttons = dict(buttons)
            for key, value in overrides.items():
                self._cms_content[key] = value
                self._cms_buttons[key] = value
            self._cms_loaded_at = time.monotonic()

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

    async def _build_client_email(self, user_id: int, client_uuid: str, *, prefix: str = "") -> str:
        user_identity = await self.db.get_user_identity(user_id)
        return build_xui_client_name(
            user_id=user_id,
            client_uuid=client_uuid,
            username=(user_identity or {}).get("username"),
            first_name=(user_identity or {}).get("first_name"),
            client_code=(user_identity or {}).get("client_code"),
            prefix=prefix,
        )

    @staticmethod
    def _subscription_name(sub: dict[str, object]) -> str:
        display_name = str(sub.get("display_name") or "").strip()
        if display_name:
            return display_name
        client_email = str(sub.get("client_email") or "").strip()
        if client_email:
            return client_email
        return f"Устройство #{sub.get('id')}"

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

    @staticmethod
    def _subscription_can_delete(sub: dict[str, object], now: datetime | None = None) -> bool:
        current_time = now or datetime.now(timezone.utc)
        if sub.get("revoked_at") is not None:
            return True
        expires_at = sub.get("expires_at")
        if not isinstance(expires_at, datetime):
            return not bool(sub.get("is_active"))
        return not bool(sub.get("is_active") and expires_at > current_time)

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
        del user_id
        vless_url = str(sub.get("vless_url") or "").strip()
        feed_url = await self._subscription_feed_url(
            int(sub["id"]),
            str(sub.get("feed_token") or ""),
        )
        return vless_url, feed_url

    def _configs_list_text(
        self,
        *,
        client_code: str,
        subscriptions: list[dict[str, object]],
    ) -> str:
        now = datetime.now(timezone.utc)
        item_template = self._content_text(
            "my_configs_item_template",
            "{index}. {name}\nДействует до: {expires_at}\nСтатус: {status}",
        )
        items: list[str] = []
        if not subscriptions:
            return self._content_text(
                "my_configs_empty_message",
                "Ваш доступ VXcloud\n\nID: {client_code}\n\nВаши устройства:\n\nСписок устройств пока пуст.",
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
            "Ваш доступ VXcloud\n\nID: {client_code}\n\nВаши устройства:\n\n{items}",
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
                    text=self._button_label("buy_new_config_button", "⭐ Купить новый доступ"),
                    callback_data="act|buy_new|_",
                )
            ]
        )
        return InlineKeyboardMarkup(rows)

    async def _config_card_markup(
        self,
        user_id: int | None,
        subscription_id: int,
        copy_text: str,
        *,
        can_delete: bool,
    ) -> InlineKeyboardMarkup:
        renew_url = await self._account_url(user_id, f"/account/renew/?subscription_id={subscription_id}")
        rows = [
            [
                InlineKeyboardButton(
                    text=self._button_label("config_copy_button", "📋 Скопировать ссылку"),
                    api_kwargs={"copy_text": {"text": copy_text}},
                )
            ],
            [
                InlineKeyboardButton(text=self._button_label("config_qr_button", "📷 QR-код"), callback_data=f"act|cfg_qr:{subscription_id}|_"),
                InlineKeyboardButton(text=self._button_label("config_renew_button", "🔄 Продлить"), url=renew_url),
            ],
        ]
        action_row = [
            InlineKeyboardButton(text=self._button_label("config_rename_button", "✏️ Переименовать"), callback_data=f"act|cfg_rename:{subscription_id}|_"),
        ]
        if can_delete:
            action_row.append(
                InlineKeyboardButton(
                    text=self._button_label("config_delete_button", "🗑️ Удалить"),
                    callback_data=f"act|cfg_delete:{subscription_id}|_",
                )
            )
        rows.append(action_row)
        rows.append([InlineKeyboardButton(text=self._button_label("back_button", "⬅️ Назад"), callback_data="act|cfg_back|_")])
        return InlineKeyboardMarkup(rows)

    async def _config_card_text(self, user_id: int, sub: dict[str, object], *, client_code: str) -> tuple[str, str, str]:
        vless_url, feed_url = await self._resolve_subscription_links(user_id, sub)
        primary_link = feed_url or vless_url
        expires_at = sub.get("expires_at")
        expires_text = self._format_local_dt(expires_at) if isinstance(expires_at, datetime) else "—"
        status_text = self._subscription_status(sub, datetime.now(timezone.utc))
        text = (
            f"Устройство: {self._subscription_name(sub)}\n\n"
            f"ID: {client_code}\n\n"
            f"Статус: {status_text}\n"
            f"Действует до: {expires_text}\n"
            "\nОсновной способ: импортируйте подписку VXcloud."
        )
        if feed_url:
            text += f"\n\nПодписка: {feed_url}"
            text += "\nПосле импорта VXcloud сможет менять ноду без ручной замены конфига."
        if vless_url:
            text += f"\n\nRaw VLESS: {vless_url}"
        return text, primary_link, vless_url

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
                        "Готово! Telegram успешно привязан к вашему аккаунту на сайте.",
                    ),
                    reply_markup=await self._menu_keyboard_for_user(user_id),
                )
                return
            if status == "used":
                await update.message.reply_text(
                    self._content_text(
                        "link_used_message",
                        "Этот код уже использован. Сгенерируйте новый код на сайте.",
                    ),
                    reply_markup=await self._menu_keyboard_for_user(user_id),
                )
                return
            if status == "expired":
                await update.message.reply_text(
                    self._content_text(
                        "link_expired_message",
                        "Срок действия кода истёк. Сгенерируйте новый код на сайте.",
                    ),
                    reply_markup=await self._menu_keyboard_for_user(user_id),
                )
                return
            await update.message.reply_text(
                self._content_text(
                    "link_invalid_message",
                    "Неверный код привязки. Проверьте код и попробуйте снова.",
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
                    active_sub = await self.db.get_active_subscription(user_id)
                    status_text = "без активного доступа"
                    expiry_text = "—"
                    if active_sub:
                        status_text = "активен"
                        expires_at = active_sub.get("expires_at")
                        if isinstance(expires_at, datetime):
                            expiry_text = self._format_local_dt(expires_at)
                    if update.effective_user and update.effective_user.username:
                        username_text = f"@{update.effective_user.username}"
                    else:
                        username_text = "—"
                    header = self._content_text(
                        "support_admin_new_ticket_header",
                        "🆘 Новый тикет поддержки",
                    )
                    await self.app.bot.send_message(
                        chat_id=self.settings.telegram_admin_id,
                        text=(
                            f"{header}\n\n"
                            "[SUPPORT]\n\n"
                            f"ID: {client_code or '-'}\n"
                            f"Пользователь: {username_text}\n"
                            f"Статус: {status_text}\n"
                            f"Действует до: {expiry_text}\n\n"
                            "Сообщение:\n"
                            f"{text_value}"
                        ),
                    )
                except Exception:
                    LOGGER.exception("Failed to notify admin about support ticket_id=%s", ticket_id)

            await update.message.reply_text(
                self._content_text(
                    "support_received_message",
                    "Сообщение отправлено\n\nМы получили ваш запрос и ответим сюда в Telegram.\n\nВаш ID:\n{client_code}",
                )
                .replace("{ticket_id}", str(ticket_id))
                .replace("{client_code}", await self.db.get_user_client_code(user_id) or f"VX-{user_id:06d}"),
                reply_markup=self._support_sent_markup(),
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
                    "Не удалось определить устройство для переименования.",
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
                    "Не удалось переименовать устройство.",
                    reply_markup=menu_keyboard,
                )
                return
            await update.message.reply_text(
                f"Имя устройства обновлено: {new_name[:80]}",
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
        if selected_menu_key == "menu_support":
            await self._show_support_hub(update.message, user_id)
            return
        if selected_menu_key == "menu_site":
            account_url = await self._account_url(user_id)
            await update.message.reply_text(
                self._content_text(
                    "menu_site_response",
                    "Откройте личный кабинет на сайте.",
                ),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text=self._button_label("menu_site", "🌐 Личный кабинет на сайте"),
                                url=account_url,
                            )
                        ]
                    ]
                ),
            )
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
        message = update.message or (update.callback_query.message if update.callback_query else None)
        if message is None:
            return
        user_id = await self._ensure_user(update)
        await self._show_buy_offer(message, user_id)

    async def trial(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._refresh_cms()
        message = update.message or (update.callback_query.message if update.callback_query else None)
        if message is None:
            return
        user_id = await self._ensure_user(update)
        await self._show_trial_offer(message, user_id)

    async def renew(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = await self._ensure_user(update)
        message = update.message or (update.callback_query.message if update.callback_query else None)
        if message is None:
            return
        await self._show_renew_offer(message, user_id, context)

    async def admin_reload(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.cms is None:
            await update.message.reply_text("CMS не настроен.")
            return
        if not update.effective_user or update.effective_user.id != self.settings.telegram_admin_id:
            await update.message.reply_text("Доступ запрещён.")
            return
        await self._refresh_cms(force=True)
        await update.message.reply_text("Контент CMS обновлён.")

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
            await update.message.reply_text("Доступ запрещён.")
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
            await update.message.reply_text("Доступ запрещён.")
            return
        assert update.message is not None

        ticket_id = self._parse_ticket_id(context.args)
        if ticket_id is None:
            await update.message.reply_text("Использование: /ticket <id>")
            return

        ticket = await self.db.get_ticket_for_admin(ticket_id)
        if not ticket:
            await update.message.reply_text(f"Тикет #{ticket_id} не найден.")
            return

        messages = await self.db.list_ticket_messages(ticket_id=ticket_id, limit=10)
        header = (
            f"Тикет #{ticket_id}\n"
            f"Статус: {ticket.get('status')}\n"
            f"ID: {ticket.get('client_code') or '-'}"
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
            await update.message.reply_text("Доступ запрещён.")
            return
        assert update.message is not None

        ticket_id = self._parse_ticket_id(context.args)
        if ticket_id is None or len(context.args) < 2:
            await update.message.reply_text("Использование: /reply_ticket <id> <text>")
            return
        reply_text = " ".join(context.args[1:]).strip()
        if not reply_text:
            await update.message.reply_text("Использование: /reply_ticket <id> <text>")
            return

        ticket = await self.db.get_ticket_for_admin(ticket_id)
        if not ticket:
            await update.message.reply_text(f"Тикет #{ticket_id} не найден.")
            return
        if str(ticket.get("status") or "").lower() == "closed":
            await update.message.reply_text(f"Тикет #{ticket_id} уже закрыт.")
            return

        telegram_id = ticket.get("telegram_id")
        if telegram_id is None or int(telegram_id) <= 0:
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

        await update.message.reply_text(f"Ответ отправлен (тикет #{ticket_id}).")


    async def admin_close_ticket(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_admin(update):
            assert update.message is not None
            await update.message.reply_text("Доступ запрещён.")
            return
        assert update.message is not None

        ticket_id = self._parse_ticket_id(context.args)
        if ticket_id is None:
            await update.message.reply_text("Использование: /close <id>")
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
            await update.message.reply_text("Доступ запрещён.")
            return
        if not context.args or len(context.args) < 2:
            await update.message.reply_text("Использование: /reply <client_code> <text>")
            return

        client_code = context.args[0].strip()
        reply_text = " ".join(context.args[1:]).strip()
        if not client_code or not reply_text:
            await update.message.reply_text("Использование: /reply <client_code> <text>")
            return

        user = await self.db.get_user_by_client_code(client_code)
        if not user:
            await update.message.reply_text(f"Пользователь с ID {client_code} не найден.")
            return

        user_id = int(user["id"])
        telegram_id = int(user["telegram_id"])
        normalized_client_code = str(user.get("client_code") or client_code).upper()
        if telegram_id <= 0:
            await update.message.reply_text(
                f"Пользователь {normalized_client_code} ещё не привязал Telegram."
            )
            return

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
                f"Тикет #{ticket_id}: ответ сохранён, но не удалось доставить сообщение пользователю."
            )
            return

        await update.message.reply_text(
            f"Отправлено пользователю {normalized_client_code} (тикет #{ticket_id})."
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
            if target == "buy_new":
                await query.answer()
                if query.message is not None:
                    user_id = await self._ensure_user(update)
                    await self._show_buy_offer(query.message, user_id)
                return
            if target == "buy_existing_renew":
                await query.answer()
                if query.message is not None:
                    user_id = await self._ensure_user(update)
                    await self._show_renew_offer(query.message, user_id, context)
                return
            if target == "buy_existing_continue":
                await query.answer()
                if query.message is not None:
                    user_id = await self._ensure_user(update)
                    await self._show_buy_checkout_options(query.message, user_id)
                return
            if target == "buy_stars_info":
                await query.answer()
                if query.message is not None:
                    await self._start_buy_flow(update, context)
                return
            if target == "buy_stars_continue":
                await query.answer()
                if query.message is not None:
                    await self._start_buy_flow(update, context)
                return
            if target == "buy_card":
                await query.answer()
                if query.message is not None:
                    await self._show_buy_card_info(query.message)
                return
            if target == "buy_card_back":
                await query.answer()
                user_id = await self._ensure_user(update)
                await query.edit_message_reply_markup(reply_markup=await self._buy_offer_markup(user_id))
                return
            if target == "buy_back":
                await query.answer()
                if query.message is not None:
                    user_id = await self._ensure_user(update)
                    await self._show_buy_checkout_options(query.message, user_id)
                return
            if target == "renew_stars_info":
                await query.answer()
                if query.message is not None:
                    user_id = await self._ensure_user(update)
                    target_subscription_id, _ = await self._resolve_renew_target(user_id, context)
                    if not target_subscription_id:
                        await query.message.reply_text(
                            "Не удалось определить доступ для продления.",
                            reply_markup=self._renew_no_active_markup(),
                        )
                    else:
                        await self._send_stars_invoice_for_message(
                            query.message,
                            user_id=user_id,
                            mode="renew",
                            subscription_id=target_subscription_id,
                        )
                return
            if target == "renew_stars_continue":
                await query.answer()
                if query.message is not None:
                    user_id = await self._ensure_user(update)
                    target_subscription_id, _ = await self._resolve_renew_target(user_id, context)
                    if not target_subscription_id:
                        await self._show_renew_offer(query.message, user_id, context)
                        return
                    await self._send_stars_invoice_for_message(
                        query.message,
                        user_id=user_id,
                        mode="renew",
                        target_subscription_id=target_subscription_id,
                    )
                return
            if target == "renew_card":
                await query.answer()
                if query.message is not None:
                    await self._show_renew_card_info(query.message)
                return
            if target == "renew_card_back":
                await query.answer()
                user_id = await self._ensure_user(update)
                target_subscription_id, _ = await self._resolve_renew_target(user_id, context)
                await query.edit_message_reply_markup(reply_markup=await self._renew_offer_markup(user_id, target_subscription_id))
                return
            if target == "renew_back":
                await query.answer()
                if query.message is not None:
                    user_id = await self._ensure_user(update)
                    await self._send_start_screen(query.message, user_id)
                return
            if target == "trial_activate":
                if query.message is not None:
                    if context.user_data.get("trial_activating"):
                        await query.answer("Пробный доступ уже активируется…")
                        return
                    await query.answer()
                    user_id = await self._ensure_user(update)
                    if await self.db.has_any_subscription(user_id):
                        await query.message.reply_text(
                            "Пробный доступ уже был использован\n\n"
                            "Вы можете сразу оформить платный доступ.",
                            reply_markup=self._trial_used_markup(),
                        )
                    else:
                        context.user_data["trial_activating"] = True
                        try:
                            await query.message.reply_text(
                                "Активирую пробный доступ...",
                                reply_markup=await self._menu_keyboard_for_user(user_id),
                            )
                            await self._run_user_provision(
                                user_id,
                                lambda: self._create_trial_for_user(update, user_id=user_id, days=7),
                            )
                        finally:
                            context.user_data.pop("trial_activating", None)
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
            if target == "support_hub":
                await query.answer()
                if query.message is not None:
                    user_id = await self._ensure_user(update)
                    await self._show_support_hub(query.message, user_id)
                return
            if target == "support_start":
                context.user_data["support_wait_message"] = True
                await query.answer()
                if query.message is not None:
                    await query.message.reply_text(
                        self._content_text(
                            "support_start_message",
                            "Напишите сообщение одним сообщением в этот чат.\n\nМы получим его вместе с вашим ID и данными по доступу.",
                        )
                    )
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
                    await query.answer("Некорректное устройство", show_alert=True)
                    return
                sub = await self.db.get_subscription(user_id, subscription_id)
                if not sub:
                    await query.answer("Устройство не найдено", show_alert=True)
                    return
                context.user_data["selected_subscription_id"] = subscription_id
                client_code = await self.db.get_user_client_code(user_id) or f"VX-{user_id:06d}"
                text, vless_url, sub_url = await self._config_card_text(user_id, sub, client_code=client_code)
                await query.answer()
                await query.edit_message_text(
                    text=text,
                    reply_markup=await self._config_card_markup(
                        user_id,
                        subscription_id,
                        vless_url,
                        can_delete=self._subscription_can_delete(sub),
                    ),
                )
                return
            if target.startswith("cfg_copy:"):
                user_id = await self._ensure_user(update)
                try:
                    subscription_id = int(target.split(":", 1)[1])
                except (IndexError, ValueError):
                    await query.answer("Некорректное устройство", show_alert=True)
                    return
                sub = await self.db.get_subscription(user_id, subscription_id)
                if not sub:
                    await query.answer("Устройство не найдено", show_alert=True)
                    return
                client_code = await self.db.get_user_client_code(user_id) or f"VX-{user_id:06d}"
                text, vless_url, _ = await self._config_card_text(
                    user_id,
                    sub,
                    client_code=client_code,
                )
                await query.answer("Обновляю карточку")
                if query.message is not None:
                    await query.edit_message_text(
                        text=text,
                        reply_markup=await self._config_card_markup(
                            user_id,
                            subscription_id,
                            vless_url,
                            can_delete=self._subscription_can_delete(sub),
                        ),
                    )
                return
            if target.startswith("cfg_qr:"):
                user_id = await self._ensure_user(update)
                try:
                    subscription_id = int(target.split(":", 1)[1])
                except (IndexError, ValueError):
                    await query.answer("Некорректное устройство", show_alert=True)
                    return
                sub = await self.db.get_subscription(user_id, subscription_id)
                if not sub:
                    await query.answer("Устройство не найдено", show_alert=True)
                    return
                text, vless_url, sub_url = await self._config_card_text(
                    user_id,
                    sub,
                    client_code=(await self.db.get_user_client_code(user_id) or f"VX-{user_id:06d}"),
                )
                qr_payload = vless_url
                qr_img = self._build_styled_qr(qr_payload, "QR доступа")
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
                    await query.answer("Некорректное устройство", show_alert=True)
                    return
                sub = await self.db.get_subscription(user_id, subscription_id)
                if not sub:
                    await query.answer("Устройство не найдено", show_alert=True)
                    return
                context.user_data["selected_subscription_id"] = subscription_id
                client_code = await self.db.get_user_client_code(user_id) or f"VX-{user_id:06d}"
                text, vless_url, _ = await self._config_card_text(
                    user_id,
                    sub,
                    client_code=client_code,
                )
                await query.answer("Нажмите кнопку продления картой")
                if query.message is not None:
                    await query.edit_message_text(
                        text=text,
                        reply_markup=await self._config_card_markup(
                            user_id,
                            subscription_id,
                            vless_url,
                            can_delete=self._subscription_can_delete(sub),
                        ),
                    )
                return
            if target.startswith("cfg_rename:"):
                try:
                    subscription_id = int(target.split(":", 1)[1])
                except (IndexError, ValueError):
                    await query.answer("Некорректное устройство", show_alert=True)
                    return
                context.user_data["rename_wait_subscription_id"] = subscription_id
                await query.answer()
                if query.message is not None:
                    await query.message.reply_text("Отправьте новое имя устройства одним сообщением.")
                return
            if target.startswith("cfg_delete:"):
                user_id = await self._ensure_user(update)
                try:
                    subscription_id = int(target.split(":", 1)[1])
                except (IndexError, ValueError):
                    await query.answer("Некорректное устройство", show_alert=True)
                    return
                sub = await self.db.get_subscription(user_id, subscription_id)
                if not sub:
                    await query.answer("Устройство не найдено", show_alert=True)
                    return
                if not self._subscription_can_delete(sub):
                    await query.answer("Активный конфиг удалить нельзя", show_alert=True)
                    return
                deleted = False
                try:
                    delete_result = await self.xui.delete_client(
                        int(sub["inbound_id"]),
                        str(sub["client_uuid"]),
                        email=str(sub["client_email"]),
                        expiry=sub["expires_at"],
                        limit_ip=self.settings.max_devices_per_sub,
                        flow=self.settings.vpn_flow,
                    )
                    if delete_result != "deleted":
                        await query.answer("Не удалось удалить конфиг в 3x-ui", show_alert=True)
                        return
                except Exception:
                    LOGGER.exception("Failed to delete config in x-ui subscription_id=%s", subscription_id)
                    await query.answer("Не удалось удалить конфиг в 3x-ui", show_alert=True)
                    return

                deleted = await self.db.delete_subscription(user_id, subscription_id)
                await query.answer("Конфиг удален" if deleted else "Не удалось удалить конфиг")
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
                    await query.message.reply_text(f"Скопируйте ссылку доступа:\n{link}")
                else:
                    await query.message.reply_text("Ссылка устарела. Нажмите «📊 Мой доступ» ещё раз.")
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
                    flow=self.settings.vpn_flow,
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
                    flow=self.settings.vpn_flow,
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
                flow=self.settings.vpn_flow,
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
                "Оплата в боте доступна только через звёзды Telegram ⭐\nДля iPhone обычно используется способ оплаты через мобильный баланс МТС.",
            )
        )
        mode_prefix = "renew" if mode == "renew" else "buynew"
        payload_scope = f"{mode_prefix}:{user_id}:{int(target_subscription_id or 0)}:" if mode_prefix == "renew" else f"{mode_prefix}:{user_id}:"
        timestamp = int(datetime.now(timezone.utc).timestamp())
        rand = uuid.uuid4().hex[:6]
        if mode_prefix == "renew":
            payload = f"{mode_prefix}:{user_id}:{int(target_subscription_id or 0)}:{timestamp}:{rand}"
        else:
            payload = f"{mode_prefix}:{user_id}:{timestamp}:{rand}"
        order = await self.db.create_or_reuse_pending_stars_order(
            user_id=user_id,
            amount_stars=self.settings.plan_price_stars,
            payload_prefix=payload_scope,
            new_payload=payload,
            max_age_seconds=1800,
        )
        payload = str(order["payload"])
        if phone:
            self._pending_profiles[payload] = {"phone": phone, "name": (customer_name or "").strip()}
        price_label = self._content_text("invoice_price_label", "Оплата звёздами")
        prices = [LabeledPrice(label=price_label, amount=self.settings.plan_price_stars)]
        title = self._content_text("invoice_title", "Оплата VXcloud через звёзды")
        description = self._content_text(
            "invoice_description",
            "Оплата доступа в боте выполняется только через звёзды Telegram. Для iPhone чаще всего — через мобильный баланс МТС.",
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
            await query.answer(ok=False, error_message="Заказ не найден. Попробуйте снова.")
            return
        if order["status"] != "pending":
            await query.answer(ok=False, error_message="Заказ уже обработан.")
            return
        if int(query.total_amount) != int(order["amount_stars"]):
            await query.answer(ok=False, error_message="Сумма не совпадает. Попробуйте снова.")
            return
        await query.answer(ok=True)


    async def successful_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        assert update.message is not None
        payment = update.message.successful_payment
        order = await self.db.get_order_by_payload(payment.invoice_payload)
        if not order:
            await update.message.reply_text("Оплата получена, но заказ не найден. Обратитесь в поддержку.")
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
                    "Платёж уже обработан. Отправляю ваш доступ...",
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
                    "Платёж уже обработан. Отправляю ваш доступ...",
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
        await update.message.reply_text("Оплата получена. Подготавливаю доступ...")
        payload = str(order.get("payload") or "")
        is_renew = payload.startswith("renew:")
        renew_subscription_id: int | None = None
        if is_renew:
            parts = payload.split(":")
            if len(parts) >= 3 and parts[2].isdigit():
                parsed_id = int(parts[2])
                if parsed_id > 0:
                    renew_subscription_id = parsed_id

        try:
            await asyncio.wait_for(
                self._run_user_provision(
                    user_id,
                    lambda: self._activate_order_and_send_config(update, order_id, send_config=False),
                ),
                timeout=45,
            )
            subscriptions = await self.db.list_subscriptions(user_id)
            if not subscriptions:
                await self.mysub(update, context)
                return

            account_url = await self._account_url(user_id)
            target_id = int(subscriptions[0]["id"])
            target_exp = subscriptions[0].get("expires_at")
            if is_renew:
                if renew_subscription_id:
                    selected = await self.db.get_subscription(user_id, renew_subscription_id)
                    if selected:
                        target_id = renew_subscription_id
                        target_exp = selected.get("expires_at")
                expiry_text = self._format_local_dt(target_exp) if isinstance(target_exp, datetime) else "—"
                await update.message.reply_text(
                    "Доступ продлён\n\n"
                    "Теперь он действует до:\n"
                    f"{expiry_text}\n\n"
                    "Ниже вы можете открыть доступ, показать QR-код\n"
                    "или перейти к своим устройствам.",
                    reply_markup=self._renew_success_markup(target_id, account_url),
                )
            else:
                await update.message.reply_text(
                    "Оплата получена\n\n"
                    "Новый доступ готов.\n\n"
                    "Ниже вы можете сразу открыть его, показать QR-код\n"
                    "или перейти к своим данным.",
                    reply_markup=self._post_payment_ready_markup(target_id, account_url),
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
                    "Платёж получен, но активация задерживается. Нажмите «📊 Мой доступ» через 10-20 секунд. Если доступ не появится, напишите в поддержку.",
                )
            )
            if self.settings.telegram_admin_id:
                try:
                    await self.app.bot.send_message(
                        chat_id=self.settings.telegram_admin_id,
                        text=(
                            "⚠️ Ошибка активации после оплаты.\n"
                            f"user_id={order['user_id']} order_id={order['id']}"
                        ),
                    )
                except Exception:
                    LOGGER.exception("Failed to notify admin about provisioning issue")

    async def _activate_order_and_send_config(
        self,
        update: Update | None,
        order_id: int,
        message: Message | None = None,
        send_config: bool = True,
    ) -> None:
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
        sub_url = await self._subscription_feed_url(result.subscription_id, result.feed_token)
        if send_config:
            await self._send_config(
                update,
                result.vless_url,
                result.expires_at,
                sub_url,
                subscription_id=result.subscription_id,
                client_code=client_code,
                user_id=result.user_id,
                last_payment_method=last_payment_method,
                message=message,
            )

    async def myvpn(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = await self._ensure_user(update)
        sub = await self.db.get_active_subscription(user_id)
        if not sub:
            await update.message.reply_text("Доступ не найден. Используйте «⭐ Купить новый доступ».")
            return
        sub_url = await self._subscription_feed_url(
            int(sub["id"]),
            str(sub.get("feed_token") or ""),
        )
        client_code = await self.db.get_user_client_code(user_id)
        last_payment_method = await self.db.get_latest_payment_method(user_id)
        await self._send_config(
            update,
            str(sub["vless_url"]),
            sub["expires_at"],
            sub_url,
            subscription_id=int(sub["id"]),
            client_code=client_code,
            user_id=user_id,
            last_payment_method=last_payment_method,
        )

    async def _create_trial_for_user(self, update: Update, user_id: int, days: int) -> None:
        now = datetime.now(timezone.utc)
        client_uuid = str(uuid.uuid4())
        client_email = await self._build_client_email(user_id, client_uuid, prefix="trial")
        new_exp = now + timedelta(days=days)
        assigned_node_id: int | None = None

        if bool(getattr(self.settings, "vpn_cluster_enabled", False)):
            best = await pick_best_node(self.db)
            if not best:
                raise RuntimeError("No eligible VPN node found for trial activation")
            node = best.node
            reality = _node_reality_info(node)
            if reality is None:
                raise RuntimeError("Selected trial node has no usable Reality metadata")
            xui_sub_id = uuid.uuid5(uuid.NAMESPACE_URL, f"vxcloud:{client_uuid}").hex
            alias_fqdn = generate_subscription_alias(self.settings)
            created = await create_client_on_node(
                node,
                client_uuid=client_uuid,
                client_email=client_email,
                sub_id=xui_sub_id,
                expires_at=new_exp,
                limit_ip=self.settings.max_devices_per_sub,
                flow=self.settings.vpn_flow,
            )
            alias_result = await ensure_subscription_alias_record(
                settings=self.settings,
                alias_fqdn=alias_fqdn,
                node=node,
                ttl=int(getattr(self.settings, "vpn_alias_default_ttl", 300)),
            )
            vless_url = build_subscription_vless_url(
                settings=self.settings,
                node=node,
                client_uuid=client_uuid,
                reality=reality,
                subscription={"alias_fqdn": alias_fqdn},
            )
            assigned_node_id = int(node["id"])
            await self.db.create_subscription(
                user_id=user_id,
                inbound_id=int(node.get("xui_inbound_id") or self.settings.xui_inbound_id),
                client_uuid=client_uuid,
                client_email=client_email,
                xui_sub_id=str(created.get("xui_sub_id") or xui_sub_id),
                vless_url=vless_url,
                expires_at=new_exp,
                assigned_node_id=assigned_node_id,
                assignment_source="trial",
                migration_state="ready",
                alias_fqdn=alias_fqdn,
                current_node_id=assigned_node_id,
                desired_node_id=None,
                assignment_state="steady",
                ttl_seconds=alias_result.ttl,
                dns_provider=alias_result.provider,
                dns_record_id=alias_result.record_id,
                last_dns_change_id=alias_result.change_id,
                compatibility_pool=str(node.get("compatibility_pool") or "default"),
            )
        else:
            inbound = await self.xui.get_inbound(self.settings.xui_inbound_id)
            reality = self.xui.parse_reality(inbound)
            inbound_port = int(inbound["port"])
            await self.xui.add_client(
                self.settings.xui_inbound_id,
                client_uuid,
                client_email,
                new_exp,
                limit_ip=self.settings.max_devices_per_sub,
                flow=self.settings.vpn_flow,
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
                flow=self.settings.vpn_flow,
            )
            await self.db.create_subscription(
                user_id=user_id,
                inbound_id=self.settings.xui_inbound_id,
                client_uuid=client_uuid,
                client_email=client_email,
                vless_url=vless_url,
                expires_at=new_exp,
                assignment_source="trial",
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
            client_email = await self._build_client_email(user_id, client_uuid)
            new_exp = now + timedelta(days=self.settings.plan_days)
            await self.xui.add_client(
                self.settings.xui_inbound_id,
                client_uuid,
                client_email,
                new_exp,
                limit_ip=self.settings.max_devices_per_sub,
                flow=self.settings.vpn_flow,
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
                flow=self.settings.vpn_flow,
            )
            await self.db.create_subscription(
                user_id=user_id,
                inbound_id=self.settings.xui_inbound_id,
                client_uuid=client_uuid,
                client_email=client_email,
                vless_url=vless_url,
                expires_at=new_exp,
            )
            created_sub = await self.db.get_active_subscription(user_id)
            sub_url = None
            if created_sub and created_sub.get("id"):
                sub_url = await self._subscription_feed_url(
                    int(created_sub["id"]),
                    str(created_sub.get("feed_token") or ""),
                )
            last_payment_method = await self.db.get_latest_payment_method(user_id)
            await self._send_config(
                update,
                vless_url,
                new_exp,
                sub_url,
                subscription_id=None,
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
            flow=self.settings.vpn_flow,
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
            flow=self.settings.vpn_flow,
        )
        await self.db.extend_subscription(sub["id"], new_exp, vless_url)
        sub_url = await self._subscription_feed_url(
            int(sub["id"]),
            str(sub.get("feed_token") or ""),
        )
        last_payment_method = await self.db.get_latest_payment_method(user_id)
        await self._send_config(
            update,
            vless_url,
            new_exp,
            sub_url,
            subscription_id=int(sub["id"]),
            user_id=user_id,
            last_payment_method=last_payment_method,
        )

    async def _send_config(
        self,
        update: Update | None,
        vless_url: str,
        expires_at: datetime,
        subscription_url: str | None = None,
        subscription_id: int | None = None,
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
        qr_payload = link_for_copy
        qr_title = "QR доступа" if subscription_url else "QR подключения"

        account_url = await self._account_url(user_id)
        renew_path = "/account/renew/"
        if isinstance(subscription_id, int) and subscription_id > 0:
            renew_path = f"{renew_path}?subscription_id={subscription_id}"
        renew_url = await self._account_url(user_id, renew_path)

        buttons: list[list[InlineKeyboardButton]] = [
            [InlineKeyboardButton(text="📋 Скопировать ссылку", api_kwargs={"copy_text": {"text": link_for_copy}})],
        ]
        buttons.append(
            [
                InlineKeyboardButton(
                    text=self._with_card_price(self._button_label("pay_card_button", "💳 Оплатить картой")),
                    url=renew_url,
                )
            ]
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text=self._button_label("open_instructions", "💬 Инструкция"),
                    callback_data="nav|menu_instructions|_",
                )
            ]
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text=self._button_label("open_account", "🌐 Личный кабинет на сайте"),
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
            "Доступ активен до: {expires_at}\nID: {client_code}",
        )
        text = (
            text.replace("{expires_at}", self._format_local_dt(expires_at))
            .replace("{client_code}", resolved_client_code)
            .replace("{payment_method}", self._format_payment_method(last_payment_method))
            .replace("{subscription_url}", subscription_url or "")
            .replace("{vless_url}", vless_url)
            .replace("{user_id}", str(user_id) if user_id is not None else "")
        )
        if subscription_url and "{subscription_url}" not in text:
            text += f"\nПодписка VXcloud: {subscription_url}"
        if vless_url and "{vless_url}" not in text:
            text += f"\nRaw VLESS: {vless_url}"
        if "Способ оплаты:" not in text:
            text += f"\nСпособ оплаты: {self._format_payment_method(last_payment_method)}"
        copy_link_hint = self._content_text(
            "copy_link_hint",
            "Нажмите «Скопировать ссылку», затем откройте приложение, нажмите + и выберите импорт из буфера обмена.",
        ).replace("\\n", "\n").replace("/n", "\n")
        single_device_warning = self._content_text(
            "single_device_warning",
            "⚠️ Один доступ нельзя использовать одновременно на двух устройствах.",
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
                    if tg_id and int(tg_id) > 0:
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
            if tg_id <= 0:
                continue
            sub_id = int(item["id"])
            config_name = str(item.get("display_name") or f"Конфиг #{sub_id}")
            expires_label = self._format_local_dt(expires_at)
            if expires_at <= now:
                msg = self._content_text(
                    "reminder_expired_message",
                    "Истёк конфиг VXcloud: {name}\nДействовал до: {expires_at}\n\nИспользуйте /buy для продления.",
                )
                tag = "expired"
            elif expires_at <= now + timedelta(days=1):
                msg = self._content_text(
                    "reminder_1d_message",
                    "Напоминание: конфиг VXcloud скоро истекает\nУстройство: {name}\nДо: {expires_at}",
                )
                tag = "1d"
            else:
                msg = self._content_text(
                    "reminder_3d_message",
                    "Напоминание: конфиг VXcloud истекает менее чем через 3 дня\nУстройство: {name}\nДо: {expires_at}",
                )
                tag = "3d"
            msg = (
                msg.replace("{name}", config_name)
                .replace("{expires_at}", expires_label)
                .replace("{id}", str(sub_id))
            )

            try:
                await self.app.bot.send_message(chat_id=tg_id, text=msg)
                await self.db.log_reminder(sub_id, tag)
            except Exception:
                LOGGER.exception("Failed to send reminder to telegram_id=%s", tg_id)

