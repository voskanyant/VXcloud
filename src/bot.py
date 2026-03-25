from __future__ import annotations

import asyncio
import io
import logging
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

import qrcode
from PIL import Image, ImageDraw, ImageOps
from telegram import KeyboardButton, LabeledPrice, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
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
        self.app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, self.successful_payment))
        self.app.add_handler(MessageHandler(filters.CONTACT, self.handle_contact))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.menu_click))

    def _menu_keyboard(self) -> ReplyKeyboardMarkup:
        buy_label = self._button_label("menu_buy", "Купить VPN")
        mysub_label = self._button_label("menu_mysub", "Моя подписка")
        return ReplyKeyboardMarkup(
            [
                [KeyboardButton(buy_label), KeyboardButton(mysub_label)],
            ],
            resize_keyboard=True,
            is_persistent=True,
        )

    def _contact_keyboard(self) -> ReplyKeyboardMarkup:
        share_label = self._button_label("contact_share", "Share phone number")
        cancel_label = self._button_label("contact_cancel", "Cancel")
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
        await self._ensure_user(update)
        await self._refresh_cms()
        default_msg = (
            "Добро пожаловать в VPN X.\n\n"
            "Мы предлагаем быстрый, легкий и стабильный VPN для России.\n"
            "Подходит для повседневного использования: соцсети, мессенджеры, сайты и приложения.\n\n"
            "Нажмите «Купить VPN», чтобы оформить подписку, или «Моя подписка», чтобы проверить статус."
        )
        msg = self._content_text("start_message", default_msg)
        await update.message.reply_text(msg, reply_markup=self._menu_keyboard())

    async def menu_click(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._refresh_cms()
        raw_text = (update.message.text or "").strip()
        text = raw_text.lower()
        buy_label = self._button_label("menu_buy", "Купить VPN").strip().lower()
        sub_label = self._button_label("menu_mysub", "Моя подписка").strip().lower()
        cancel_label = self._button_label("contact_cancel", "Cancel").strip().lower()

        if text in {"cancel", "отмена", cancel_label}:
            context.user_data.pop("buy_wait_phone", None)
            context.user_data.pop("buy_wait_name", None)
            context.user_data.pop("buy_phone", None)
            await update.message.reply_text(
                self._content_text("cancel_message", "Операция отменена."),
                reply_markup=self._menu_keyboard(),
            )
            return

        if context.user_data.get("buy_wait_name"):
            user_id = await self._ensure_user(update)
            phone = context.user_data.get("buy_phone")
            if not phone:
                context.user_data.pop("buy_wait_name", None)
                await update.message.reply_text(
                    self._content_text("phone_missing_message", "Номер не сохранен. Нажмите Купить VPN еще раз."),
                    reply_markup=self._menu_keyboard(),
                )
                return
            customer_name = raw_text[:64]
            context.user_data.pop("buy_wait_name", None)
            context.user_data.pop("buy_phone", None)
            await update.message.reply_text(
                self._content_text("sending_invoice_message", "Высылаю счет..."),
                reply_markup=self._menu_keyboard(),
            )
            await self._send_stars_invoice(update, user_id, phone=phone, customer_name=customer_name)
            return

        if context.user_data.get("buy_wait_phone"):
            await update.message.reply_text(
                self._content_text("share_contact_hint_message", "Нажмите кнопку и поделитесь контактом."),
                reply_markup=self._contact_keyboard(),
            )
            return

        if text == buy_label:
            await self.buy(update, context)
            return
        if text == sub_label:
            await self.mysub(update, context)
            return
        await update.message.reply_text(
            self._content_text("menu_unknown_message", "Используйте кнопки меню: Купить VPN или Моя подписка."),
            reply_markup=self._menu_keyboard(),
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
                "Поделитесь номером телефона, затем отправьте имя и я выставлю счет.",
            ),
            reply_markup=self._contact_keyboard(),
        )

    async def handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._refresh_cms()
        if not context.user_data.get("buy_wait_phone"):
            return

        assert update.effective_user is not None
        contact = update.message.contact
        if contact is None:
            await update.message.reply_text(
                self._content_text("contact_missing_message", "Контакт не получен. Повторите."),
                reply_markup=self._contact_keyboard(),
            )
            return
        if contact.user_id and contact.user_id != update.effective_user.id:
            await update.message.reply_text(
                self._content_text("contact_self_only_message", "Поделитесь своим номером."),
                reply_markup=self._contact_keyboard(),
            )
            return

        try:
            normalized_phone = self._normalize_phone(contact.phone_number)
        except ValueError:
            await update.message.reply_text(
                self._content_text("phone_invalid_message", "Неверный формат номера. Повторите."),
                reply_markup=self._contact_keyboard(),
            )
            return

        context.user_data["buy_wait_phone"] = False
        context.user_data["buy_wait_name"] = True
        context.user_data["buy_phone"] = normalized_phone
        phone_saved_template = self._content_text(
            "phone_saved_message",
            "Номер сохранен: {phone}\nТеперь отправьте ваше имя.",
        )
        await update.message.reply_text(
            phone_saved_template.replace("{phone}", normalized_phone),
            reply_markup=self._menu_keyboard(),
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

    async def mysub(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._refresh_cms()
        user_id = await self._ensure_user(update)
        sub = await self.db.get_active_subscription(user_id)
        if not sub:
            await update.message.reply_text(
                self._content_text("no_subscription_message", "У вас нет активной подписки.\nНажмите «Купить VPN».")
            )
            return

        now = datetime.now(timezone.utc)
        expires_at = sub["expires_at"]
        if expires_at > now:
            days_left = int((expires_at - now).total_seconds() // 86400)
            if (expires_at - now).total_seconds() % 86400:
                days_left += 1
            await update.message.reply_text(
                "Подписка: АКТИВНА\n"
                f"Действует до: {expires_at:%Y-%m-%d %H:%M UTC}\n"
                f"Осталось дней: {days_left}"
            )
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
                "Подписка: ИСТЕКЛА\n"
                f"Дата окончания: {expires_at:%Y-%m-%d %H:%M UTC}"
            )

    async def _send_stars_invoice(
        self,
        update: Update,
        user_id: int,
        phone: str | None = None,
        customer_name: str | None = None,
    ) -> None:
        await self._refresh_cms()
        payload = f"buy:{user_id}:{int(datetime.now(timezone.utc).timestamp())}"
        await self.db.create_order(user_id=user_id, amount_stars=self.settings.plan_price_stars, payload=payload)
        if phone:
            self._pending_profiles[payload] = {"phone": phone, "name": (customer_name or "").strip()}
        prices = [LabeledPrice(label=f"VPN {self.settings.plan_days} days", amount=self.settings.plan_price_stars)]
        title = self._content_text("invoice_title", f"VPN на {self.settings.plan_days} дней")
        description = self._content_text("invoice_description", f"Доступ к VPN на {self.settings.plan_days} дней")
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
        payment = update.message.successful_payment
        order = await self.db.get_order_by_payload(payment.invoice_payload)
        if not order:
            await update.message.reply_text("Оплата получена, но заказ не найден. Обратитесь в поддержку.")
            return

        charge_id = payment.telegram_payment_charge_id
        if await self.db.is_charge_processed(charge_id):
            return

        await self.db.mark_order_paid(
            order_id=int(order["id"]),
            telegram_payment_charge_id=charge_id,
            provider_payment_charge_id=payment.provider_payment_charge_id,
        )
        profile = self._pending_profiles.pop(payment.invoice_payload, {})
        phone = profile.get("phone")
        customer_name = profile.get("name")
        await update.message.reply_text("Оплата прошла успешно. Активирую ваш VPN...")
        await self._create_or_extend_for_user(
            update,
            int(order["user_id"]),
            phone=phone,
            customer_name=customer_name,
        )

    async def myvpn(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = await self._ensure_user(update)
        sub = await self.db.get_active_subscription(user_id)
        if not sub:
            await update.message.reply_text("Подписка не найдена. Используйте /buy.")
            return
        client_uuid = str(sub["client_uuid"])
        sub_id = await self.xui.get_client_sub_id(self.settings.xui_inbound_id, client_uuid)
        sub_url = (
            f"https://{self.settings.vpn_public_host}:{self.settings.xui_sub_port}/sub/{sub_id}"
            if sub_id
            else None
        )
        await self._send_config(update, sub["vless_url"], sub["expires_at"], sub_url)

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
        await self.xui.update_client(self.settings.xui_inbound_id, client_uuid, client_email, new_exp)

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
        if subscription_url:
            sub_img = self._build_styled_qr(subscription_url, "Subscription QR")
            sub_buff = io.BytesIO()
            sub_img.save(sub_buff, format="PNG")
            sub_buff.seek(0)
            await update.message.reply_photo(photo=sub_buff)

        vless_img = self._build_styled_qr(vless_url, "Direct VLESS QR")
        vless_buff = io.BytesIO()
        vless_img.save(vless_buff, format="PNG")
        vless_buff.seek(0)

        text = f"Подписка активна до: {expires_at.strftime('%Y-%m-%d %H:%M UTC')}"
        if subscription_url:
            text += f"\n\nСсылка подписки:\n{subscription_url}"
        await update.message.reply_photo(photo=vless_buff)
        await update.message.reply_text(text)

    @staticmethod
    def _build_styled_qr(data: str, title: str) -> Image.Image:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=12,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#111111", back_color="white").convert("RGB")

        # White rounded card with a subtle accent stripe to improve visual style
        card_w = qr_img.width + 64
        card_h = qr_img.height + 120
        card = Image.new("RGB", (card_w, card_h), "#EEF3FF")
        draw = ImageDraw.Draw(card)
        draw.rounded_rectangle((8, 8, card_w - 8, card_h - 8), radius=28, fill="white", outline="#DCE5FF", width=2)
        draw.rounded_rectangle((24, 22, card_w - 24, 54), radius=16, fill="#E8F0FF")
        draw.text((36, 30), title, fill="#294A8D")

        qr_with_border = ImageOps.expand(qr_img, border=8, fill="#F4F7FF")
        card.paste(qr_with_border, ((card_w - qr_with_border.width) // 2, 68))
        return card

    async def reminder_tick(self) -> None:
        items = await self.db.due_reminders()
        now = datetime.now(timezone.utc)
        for item in items:
            expires_at = item["expires_at"]
            tg_id = int(item["telegram_id"])
            sub_id = int(item["id"])
            if expires_at <= now:
                msg = "Ваша подписка VPN истекла. Используйте /buy для продления."
                tag = "expired"
            elif expires_at <= now + timedelta(days=1):
                msg = f"Напоминание: подписка VPN истекает менее чем через 24 часа ({expires_at:%Y-%m-%d %H:%M UTC})."
                tag = "1d"
            else:
                msg = f"Напоминание: подписка VPN истекает менее чем через 3 дня ({expires_at:%Y-%m-%d %H:%M UTC})."
                tag = "3d"

            try:
                await self.app.bot.send_message(chat_id=tg_id, text=msg)
                await self.db.log_reminder(sub_id, tag)
            except Exception:
                LOGGER.exception("Failed to send reminder to telegram_id=%s", tg_id)
