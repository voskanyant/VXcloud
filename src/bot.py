from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timedelta, timezone

import qrcode
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .config import Settings
from .db import DB
from .vless import build_vless_url
from .xui_client import XUIClient


LOGGER = logging.getLogger(__name__)


class VPNBot:
    def __init__(self, app: Application, settings: Settings, db: DB, xui: XUIClient) -> None:
        self.app = app
        self.settings = settings
        self.db = db
        self.xui = xui

    def register(self) -> None:
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("buy", self.buy))
        self.app.add_handler(CommandHandler("myvpn", self.myvpn))
        self.app.add_handler(CommandHandler("renew", self.renew))

    async def _ensure_user(self, update: Update) -> int:
        assert update.effective_user is not None
        u = update.effective_user
        return await self.db.upsert_user(u.id, u.username, u.first_name)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._ensure_user(update)
        msg = (
            "VPN bot is ready.\n\n"
            "Commands:\n"
            "/buy - Buy 30-day plan\n"
            "/myvpn - Show your current config and QR\n"
            "/renew - Extend your plan"
        )
        await update.message.reply_text(msg)

    async def buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._create_or_extend(update)

    async def renew(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._create_or_extend(update)

    async def myvpn(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = await self._ensure_user(update)
        sub = await self.db.get_active_subscription(user_id)
        if not sub:
            await update.message.reply_text("No subscription found. Use /buy first.")
            return
        await self._send_config(update, sub["vless_url"], sub["expires_at"])

    async def _create_or_extend(self, update: Update) -> None:
        user_id = await self._ensure_user(update)
        now = datetime.now(timezone.utc)
        sub = await self.db.get_active_subscription(user_id)

        inbound = await self.xui.get_inbound(self.settings.xui_inbound_id)
        reality = self.xui.parse_reality(inbound)
        inbound_port = int(inbound["port"])

        if sub is None:
            client_uuid = str(uuid.uuid4())
            client_email = f"tg_{user_id}_{int(now.timestamp())}"
            new_exp = now + timedelta(days=self.settings.plan_days)
            await self.xui.add_client(self.settings.xui_inbound_id, client_uuid, client_email, new_exp)

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
            await self._send_config(update, vless_url, new_exp)
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
        await self._send_config(update, vless_url, new_exp)

    async def _send_config(self, update: Update, vless_url: str, expires_at: datetime) -> None:
        img = qrcode.make(vless_url)
        buff = io.BytesIO()
        img.save(buff, format="PNG")
        buff.seek(0)

        text = (
            f"Plan active until: {expires_at.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"`{vless_url}`"
        )
        await update.message.reply_photo(photo=buff, caption="Your VPN QR")
        await update.message.reply_text(text, parse_mode="Markdown")

    async def reminder_tick(self) -> None:
        items = await self.db.due_reminders()
        now = datetime.now(timezone.utc)
        for item in items:
            expires_at = item["expires_at"]
            tg_id = int(item["telegram_id"])
            sub_id = int(item["id"])
            if expires_at <= now:
                msg = "Your VPN subscription has expired. Use /renew to reactivate."
                tag = "expired"
            elif expires_at <= now + timedelta(days=1):
                msg = f"Reminder: your VPN expires in less than 24h ({expires_at:%Y-%m-%d %H:%M UTC}). Use /renew."
                tag = "1d"
            else:
                msg = f"Reminder: your VPN expires in less than 3 days ({expires_at:%Y-%m-%d %H:%M UTC})."
                tag = "3d"

            try:
                await self.app.bot.send_message(chat_id=tg_id, text=msg)
                await self.db.log_reminder(sub_id, tag)
            except Exception:
                LOGGER.exception("Failed to send reminder to telegram_id=%s", tg_id)
