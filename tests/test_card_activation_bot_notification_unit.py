import os
import sys
import unittest
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"
if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vxcloud_site.settings")

import django

django.setup()

from cabinet.views import (  # noqa: E402
    _notify_user_after_card_activation,
    _telegram_my_vpn_reply_markup,
    _telegram_my_vpn_text_after_card_activation,
)


class FakeActivationNotifyDB:
    def __init__(self) -> None:
        self.notified = False
        self.subscriptions = [
            {
                "id": 42,
                "display_name": "Tigran iPhone",
                "expires_at": datetime.now(dt_timezone.utc) + timedelta(days=30),
                "is_active": True,
                "revoked_at": None,
            },
            {
                "id": 43,
                "display_name": "MacBook",
                "expires_at": datetime.now(dt_timezone.utc) + timedelta(days=10),
                "is_active": True,
                "revoked_at": None,
            },
        ]

    async def get_user_telegram_id(self, user_id: int) -> int:
        self.user_id = user_id
        return 999

    async def mark_order_notified_if_pending(self, order_id: int) -> bool:
        self.order_id = order_id
        if self.notified:
            return False
        self.notified = True
        return True

    async def get_user_client_code(self, user_id: int) -> str:
        self.user_id = user_id
        return "VX-000001"

    async def list_subscriptions(self, user_id: int):
        self.user_id = user_id
        return self.subscriptions


class CardActivationBotNotificationUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_card_activation_notification_sends_fresh_my_vpn_screen(self):
        db = FakeActivationNotifyDB()
        sent: list[tuple[str, int, str, dict[str, object] | None]] = []

        def fake_send(token, chat_id, text, reply_markup=None):
            sent.append((token, chat_id, text, reply_markup))

        with patch("cabinet.views._send_telegram_message_sync", side_effect=fake_send):
            await _notify_user_after_card_activation(
                db=db,
                order_id=1001,
                telegram_bot_token="token",
                user_id=123,
            )

        self.assertEqual(len(sent), 1)
        token, chat_id, text, reply_markup = sent[0]
        self.assertEqual(token, "token")
        self.assertEqual(chat_id, 999)
        self.assertIn("Оплата получена", text)
        self.assertIn("Мой VPN", text)
        self.assertIn("ID: VX-000001", text)
        self.assertIn("активных: 2", text)
        self.assertIn("Tigran iPhone", text)
        self.assertIn("MacBook", text)
        self.assertIsNotNone(reply_markup)
        self.assertEqual(reply_markup["inline_keyboard"][0][0]["callback_data"], "act|cfg_open:43|_")
        self.assertEqual(reply_markup["inline_keyboard"][1][0]["callback_data"], "act|cfg_open:42|_")

    async def test_card_activation_notification_is_sent_once(self):
        db = FakeActivationNotifyDB()
        sent: list[object] = []

        with patch("cabinet.views._send_telegram_message_sync", side_effect=lambda *args, **kwargs: sent.append(args)):
            await _notify_user_after_card_activation(
                db=db,
                order_id=1001,
                telegram_bot_token="token",
                user_id=123,
            )
            await _notify_user_after_card_activation(
                db=db,
                order_id=1001,
                telegram_bot_token="token",
                user_id=123,
            )

        self.assertEqual(len(sent), 1)

    def test_my_vpn_notification_text_has_spaced_entries_and_buttons(self):
        subscriptions = [
            {
                "id": 12,
                "display_name": "Phone",
                "expires_at": datetime.now(dt_timezone.utc) + timedelta(days=1),
                "is_active": True,
                "revoked_at": None,
            },
            {
                "id": 13,
                "display_name": "Laptop",
                "expires_at": datetime.now(dt_timezone.utc) + timedelta(days=10),
                "is_active": True,
                "revoked_at": None,
            },
        ]

        text = _telegram_my_vpn_text_after_card_activation(
            client_code="VX-000123",
            subscriptions=subscriptions,
        )
        markup = _telegram_my_vpn_reply_markup(subscriptions)

        self.assertIn("1. ⏳ скоро закончится Phone", text)
        self.assertIn("\n\n2. ✅ активен Laptop", text)
        self.assertEqual(markup["inline_keyboard"][0][0]["text"], "1. ⏳ Phone")
        self.assertEqual(markup["inline_keyboard"][1][0]["text"], "2. ✅ Laptop")


if __name__ == "__main__":
    unittest.main()
