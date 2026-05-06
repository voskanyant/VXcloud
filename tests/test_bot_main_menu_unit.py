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
    async def get_active_subscription(self, user_id: int):
        del user_id
        return None


class FakeMessage:
    chat_id = 123

    def __init__(self):
        self.replies = []

    async def edit_text(self, *args, **kwargs):
        raise RuntimeError("incoming user messages are not editable")

    async def reply_text(self, text, reply_markup=None):
        self.replies.append((text, reply_markup))


class BotMainMenuUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_screen_sends_persistent_reply_keyboard(self):
        bot = VPNBot(
            app=SimpleNamespace(bot=SimpleNamespace()),
            settings=SimpleNamespace(),
            db=FakeDB(),
            xui=SimpleNamespace(),
        )
        message = FakeMessage()

        await bot._send_start_screen(message, user_id=123)

        self.assertEqual(len(message.replies), 1)
        reply_markup = message.replies[0][1]
        self.assertIsInstance(reply_markup, ReplyKeyboardMarkup)
        self.assertNotIsInstance(reply_markup, InlineKeyboardMarkup)


if __name__ == "__main__":
    unittest.main()
