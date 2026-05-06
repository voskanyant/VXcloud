import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vxcloud_site.settings")

from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup

from src.bot import VPNBot


class FakeDB:
    def __init__(self):
        self.renamed = []
        self.support_messages = []

    async def fetch_bot_site_text_overrides(self):
        return {}

    async def get_active_subscription(self, user_id: int):
        del user_id
        return None

    async def upsert_user(self, telegram_id, username, first_name):
        del telegram_id, username, first_name
        return 123

    async def create_ticket(self, *, user_id, subject):
        del user_id, subject
        return 77

    async def add_message(self, *, ticket_id, sender_role, sender_user_id, message_text):
        self.support_messages.append((ticket_id, sender_role, sender_user_id, message_text))

    async def get_user_client_code(self, user_id: int):
        return f"VX-{user_id:06d}"

    async def rename_subscription(self, *, user_id, subscription_id, display_name):
        self.renamed.append((user_id, subscription_id, display_name))
        return True

    async def list_subscriptions(self, user_id: int):
        del user_id
        return []

    async def get_latest_paid_order(self, user_id: int):
        del user_id
        return None


class FakeMessage:
    chat_id = 123

    def __init__(self, text=""):
        self.text = text
        self.replies = []

    async def edit_text(self, *args, **kwargs):
        raise RuntimeError("incoming user messages are not editable")

    async def reply_text(self, text, reply_markup=None):
        self.replies.append((text, reply_markup))


def make_bot(db=None):
    settings = SimpleNamespace(
        card_payment_amount_minor=24900,
        card_payment_currency="RUB",
        magic_link_shared_secret="",
        magic_link_api_timeout_seconds=1,
        telegram_admin_id=0,
        timezone="UTC",
    )
    return VPNBot(
        app=SimpleNamespace(bot=SimpleNamespace()),
        settings=settings,
        db=db or FakeDB(),
        xui=SimpleNamespace(),
    )


def make_update(message):
    return SimpleNamespace(
        message=message,
        callback_query=None,
        effective_user=SimpleNamespace(id=999, username="tester", first_name="Test"),
    )


class BotMainMenuUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_screen_sends_minimal_persistent_reply_keyboard(self):
        bot = make_bot()
        message = FakeMessage()

        await bot._send_start_screen(message, user_id=123)

        self.assertEqual(len(message.replies), 1)
        reply_markup = message.replies[0][1]
        self.assertIsInstance(reply_markup, ReplyKeyboardMarkup)
        self.assertNotIsInstance(reply_markup, InlineKeyboardMarkup)
        labels = [button.text for row in reply_markup.keyboard for button in row]
        self.assertEqual(labels, ["My VPN", "Buy access", "Renew", "Support", "Open app"])
        open_app_button = reply_markup.keyboard[-1][0]
        self.assertIsNotNone(open_app_button.web_app)
        self.assertEqual(open_app_button.web_app.url, "https://vxcloud.ru/account-app/?embed=1")

    async def test_buy_markup_uses_mini_app_button_and_browser_fallback(self):
        bot = make_bot()

        markup = await bot._buy_offer_markup(user_id=123)

        self.assertIsNotNone(markup.inline_keyboard[0][0].web_app)
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/buy/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].url, "https://vxcloud.ru/account/?next=%2Faccount%2Fbuy%2F")

    async def test_my_vpn_list_has_direct_subscription_actions(self):
        bot = make_bot()
        subscriptions = [{"id": 42, "display_name": "Work laptop"}]

        markup = bot._configs_list_markup(subscriptions)

        self.assertEqual(markup.inline_keyboard[0][0].text, "1. Work laptop")
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "act|cfg_open:42|_")
        action_row = markup.inline_keyboard[1]
        self.assertEqual(action_row[0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertEqual(action_row[1].callback_data, "act|cfg_qr:42|_")
        self.assertEqual(action_row[2].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=42&embed=1")
        self.assertEqual(markup.inline_keyboard[-2][0].web_app.url, "https://vxcloud.ru/account-app/buy/?embed=1")
        self.assertEqual(markup.inline_keyboard[-1][0].callback_data, "act|buy_new|_")

    async def test_instructions_hub_uses_short_webapp_device_choices(self):
        bot = make_bot()

        markup = bot._node_inline_keyboard("menu_instructions")

        self.assertEqual(bot._node_response_text("menu_instructions"), "How to connect\n\nChoose your device. The full guide opens inside Telegram.")
        self.assertEqual(markup.inline_keyboard[0][0].text, "iPhone")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/instructions/?device=iphone")
        self.assertEqual(markup.inline_keyboard[1][0].web_app.url, "https://vxcloud.ru/instructions/?device=android")
        self.assertEqual(markup.inline_keyboard[2][0].web_app.url, "https://vxcloud.ru/instructions/?device=desktop")
        self.assertEqual(markup.inline_keyboard[3][0].web_app.url, "https://vxcloud.ru/instructions/")
        self.assertEqual(markup.inline_keyboard[4][0].callback_data, "act|start_mysub|_")

    async def test_support_message_submission_restores_main_menu(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage("Need help")
        context = SimpleNamespace(user_data={"support_wait_message": True})

        await bot.menu_click(make_update(message), context)

        self.assertNotIn("support_wait_message", context.user_data)
        self.assertEqual(db.support_messages, [(77, "user", 123, "Need help")])
        self.assertIsInstance(message.replies[-1][1], ReplyKeyboardMarkup)

    async def test_rename_submission_restores_main_menu(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage("Work laptop")
        context = SimpleNamespace(user_data={"rename_wait_subscription_id": 42})

        await bot.menu_click(make_update(message), context)

        self.assertNotIn("rename_wait_subscription_id", context.user_data)
        self.assertEqual(db.renamed, [(123, 42, "Work laptop")])
        self.assertTrue(any(isinstance(reply_markup, ReplyKeyboardMarkup) for _text, reply_markup in message.replies))


if __name__ == "__main__":
    unittest.main()
