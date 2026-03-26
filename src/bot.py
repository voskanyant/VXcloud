from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import qrcode
from PIL import Image
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, LabeledPrice, ReplyKeyboardMarkup, Update, WebAppInfo
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
from .vless import build_vless_url
from .xui_client import XUIClient


LOGGER = logging.getLogger(__name__)
STREISAND_APPSTORE_URL = "https://apps.apple.com/us/app/streisand/id6450534064"


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

    def register(self) -> None:
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("menu", self.start))
        self.app.add_handler(CommandHandler("buy", self.buy))
        self.app.add_handler(CommandHandler("mysub", self.mysub))
        self.app.add_handler(CommandHandler("myvpn", self.myvpn))
        self.app.add_handler(CommandHandler("renew", self.renew))
        self.app.add_handler(CommandHandler("admin_reload", self.admin_reload))
        self.app.add_handler(PreCheckoutQueryHandler(self.precheckout))
        self.app.add_handler(CallbackQueryHandler(self.inline_callback))
        self.app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, self.successful_payment))
        self.app.add_handler(MessageHandler(filters.CONTACT, self.handle_contact))
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

    def _contact_keyboard(self) -> ReplyKeyboardMarkup:
        share_label = self._button_label("contact_share", "\u041f\u043e\u0434\u0435\u043b\u0438\u0442\u044c\u0441\u044f \u043d\u043e\u043c\u0435\u0440\u043e\u043c")
        cancel_label = self._button_label("contact_cancel", "\u041e\u0442\u043c\u0435\u043d\u0430")
        return ReplyKeyboardMarkup(
            [[KeyboardButton(share_label, request_contact=True)], [KeyboardButton(cancel_label)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

    def _content_text(self, key: str, default: str) -> str:
        value = self._cms_content.get(key)
        return value if value else default

    def _button_label(self, key: str, default: str) -> str:
        value = self._cms_buttons.get(key)
        return value if value else default

    async def _has_active_subscription(self, user_id: int) -> bool:
        sub = await self.db.get_active_subscription(user_id)
        if not sub:
            return False
        return sub["expires_at"] > datetime.now(timezone.utc)

    async def _menu_keyboard_for_user(self, user_id: int) -> ReplyKeyboardMarkup:
        return self._menu_keyboard(has_active_subscription=await self._has_active_subscription(user_id))

    def _display_tz(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.settings.timezone)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")

    def _format_local_dt(self, dt: datetime) -> str:
        return dt.astimezone(self._display_tz()).strftime("%d/%m/%Y %H:%M")

    def _menu_buttons(self, has_active_subscription: bool = False) -> list[tuple[str, str]]:
        buy_key = "menu_renew" if has_active_subscription else "menu_buy"
        buy_default = "\U0001f504 \u041f\u0440\u043e\u0434\u043b\u0438\u0442\u044c" if has_active_subscription else "\U0001f4b3 \u041a\u0443\u043f\u0438\u0442\u044c VPN"
        return [
            ("menu_trial", self._button_label("menu_trial", "\U0001f381 \u0411\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e 7\u0434").strip() or "\U0001f381 \u0411\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e 7\u0434"),
            (buy_key, self._button_label(buy_key, buy_default).strip() or buy_default),
            ("menu_mysub", self._button_label("menu_mysub", "\U0001f4ca \u041c\u043e\u044f \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0430").strip() or "\U0001f4ca \u041c\u043e\u044f \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0430"),
            (
                "menu_instructions",
                self._button_label("menu_instructions", "\U0001f4ac \u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f").strip() or "\U0001f4ac \u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f",
            ),
            (
                "menu_site",
                self._button_label("menu_site", "\U0001f310 VXcloud.ru").strip() or "\U0001f310 VXcloud.ru",
            ),
        ]

    def _site_url(self) -> str:
        return self._content_text("site_url", "https://vxcloud.ru").strip() or "https://vxcloud.ru"

    def _account_url(self) -> str:
        explicit = self._content_text("account_page_url", "").strip()
        if explicit:
            return explicit
        return self._site_url().rstrip("/") + "/account/"

    def _open_app_url(self, config_url: str) -> str:
        return f"{self._site_url().rstrip('/')}/open-app/?u={quote(config_url, safe='')}"

    def _node_response_text(self, node_key: str) -> str:
        response_key = f"{node_key}_response"
        legacy_key = f"{node_key.removeprefix('menu_')}_response"
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
                if row_buttons:
                    rows.append(row_buttons)

        if parent_key:
            rows.append([InlineKeyboardButton(text="â¬…ï¸ Back", callback_data=f"nav|{parent_key}|_")])

        if not rows:
            return None
        return InlineKeyboardMarkup(rows)

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

        default_msg = (
            "\u0414\u043e\u0431\u0440\u043e \u043f\u043e\u0436\u0430\u043b\u043e\u0432\u0430\u0442\u044c \u0432 VXcloud.\n\n"
            "\u041c\u044b \u043f\u0440\u0435\u0434\u043b\u0430\u0433\u0430\u0435\u043c \u0431\u044b\u0441\u0442\u0440\u044b\u0439, \u043b\u0435\u0433\u043a\u0438\u0439 \u0438 \u0441\u0442\u0430\u0431\u0438\u043b\u044c\u043d\u044b\u0439 VPN \u0434\u043b\u044f \u0420\u043e\u0441\u0441\u0438\u0438.\n"
            "\u041f\u043e\u0434\u0445\u043e\u0434\u0438\u0442 \u0434\u043b\u044f \u043f\u043e\u0432\u0441\u0435\u0434\u043d\u0435\u0432\u043d\u043e\u0433\u043e \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u044f: \u0441\u043e\u0446\u0441\u0435\u0442\u0438, \u043c\u0435\u0441\u0441\u0435\u043d\u0434\u0436\u0435\u0440\u044b, \u0441\u0430\u0439\u0442\u044b \u0438 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u044f.\n\n"
            "\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 \u043a\u043d\u043e\u043f\u043a\u0438 \u043c\u0435\u043d\u044e \u043d\u0438\u0436\u0435."
        )
        msg = self._content_text("start_message", default_msg)
        await update.message.reply_text(msg, reply_markup=await self._menu_keyboard_for_user(user_id))

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
            await update.message.reply_text(
                self._content_text("cancel_message", "\u041e\u043f\u0435\u0440\u0430\u0446\u0438\u044f \u043e\u0442\u043c\u0435\u043d\u0435\u043d\u0430."),
                reply_markup=menu_keyboard,
            )
            return

        if context.user_data.get("buy_wait_name"):
            phone = context.user_data.get("buy_phone")
            if not phone:
                context.user_data.pop("buy_wait_name", None)
                await update.message.reply_text(
                    self._content_text("phone_missing_message", "\u041d\u043e\u043c\u0435\u0440 \u043d\u0435 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d. \u041d\u0430\u0436\u043c\u0438\u0442\u0435 \u00ab\u041a\u0443\u043f\u0438\u0442\u044c VPN\u00bb \u0435\u0449\u0435 \u0440\u0430\u0437."),
                    reply_markup=menu_keyboard,
                )
                return
            customer_name = raw_text[:64]
            context.user_data.pop("buy_wait_name", None)
            context.user_data.pop("buy_phone", None)
            await update.message.reply_text(
                self._content_text("sending_invoice_message", "\u0412\u044b\u0441\u044b\u043b\u0430\u044e \u0441\u0447\u0435\u0442..."),
                reply_markup=menu_keyboard,
            )
            await self._send_stars_invoice(update, user_id, phone=phone, customer_name=customer_name)
            return

        if context.user_data.get("buy_wait_phone"):
            await update.message.reply_text(
                self._content_text("share_contact_hint_message", "\u041d\u0430\u0436\u043c\u0438\u0442\u0435 \u043a\u043d\u043e\u043f\u043a\u0443 \u0438 \u043f\u043e\u0434\u0435\u043b\u0438\u0442\u0435\u0441\u044c \u043a\u043e\u043d\u0442\u0430\u043a\u0442\u043e\u043c."),
                reply_markup=self._contact_keyboard(),
            )
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
        await self._ensure_user(update)
        context.user_data["buy_wait_phone"] = True
        context.user_data.pop("buy_wait_name", None)
        context.user_data.pop("buy_phone", None)
        await update.message.reply_text(
            self._content_text(
                "buy_intro_message",
                "ÐŸÐ¾Ð´ÐµÐ»Ð¸Ñ‚ÐµÑÑŒ Ð½Ð¾Ð¼ÐµÑ€Ð¾Ð¼ Ñ‚ÐµÐ»ÐµÑ„Ð¾Ð½Ð°, Ð·Ð°Ñ‚ÐµÐ¼ Ð¾Ñ‚Ð¿Ñ€Ð°Ð²ÑŒÑ‚Ðµ Ð¸Ð¼Ñ Ð¸ Ñ Ð²Ñ‹ÑÑ‚Ð°Ð²Ð»ÑŽ ÑÑ‡ÐµÑ‚.",
            ),
            reply_markup=self._contact_keyboard(),
        )

    async def trial(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._refresh_cms()
        assert update.message is not None
        user_id = await self._ensure_user(update)

        if await self.db.has_any_subscription(user_id):
            await update.message.reply_text(
                self._content_text(
                    "trial_unavailable_message",
                    "\u041f\u0440\u043e\u0431\u043d\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434 \u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d \u0442\u043e\u043b\u044c\u043a\u043e \u043e\u0434\u0438\u043d \u0440\u0430\u0437 \u0434\u043b\u044f \u043d\u043e\u0432\u044b\u0445 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439.",
                ),
                reply_markup=await self._menu_keyboard_for_user(user_id),
            )
            return

        await update.message.reply_text(
            self._content_text("trial_activating_message", "\u0410\u043a\u0442\u0438\u0432\u0438\u0440\u0443\u044e \u0432\u0430\u0448 \u0431\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434 \u043d\u0430 7 \u0434\u043d\u0435\u0439..."),
            reply_markup=await self._menu_keyboard_for_user(user_id),
        )
        await self._create_trial_for_user(update, user_id=user_id, days=7)

    async def handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._refresh_cms()
        if not context.user_data.get("buy_wait_phone"):
            return

        assert update.effective_user is not None
        contact = update.message.contact
        if contact is None:
            await update.message.reply_text(
                self._content_text("contact_missing_message", "ÐšÐ¾Ð½Ñ‚Ð°ÐºÑ‚ Ð½Ðµ Ð¿Ð¾Ð»ÑƒÑ‡ÐµÐ½. ÐŸÐ¾Ð²Ñ‚Ð¾Ñ€Ð¸Ñ‚Ðµ."),
                reply_markup=self._contact_keyboard(),
            )
            return
        if contact.user_id and contact.user_id != update.effective_user.id:
            await update.message.reply_text(
                self._content_text("contact_self_only_message", "ÐŸÐ¾Ð´ÐµÐ»Ð¸Ñ‚ÐµÑÑŒ ÑÐ²Ð¾Ð¸Ð¼ Ð½Ð¾Ð¼ÐµÑ€Ð¾Ð¼."),
                reply_markup=self._contact_keyboard(),
            )
            return

        try:
            normalized_phone = self._normalize_phone(contact.phone_number)
        except ValueError:
            await update.message.reply_text(
                self._content_text("phone_invalid_message", "ÐÐµÐ²ÐµÑ€Ð½Ñ‹Ð¹ Ñ„Ð¾Ñ€Ð¼Ð°Ñ‚ Ð½Ð¾Ð¼ÐµÑ€Ð°. ÐŸÐ¾Ð²Ñ‚Ð¾Ñ€Ð¸Ñ‚Ðµ."),
                reply_markup=self._contact_keyboard(),
            )
            return

        context.user_data["buy_wait_phone"] = False
        context.user_data["buy_wait_name"] = True
        context.user_data["buy_phone"] = normalized_phone
        phone_saved_template = self._content_text(
            "phone_saved_message",
            "ÐÐ¾Ð¼ÐµÑ€ ÑÐ¾Ñ…Ñ€Ð°Ð½ÐµÐ½: {phone}\nÐ¢ÐµÐ¿ÐµÑ€ÑŒ Ð¾Ñ‚Ð¿Ñ€Ð°Ð²ÑŒÑ‚Ðµ Ð²Ð°ÑˆÐµ Ð¸Ð¼Ñ.",
        )
        await update.message.reply_text(
            phone_saved_template.replace("{phone}", normalized_phone),
            reply_markup=await self._menu_keyboard_for_user(await self._ensure_user(update)),
        )

    async def renew(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = await self._ensure_user(update)
        await self._send_stars_invoice(update, user_id)

    async def admin_reload(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.cms is None:
            await update.message.reply_text("CMS is not configured.")
            return
        if not update.effective_user or update.effective_user.id != self.settings.telegram_admin_id:
            await update.message.reply_text("Access denied.")
            return
        await self._refresh_cms(force=True)
        await update.message.reply_text("CMS content reloaded.")

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
        assert update.message is not None
        user_id = await self._ensure_user(update)
        sub = await self.db.get_active_subscription(user_id)
        if not sub:
            paid_order = await self.db.get_latest_paid_order(user_id)
            if paid_order:
                await update.message.reply_text(
                    self._content_text(
                        "recovering_subscription_message",
                        "ÐÐ°Ð¹Ð´ÐµÐ½ Ð¾Ð¿Ð»Ð°Ñ‡ÐµÐ½Ð½Ñ‹Ð¹ Ð·Ð°ÐºÐ°Ð·. ÐŸÑ€Ð¾Ð±ÑƒÑŽ Ð²Ð¾ÑÑÑ‚Ð°Ð½Ð¾Ð²Ð¸Ñ‚ÑŒ Ð¿Ð¾Ð´Ð¿Ð¸ÑÐºÑƒ...",
                    )
                )
                try:
                    await asyncio.wait_for(self._create_or_extend_for_user(update, user_id), timeout=45)
                    return
                except Exception:
                    LOGGER.exception(
                        "Failed to recover subscription for user_id=%s from paid order_id=%s",
                        user_id,
                        paid_order.get("id"),
                    )
                    await update.message.reply_text(
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
            await update.message.reply_text(
                self._content_text(
                    "no_subscription_message",
                    "Ð£ Ð²Ð°Ñ Ð½ÐµÑ‚ Ð°ÐºÑ‚Ð¸Ð²Ð½Ð¾Ð¹ Ð¿Ð¾Ð´Ð¿Ð¸ÑÐºÐ¸.\nÐÐ°Ð¶Ð¼Ð¸Ñ‚Ðµ Â«ÐšÑƒÐ¿Ð¸Ñ‚ÑŒ VPNÂ».",
                )
            )
            return

        now = datetime.now(timezone.utc)
        expires_at = sub["expires_at"]
        if expires_at > now:
            client_uuid = str(sub["client_uuid"])
            sub_id = await self.xui.get_client_sub_id(self.settings.xui_inbound_id, client_uuid)
            sub_url = (
                f"https://{self.settings.vpn_public_host}:{self.settings.xui_sub_port}/sub/{sub_id}"
                if sub_id
                else None
            )
            await self._send_config(update, sub["vless_url"], expires_at, sub_url)
        else:
            await update.message.reply_text(
                "ÐŸÐ¾Ð´Ð¿Ð¸ÑÐºÐ°: Ð˜Ð¡Ð¢Ð•ÐšÐ›Ð\n"
                f"Ð”Ð°Ñ‚Ð° Ð¾ÐºÐ¾Ð½Ñ‡Ð°Ð½Ð¸Ñ: {self._format_local_dt(expires_at)}"
            )

    async def _send_stars_invoice(
        self,
        update: Update,
        user_id: int,
        phone: str | None = None,
        customer_name: str | None = None,
    ) -> None:
        await self._refresh_cms()
        await update.message.reply_text(
            self._content_text(
                "stars_only_notice",
                "ÐžÐ¿Ð»Ð°Ñ‚Ð° Ð² Ð±Ð¾Ñ‚Ðµ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð½Ð° Ñ‚Ð¾Ð»ÑŒÐºÐ¾ Ñ‡ÐµÑ€ÐµÐ· Telegram Stars â­\nÐ”Ð»Ñ iPhone Ð¾Ð±Ñ‹Ñ‡Ð½Ð¾ Ð¸ÑÐ¿Ð¾Ð»ÑŒÐ·ÑƒÐµÑ‚ÑÑ ÑÐ¿Ð¾ÑÐ¾Ð± Ð¾Ð¿Ð»Ð°Ñ‚Ñ‹ Ñ‡ÐµÑ€ÐµÐ· Ð¼Ð¾Ð±Ð¸Ð»ÑŒÐ½Ñ‹Ð¹ Ð±Ð°Ð»Ð°Ð½Ñ ÐœÐ¢Ð¡.",
            )
        )
        payload = f"buy:{user_id}:{int(datetime.now(timezone.utc).timestamp())}"
        await self.db.create_order(user_id=user_id, amount_stars=self.settings.plan_price_stars, payload=payload)
        if phone:
            self._pending_profiles[payload] = {"phone": phone, "name": (customer_name or "").strip()}
        price_label = self._content_text("invoice_price_label", "ÐžÐ¿Ð»Ð°Ñ‚Ð° Ð² Stars")
        prices = [LabeledPrice(label=price_label, amount=self.settings.plan_price_stars)]
        title = self._content_text("invoice_title", "ÐžÐ¿Ð»Ð°Ñ‚Ð° VXcloud Ñ‡ÐµÑ€ÐµÐ· Stars")
        description = self._content_text(
            "invoice_description",
            "ÐžÐ¿Ð»Ð°Ñ‚Ð° Ð¿Ð¾Ð´Ð¿Ð¸ÑÐºÐ¸ Ð²Ñ‹Ð¿Ð¾Ð»Ð½ÑÐµÑ‚ÑÑ Ñ‚Ð¾Ð»ÑŒÐºÐ¾ Telegram Stars. Ð”Ð»Ñ iPhone Ñ‡Ð°Ñ‰Ðµ Ð²ÑÐµÐ³Ð¾ â€” Ñ‡ÐµÑ€ÐµÐ· Ð¼Ð¾Ð±Ð¸Ð»ÑŒÐ½Ñ‹Ð¹ Ð±Ð°Ð»Ð°Ð½Ñ ÐœÐ¢Ð¡.",
        )
        await update.message.reply_invoice(
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
        if await self.db.is_charge_processed(charge_id):
            # Recover path for duplicate callbacks: try to return config immediately.
            await update.message.reply_text(
                self._content_text(
                    "payment_already_processed_message",
                    "ÐŸÐ»Ð°Ñ‚ÐµÐ¶ ÑƒÐ¶Ðµ Ð¾Ð±Ñ€Ð°Ð±Ð¾Ñ‚Ð°Ð½. ÐžÑ‚Ð¿Ñ€Ð°Ð²Ð»ÑÑŽ Ð²Ð°ÑˆÑƒ Ð¿Ð¾Ð´Ð¿Ð¸ÑÐºÑƒ...",
                )
            )
            await self.mysub(update, context)
            return

        await self.db.mark_order_paid(
            order_id=int(order["id"]),
            telegram_payment_charge_id=charge_id,
            provider_payment_charge_id=payment.provider_payment_charge_id,
        )
        profile = self._pending_profiles.pop(payment.invoice_payload, {})
        phone = profile.get("phone")
        customer_name = profile.get("name")
        await update.message.reply_text("ÐžÐ¿Ð»Ð°Ñ‚Ð° Ð¿Ñ€Ð¾ÑˆÐ»Ð° ÑƒÑÐ¿ÐµÑˆÐ½Ð¾. ÐÐºÑ‚Ð¸Ð²Ð¸Ñ€ÑƒÑŽ Ð²Ð°Ñˆ VPN...")

        try:
            await asyncio.wait_for(
                self._create_or_extend_for_user(
                    update,
                    int(order["user_id"]),
                    phone=phone,
                    customer_name=customer_name,
                ),
                timeout=45,
            )
        except Exception:
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
        await self._send_config(update, sub["vless_url"], sub["expires_at"], sub_url)

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
        await self._send_config(update, vless_url, new_exp, sub_url)

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
            await self._send_config(update, vless_url, new_exp, sub_url)
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
        await self._send_config(update, vless_url, new_exp, sub_url)

    async def _send_config(
        self,
        update: Update,
        vless_url: str,
        expires_at: datetime,
        subscription_url: str | None = None,
    ) -> None:
        action_markup: InlineKeyboardMarkup | None = None
        link_for_copy = subscription_url or vless_url
        qr_payload = subscription_url or vless_url
        qr_title = "Subscription QR" if subscription_url else "Direct VLESS QR"

        buttons: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton(
                    text=self._button_label("open_in_app", "\U0001f680 \u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0432 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0438"),
                    url=self._open_app_url(vless_url),
                ),
                InlineKeyboardButton(
                    text="\U0001f4cb \u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443",
                    api_kwargs={"copy_text": {"text": link_for_copy}},
                ),
            ],
        ]
        if subscription_url:
            buttons.insert(0, [InlineKeyboardButton(text="\U0001f517 \u041e\u0442\u043a\u0440\u044b\u0442\u044c \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0443", url=subscription_url)])
        buttons.append(
            [
                InlineKeyboardButton(
                    text=self._button_label("open_account", "\U0001f464 \u041b\u0438\u0447\u043d\u044b\u0439 \u043a\u0430\u0431\u0438\u043d\u0435\u0442 \u043d\u0430 VXcloud"),
                    url=self._account_url(),
                )
            ]
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text=self._button_label("open_instructions", "\U0001f4d8 \u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f"),
                    callback_data="nav|menu_instructions|_",
                )
            ]
        )
        action_markup = InlineKeyboardMarkup(buttons)

        qr_img = self._build_styled_qr(qr_payload, qr_title)
        qr_buff = io.BytesIO()
        qr_img.save(qr_buff, format="PNG")
        qr_buff.seek(0)

        text = f"\u041f\u043e\u0434\u043f\u0438\u0441\u043a\u0430 \u0430\u043a\u0442\u0438\u0432\u043d\u0430 \u0434\u043e: {self._format_local_dt(expires_at)}"
        if subscription_url:
            text += f"\n\n\u0421\u0441\u044b\u043b\u043a\u0430 \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0438:\n{subscription_url}"
        copy_link_hint = self._content_text(
            "copy_link_hint",
            "Нажмите «Скопировать ссылку», затем откройте Streisand, нажмите + и выберите Import from Clipboard.",
        ).replace("\\n", "\n").replace("/n", "\n")
        text += "\n\n" + copy_link_hint

        await update.message.reply_photo(photo=qr_buff)
        await update.message.reply_text(text, reply_markup=action_markup)

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
