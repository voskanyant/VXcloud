import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vxcloud_site.settings")

from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove

from src.bot import VPNBot


class FakeDB:
    def __init__(self):
        self.renamed = []
        self.events = []
        self.support_messages = []
        self.subscriptions = {}
        self.subscription_list = []
        self.deleted = []
        self.active_subscription = None
        self.has_subscription = False

    async def fetch_bot_site_text_overrides(self):
        return {}

    async def get_active_subscription(self, user_id: int):
        del user_id
        return self.active_subscription

    async def has_any_subscription(self, user_id: int):
        del user_id
        return self.has_subscription

    async def get_subscription(self, user_id: int, subscription_id: int):
        del user_id
        return self.subscriptions.get(subscription_id)

    async def ensure_subscription_feed_token(self, subscription_id: int):
        sub = self.subscriptions.get(subscription_id)
        if not sub:
            return ""
        token = str(sub.get("feed_token") or f"feed-{subscription_id}")
        sub["feed_token"] = token
        return token

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
        return self.subscription_list

    async def delete_subscription(self, user_id: int, subscription_id: int):
        self.deleted.append((user_id, subscription_id))
        return True

    async def get_latest_paid_order(self, user_id: int):
        del user_id
        return None

    async def record_bot_user_event(
        self,
        *,
        user_id,
        event_name,
        telegram_id=None,
        subscription_id=None,
        metadata=None,
    ):
        self.events.append(
            {
                "user_id": user_id,
                "event_name": event_name,
                "telegram_id": telegram_id,
                "subscription_id": subscription_id,
                "metadata": metadata or {},
            }
        )
        return True


class FakeMessage:
    chat_id = 123

    def __init__(self, text=""):
        self.text = text
        self.replies = []
        self.photos = []

    async def edit_text(self, *args, **kwargs):
        raise RuntimeError("incoming user messages are not editable")

    async def reply_text(self, text, reply_markup=None):
        self.replies.append((text, reply_markup))

    async def reply_photo(self, photo, caption=None, reply_markup=None):
        self.photos.append((photo, caption, reply_markup))


class FakeCallbackQuery:
    def __init__(self, data, message=None):
        self.data = data
        self.message = message or FakeMessage()
        self.answers = []
        self.edits = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text, reply_markup=None):
        self.edits.append((text, reply_markup))


class FakeXUI:
    def __init__(self):
        self.deleted = []

    async def delete_client(self, *args, **kwargs):
        self.deleted.append((args, kwargs))
        return "deleted"


class FakeQrImage:
    def save(self, buffer, format=None):
        del format
        buffer.write(b"qr")


def make_bot(db=None):
    settings = SimpleNamespace(
        card_payment_amount_minor=24900,
        card_payment_currency="RUB",
        magic_link_shared_secret="",
        magic_link_api_timeout_seconds=1,
        telegram_admin_id=0,
        timezone="UTC",
        max_devices_per_sub=1,
        vpn_flow="xtls-rprx-vision",
    )
    return VPNBot(
        app=SimpleNamespace(bot=SimpleNamespace()),
        settings=settings,
        db=db or FakeDB(),
        xui=FakeXUI(),
    )


def make_update(message):
    return SimpleNamespace(
        message=message,
        callback_query=None,
        effective_user=SimpleNamespace(id=999, username="tester", first_name="Test"),
    )


def make_callback_update(query):
    return SimpleNamespace(
        message=None,
        callback_query=query,
        effective_user=SimpleNamespace(id=999, username="tester", first_name="Test"),
    )


def expired_subscription(subscription_id=42):
    return {
        "id": subscription_id,
        "display_name": "Old phone",
        "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
        "is_active": False,
        "revoked_at": None,
        "inbound_id": 7,
        "client_uuid": "11111111-1111-4111-8111-111111111111",
        "client_email": "old-phone@example.test",
        "alias_fqdn": "",
        "dns_record_id": "",
    }


class BotMainMenuUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_screen_sends_minimal_persistent_reply_keyboard(self):
        bot = make_bot()
        message = FakeMessage()

        await bot._send_start_screen(message, user_id=123)

        self.assertEqual(len(message.replies), 1)
        text = message.replies[0][0]
        self.assertIn("Добро пожаловать", text)
        self.assertIn("Кабинет", text)
        self.assertNotIn("Как подключить", text)
        reply_markup = message.replies[0][1]
        self.assertIsInstance(reply_markup, ReplyKeyboardMarkup)
        self.assertNotIsInstance(reply_markup, InlineKeyboardMarkup)
        labels = [button.text for row in reply_markup.keyboard for button in row]
        self.assertEqual(labels, ["Мой VPN", "Купить", "Продлить", "Поддержка", "Кабинет"])
        open_app_button = reply_markup.keyboard[-1][0]
        self.assertIsNotNone(open_app_button.web_app)
        self.assertEqual(open_app_button.web_app.url, "https://vxcloud.ru/account-app/?embed=1")

    async def test_broken_cms_text_and_button_overrides_fall_back_to_defaults(self):
        bot = make_bot()
        bot._cms_content["menu_open_app_response"] = "ÐžÑ‚ÐºÑ€Ñ‹Ñ‚ÑŒ Mini App"
        bot._cms_buttons["menu_open_app"] = "ÐšÐ°Ð±Ð¸Ð½ÐµÑ‚"

        self.assertEqual(bot._content_text("menu_open_app_response", "Чистый текст"), "Чистый текст")
        self.assertEqual(bot._button_label("menu_open_app", "Кабинет"), "Кабинет")

    async def test_start_screen_shows_compact_status_for_active_subscriptions(self):
        db = FakeDB()
        db.subscription_list = [
            {
                "id": 42,
                "display_name": "Work laptop",
                "expires_at": datetime.now(timezone.utc) + timedelta(days=2),
                "is_active": True,
                "revoked_at": None,
            },
            {
                "id": 43,
                "display_name": "Old phone",
                "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
                "is_active": False,
                "revoked_at": None,
            },
        ]
        bot = make_bot(db)
        message = FakeMessage()

        await bot._send_start_screen(message, user_id=123)

        text = message.replies[0][0]
        self.assertIn("Мой VPN", text)
        self.assertIn("Активных доступов: 1", text)
        self.assertIn("Ближайшее окончание: Work laptop", text)
        self.assertIn("Заканчиваются скоро: 1", text)
        self.assertIsInstance(message.replies[0][1], ReplyKeyboardMarkup)

    async def test_open_app_text_fallback_is_mini_app_first_and_tracked(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage("Кабинет")

        await bot.menu_click(make_update(message), SimpleNamespace(user_data={}))

        self.assertEqual(db.events[-1]["event_name"], "open_app")
        self.assertEqual(db.events[-1]["metadata"], {"source": "reply_menu"})
        text, markup = message.replies[-1]
        self.assertIn("кабинет VXcloud", text)
        self.assertIn("браузер", text)
        self.assertEqual(markup.inline_keyboard[0][0].text, "Кабинет")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "Открыть в браузере")

    async def test_legacy_site_menu_routes_to_mini_app_first(self):
        db = FakeDB()
        bot = make_bot(db)
        bot._menu_buttons = lambda has_active_subscription=False: [("menu_site", "Legacy account")]
        message = FakeMessage("Legacy account")

        await bot.menu_click(make_update(message), SimpleNamespace(user_data={}))

        self.assertEqual(db.events[-1]["event_name"], "open_app")
        self.assertEqual(db.events[-1]["metadata"], {"source": "legacy_site_menu"})
        text, markup = message.replies[-1]
        self.assertIn("Mini App", text)
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "Открыть в браузере")

    async def test_buy_markup_uses_compact_payment_actions(self):
        bot = make_bot()

        markup = await bot._buy_offer_markup(user_id=123)

        self.assertIsNotNone(markup.inline_keyboard[0][0].web_app)
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/buy/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "Оплатить Stars")
        self.assertEqual(markup.inline_keyboard[2][0].text, "Назад")
        self.assertEqual(len(markup.inline_keyboard), 3)

    async def test_buy_copy_names_mini_app_as_card_checkout_surface(self):
        bot = make_bot()
        message = FakeMessage()

        await bot._show_buy_checkout_options(message, user_id=123)

        text = message.replies[-1][0]
        self.assertIn("Mini App", text)
        self.assertIn("Telegram Stars", text)
        self.assertNotIn("на сайте", text)

    async def test_buy_with_active_access_is_app_first_for_additional_access(self):
        db = FakeDB()
        db.active_subscription = {
            "id": 42,
            "display_name": "Work laptop",
            "expires_at": datetime.now(timezone.utc) + timedelta(days=10),
            "is_active": True,
            "revoked_at": None,
        }
        bot = make_bot(db)
        message = FakeMessage()

        await bot._show_buy_offer(message, user_id=123)

        text = message.replies[-1][0]
        self.assertIn("Mini App", text)
        self.assertIn("Telegram Stars", text)
        markup = message.replies[-1][1]
        self.assertEqual(markup.inline_keyboard[0][0].text, "\u041a\u0443\u043f\u0438\u0442\u044c \u0435\u0449\u0435 \u0434\u043e\u0441\u0442\u0443\u043f \u00b7 249 RUB")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/buy/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "act|buy_existing_renew|_")
        self.assertEqual(markup.inline_keyboard[2][0].callback_data, "act|buy_stars_continue|_")
        self.assertEqual(markup.inline_keyboard[3][0].callback_data, "act|start_back|_")
        self.assertEqual(len(markup.inline_keyboard), 4)

    async def test_legacy_card_markups_keep_mini_app_primary(self):
        bot = make_bot()

        buy_markup = await bot._buy_card_markup(user_id=123)
        renew_markup = await bot._renew_card_markup(user_id=123, subscription_id=42)

        self.assertEqual(buy_markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/buy/?embed=1")
        self.assertEqual(buy_markup.inline_keyboard[1][0].callback_data, "act|buy_card_back|_")
        self.assertEqual(len(buy_markup.inline_keyboard), 2)
        self.assertEqual(renew_markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=42&embed=1")
        self.assertEqual(renew_markup.inline_keyboard[1][0].callback_data, "act|renew_card_back|_")
        self.assertEqual(len(renew_markup.inline_keyboard), 2)

    async def test_payment_ready_markups_keep_app_primary_and_browser_fallback(self):
        bot = make_bot()
        account_url = "https://vxcloud.ru/account/"

        paid_markup = bot._post_payment_ready_markup(42, account_url)
        renew_markup = bot._renew_success_markup(42, account_url)

        self.assertEqual(paid_markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertEqual(paid_markup.inline_keyboard[1][0].text, "\u0412 \u0431\u043e\u0442\u0435")
        self.assertEqual(paid_markup.inline_keyboard[1][0].callback_data, "act|cfg_open:42|_")
        self.assertEqual(paid_markup.inline_keyboard[1][1].text, "QR")
        self.assertEqual(paid_markup.inline_keyboard[-1][0].text, "\u041c\u043e\u0439 VPN")
        self.assertEqual(len(paid_markup.inline_keyboard[-1]), 1)
        self.assertEqual(renew_markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertEqual(renew_markup.inline_keyboard[1][0].text, "\u0412 \u0431\u043e\u0442\u0435")
        self.assertEqual(renew_markup.inline_keyboard[1][1].text, "QR")
        self.assertEqual(renew_markup.inline_keyboard[-1][0].text, "\u041c\u043e\u0439 VPN")
        self.assertEqual(len(renew_markup.inline_keyboard[-1]), 1)

    async def test_send_config_actions_are_mini_app_first(self):
        bot = make_bot()
        message = FakeMessage()

        await bot._send_config(
            update=None,
            vless_url="vless://11111111-1111-4111-8111-111111111111@example.test:443?type=tcp#VXcloud",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            subscription_url="https://vxcloud.ru/account/feed/token/",
            subscription_id=42,
            user_id=123,
            message=message,
        )

        self.assertEqual(len(message.photos), 1)
        markup = message.replies[-1][1]
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443 \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0438")
        self.assertEqual(
            markup.inline_keyboard[1][0].api_kwargs["copy_text"]["text"],
            "https://vxcloud.ru/account/feed/token/",
        )
        self.assertEqual(markup.inline_keyboard[2][0].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=42&embed=1")
        self.assertEqual(markup.inline_keyboard[3][0].text, "\u041a\u0430\u043a \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0438\u0442\u044c")
        self.assertEqual(markup.inline_keyboard[3][0].callback_data, "nav|menu_instructions|_")
        self.assertEqual(len(markup.inline_keyboard), 4)

    async def test_send_config_fallback_connection_link_label_is_russian(self):
        bot = make_bot()
        message = FakeMessage()

        await bot._send_config(
            update=None,
            vless_url="vless://11111111-1111-4111-8111-111111111111@example.test:443?type=tcp#VXcloud",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            subscription_url=None,
            subscription_id=42,
            user_id=123,
            message=message,
        )

        self.assertIn("\u0421\u0441\u044b\u043b\u043a\u0430 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f:", message.replies[-1][0])
        self.assertNotIn("Connection link", message.replies[-1][0])

    async def test_trial_success_markup_uses_mini_app_config_first(self):
        bot = make_bot()

        markup = bot._trial_success_markup(42)

        self.assertEqual(markup.inline_keyboard[0][0].text, "\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u043a\u0430\u0431\u0438\u043d\u0435\u0442")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "act|cfg_qr:42|_")
        self.assertEqual(markup.inline_keyboard[2][1].callback_data, "act|start_mysub|_")

    async def test_trial_offer_markup_uses_clean_contextual_actions(self):
        bot = make_bot()

        markup = bot._trial_offer_markup()

        self.assertEqual(markup.inline_keyboard[0][0].text, "\u0410\u043a\u0442\u0438\u0432\u0438\u0440\u043e\u0432\u0430\u0442\u044c 7 \u0434\u043d\u0435\u0439")
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "act|trial_activate|_")
        self.assertEqual(markup.inline_keyboard[1][0].text, "\u041d\u0430\u0437\u0430\u0434")
        self.assertEqual(len(markup.inline_keyboard[1]), 1)

    async def test_trial_used_state_is_app_first_buy(self):
        db = FakeDB()
        db.has_subscription = True
        bot = make_bot(db)
        message = FakeMessage()

        await bot._show_trial_offer(message, user_id=123)

        text = message.replies[-1][0]
        self.assertIn("Mini App", text)
        self.assertIn("Telegram Stars", text)
        markup = message.replies[-1][1]
        self.assertEqual(markup.inline_keyboard[0][0].text, "\u041a\u0443\u043f\u0438\u0442\u044c \u0432 \u043a\u0430\u0431\u0438\u043d\u0435\u0442\u0435 \u00b7 249 RUB")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/buy/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "act|buy_new|_")
        self.assertEqual(markup.inline_keyboard[2][0].callback_data, "act|start_back|_")
        self.assertEqual(len(markup.inline_keyboard), 3)

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

    async def test_my_vpn_empty_state_points_to_mini_app_buy(self):
        bot = make_bot()

        text = bot._configs_list_text(client_code="VX-000123", subscriptions=[])
        markup = bot._configs_list_markup([])

        self.assertIn("VX-000123", text)
        self.assertIn("Mini App", text)
        self.assertIn("QR", text)
        self.assertEqual(markup.inline_keyboard[0][0].text, "\u041a\u0443\u043f\u0438\u0442\u044c \u0432 \u043a\u0430\u0431\u0438\u043d\u0435\u0442\u0435")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/buy/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "\u041a\u0443\u043f\u0438\u0442\u044c Stars")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "act|buy_new|_")

    async def test_config_card_delete_uses_confirmation_callback(self):
        bot = make_bot()

        markup = await bot._config_card_markup(
            user_id=123,
            subscription_id=42,
            copy_text="https://vxcloud.ru/account/feed/token/",
            can_delete=True,
        )

        self.assertEqual(markup.inline_keyboard[0][0].text, "\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u043a\u0430\u0431\u0438\u043d\u0435\u0442")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "QR")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "act|cfg_qr:42|_")
        self.assertEqual(markup.inline_keyboard[1][1].text, "\u041f\u0440\u043e\u0434\u043b\u0438\u0442\u044c")
        self.assertEqual(markup.inline_keyboard[1][1].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=42&embed=1")
        self.assertEqual(markup.inline_keyboard[2][0].text, "\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443")
        self.assertEqual(markup.inline_keyboard[3][0].text, "\u041f\u0435\u0440\u0435\u0438\u043c\u0435\u043d\u043e\u0432\u0430\u0442\u044c")
        self.assertEqual(markup.inline_keyboard[3][1].text, "\u0423\u0434\u0430\u043b\u0438\u0442\u044c")
        self.assertEqual(markup.inline_keyboard[3][1].callback_data, "act|cfg_delete_request:42|_")
        self.assertEqual(markup.inline_keyboard[4][0].text, "\u041d\u0430\u0437\u0430\u0434")
        self.assertEqual(len(markup.inline_keyboard[4]), 1)
        self.assertEqual(markup.inline_keyboard[-1][0].callback_data, "act|cfg_back|_")

    async def test_qr_action_uses_subscription_feed_url_not_raw_vless(self):
        db = FakeDB()
        db.subscriptions[42] = {
            "id": 42,
            "display_name": "Work laptop",
            "expires_at": datetime.now(timezone.utc) + timedelta(days=10),
            "is_active": True,
            "revoked_at": None,
            "feed_token": "feed-token",
            "vless_url": "vless://raw-config@example.test:443#raw",
        }
        bot = make_bot(db)
        captured = {}

        def fake_build_qr(data, title):
            captured["data"] = data
            captured["title"] = title
            return FakeQrImage()

        bot._build_styled_qr = fake_build_qr
        query = FakeCallbackQuery("act|cfg_qr:42|_")

        await bot.inline_callback(make_callback_update(query), SimpleNamespace(user_data={}))

        self.assertEqual(captured["data"], "https://vxcloud.ru/account/feed/feed-token/")
        self.assertNotIn("vless://", captured["data"])
        self.assertEqual(db.events[-1]["event_name"], "qr_opened")
        self.assertEqual(db.events[-1]["subscription_id"], 42)
        self.assertEqual(len(query.message.photos), 1)
        self.assertIn("https://vxcloud.ru/account/feed/feed-token/", query.message.photos[0][1])

    async def test_delete_request_shows_confirmation_without_deleting(self):
        db = FakeDB()
        db.subscriptions[42] = expired_subscription()
        bot = make_bot(db)
        query = FakeCallbackQuery("act|cfg_delete_request:42|_")

        await bot.inline_callback(make_callback_update(query), SimpleNamespace(user_data={}))

        self.assertEqual(db.deleted, [])
        self.assertEqual(bot.xui.deleted, [])
        self.assertIn("\u0423\u0434\u0430\u043b\u0438\u0442\u044c Old phone?", query.edits[-1][0])
        self.assertEqual(query.edits[-1][1].inline_keyboard[0][0].callback_data, "act|cfg_delete_confirm:42|_")

    async def test_delete_cancel_answer_is_russian(self):
        db = FakeDB()
        db.subscriptions[42] = expired_subscription()
        bot = make_bot(db)
        query = FakeCallbackQuery("act|cfg_delete_cancel:42|_")

        await bot.inline_callback(make_callback_update(query), SimpleNamespace(user_data={}))

        self.assertEqual(query.answers[-1], ("\u0423\u0434\u0430\u043b\u0435\u043d\u0438\u0435 \u043e\u0442\u043c\u0435\u043d\u0435\u043d\u043e", False))

    async def test_active_delete_rejection_answer_is_russian(self):
        db = FakeDB()
        db.subscriptions[42] = {
            **expired_subscription(),
            "expires_at": datetime.now(timezone.utc) + timedelta(days=10),
            "is_active": True,
        }
        bot = make_bot(db)
        query = FakeCallbackQuery("act|cfg_delete_request:42|_")

        await bot.inline_callback(make_callback_update(query), SimpleNamespace(user_data={}))

        self.assertEqual(
            query.answers[-1],
            ("\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0439 \u043a\u043e\u043d\u0444\u0438\u0433 \u0443\u0434\u0430\u043b\u0438\u0442\u044c \u043d\u0435\u043b\u044c\u0437\u044f", True),
        )
        self.assertEqual(db.deleted, [])

    async def test_delete_confirm_removes_subscription_after_confirmation(self):
        db = FakeDB()
        db.subscriptions[42] = expired_subscription()
        bot = make_bot(db)
        query = FakeCallbackQuery("act|cfg_delete_confirm:42|_")

        await bot.inline_callback(make_callback_update(query), SimpleNamespace(user_data={}))

        self.assertEqual(db.deleted, [(123, 42)])
        self.assertEqual(len(bot.xui.deleted), 1)
        self.assertEqual(query.edits[-1][1].inline_keyboard[-1][0].callback_data, "act|buy_new|_")

    async def test_renew_offer_requires_explicit_choice_for_multiple_subscriptions(self):
        db = FakeDB()
        db.subscription_list = [
            {**expired_subscription(11), "display_name": "Phone"},
            {**expired_subscription(12), "display_name": "Laptop"},
        ]
        bot = make_bot(db)
        message = FakeMessage()
        context = SimpleNamespace(user_data={})

        await bot._show_renew_offer(message, user_id=123, context=context)

        self.assertNotIn("selected_subscription_id", context.user_data)
        self.assertIn("\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0434\u043e\u0441\u0442\u0443\u043f \u0434\u043b\u044f \u043f\u0440\u043e\u0434\u043b\u0435\u043d\u0438\u044f", message.replies[-1][0])
        markup = message.replies[-1][1]
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "act|renew_select:11|_")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "act|renew_select:12|_")
        self.assertEqual(markup.inline_keyboard[-2][0].web_app.url, "https://vxcloud.ru/account-app/renew/?embed=1")

    async def test_renew_without_active_access_is_app_first_buy(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage()
        context = SimpleNamespace(user_data={})

        await bot._show_renew_offer(message, user_id=123, context=context)

        text = message.replies[-1][0]
        self.assertIn("Mini App", text)
        self.assertIn("Telegram Stars", text)
        markup = message.replies[-1][1]
        self.assertEqual(markup.inline_keyboard[0][0].text, "\u041a\u0443\u043f\u0438\u0442\u044c \u0432 \u043a\u0430\u0431\u0438\u043d\u0435\u0442\u0435 \u00b7 249 RUB")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/buy/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "act|buy_new|_")
        self.assertEqual(markup.inline_keyboard[2][0].callback_data, "act|start_trial|_")
        self.assertEqual(markup.inline_keyboard[2][1].callback_data, "act|renew_back|_")
        self.assertEqual(len(markup.inline_keyboard), 3)

    async def test_renew_select_targets_subscription_before_showing_payment_options(self):
        db = FakeDB()
        db.subscriptions[12] = {**expired_subscription(12), "display_name": "Laptop"}
        bot = make_bot(db)
        query = FakeCallbackQuery("act|renew_select:12|_")
        context = SimpleNamespace(user_data={})

        await bot.inline_callback(make_callback_update(query), context)

        self.assertEqual(context.user_data["selected_subscription_id"], 12)
        self.assertEqual(db.events[-1]["event_name"], "renew_clicked")
        self.assertEqual(db.events[-1]["subscription_id"], 12)
        markup = query.message.replies[-1][1]
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=12&embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "\u041f\u0440\u043e\u0434\u043b\u0438\u0442\u044c Stars")
        self.assertEqual(markup.inline_keyboard[2][0].text, "\u041d\u0430\u0437\u0430\u0434")
        self.assertEqual(len(markup.inline_keyboard), 3)

    async def test_renew_select_invalid_answers_are_russian(self):
        bot = make_bot()
        bad_query = FakeCallbackQuery("act|renew_select:bad|_")

        await bot.inline_callback(make_callback_update(bad_query), SimpleNamespace(user_data={}))

        self.assertEqual(bad_query.answers[-1], ("\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u0430\u044f \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0430", True))

        missing_query = FakeCallbackQuery("act|renew_select:999|_")
        await bot.inline_callback(make_callback_update(missing_query), SimpleNamespace(user_data={}))

        self.assertEqual(missing_query.answers[-1], ("\u041f\u043e\u0434\u043f\u0438\u0441\u043a\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430", True))

    async def test_renew_copy_names_mini_app_as_card_checkout_surface(self):
        db = FakeDB()
        db.subscription_list = [
            {
                "id": 42,
                "display_name": "Work laptop",
                "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
                "is_active": True,
                "revoked_at": None,
            }
        ]
        bot = make_bot(db)
        message = FakeMessage()
        context = SimpleNamespace(user_data={})

        await bot._show_renew_offer(message, user_id=123, context=context)

        text = message.replies[-1][0]
        self.assertIn("Mini App", text)
        self.assertIn("Telegram Stars", text)
        self.assertNotIn("на сайте", text)

    async def test_instructions_hub_uses_short_webapp_device_choices(self):
        bot = make_bot()

        markup = bot._node_inline_keyboard("menu_instructions")

        self.assertEqual(bot._node_response_text("menu_instructions"), "\u041a\u0430\u043a \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0438\u0442\u044c\n\n\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u043e. \u041f\u043e\u043b\u043d\u0430\u044f \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f \u043e\u0442\u043a\u0440\u043e\u0435\u0442\u0441\u044f \u0432 Telegram.")
        self.assertEqual(markup.inline_keyboard[0][0].text, "iPhone")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/instructions/?device=iphone")
        self.assertEqual(markup.inline_keyboard[1][0].web_app.url, "https://vxcloud.ru/instructions/?device=android")
        self.assertEqual(markup.inline_keyboard[2][0].web_app.url, "https://vxcloud.ru/instructions/?device=desktop")
        self.assertEqual(markup.inline_keyboard[3][0].web_app.url, "https://vxcloud.ru/instructions/")
        self.assertEqual(markup.inline_keyboard[4][0].callback_data, "act|start_mysub|_")

    async def test_legacy_install_instructions_open_full_guide_in_mini_app(self):
        bot = make_bot()

        markup = bot._node_inline_keyboard("instructions_install")

        self.assertEqual(
            bot._node_response_text("instructions_install"),
            "\u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f \u043f\u043e \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044e\n\n\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u043e \u0432 \u043a\u0430\u0431\u0438\u043d\u0435\u0442\u0435. \u0422\u0430\u043c \u0441\u043e\u0431\u0440\u0430\u043d\u044b \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u0438, \u0441\u0441\u044b\u043b\u043a\u0438 \u043d\u0430 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u044f \u0438 \u0434\u0430\u043d\u043d\u044b\u0435 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430.",
        )
        self.assertEqual(markup.inline_keyboard[0][0].text, "\u041f\u043e\u043b\u043d\u0430\u044f \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/instructions/")
        self.assertIsNone(markup.inline_keyboard[0][0].url)
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "nav|menu_instructions|_")

    async def test_support_hub_offers_quick_message_and_mini_app(self):
        bot = make_bot()

        markup = bot._support_hub_markup()

        self.assertEqual(markup.inline_keyboard[0][0].text, "\u041d\u0430\u043f\u0438\u0441\u0430\u0442\u044c \u0432 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0443")
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "act|support_start|_")
        self.assertEqual(markup.inline_keyboard[1][0].text, "\u041f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430 \u0432 \u043a\u0430\u0431\u0438\u043d\u0435\u0442\u0435")
        self.assertEqual(markup.inline_keyboard[1][0].web_app.url, "https://vxcloud.ru/account-app/?view=support&embed=1")
        self.assertEqual(markup.inline_keyboard[2][0].callback_data, "act|start_back|_")
        self.assertEqual(len(markup.inline_keyboard[2]), 1)

    async def test_show_support_hub_uses_contextual_inline_markup(self):
        bot = make_bot()
        message = FakeMessage()

        await bot._show_support_hub(message, user_id=123)

        self.assertIn("VX-000123", message.replies[0][0])
        self.assertIsInstance(message.replies[0][1], InlineKeyboardMarkup)
        self.assertEqual(message.replies[0][1].inline_keyboard[1][0].web_app.url, "https://vxcloud.ru/account-app/?view=support&embed=1")

    async def test_support_start_hides_main_menu_for_text_input(self):
        bot = make_bot()
        query = FakeCallbackQuery("act|support_start|_")
        context = SimpleNamespace(user_data={})

        await bot.inline_callback(make_callback_update(query), context)

        self.assertTrue(context.user_data["support_wait_message"])
        self.assertEqual(bot.db.events[-1]["event_name"], "support_started")
        self.assertIsInstance(query.message.replies[-1][1], ReplyKeyboardRemove)

    async def test_support_message_submission_restores_main_menu(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage("Need help")
        context = SimpleNamespace(user_data={"support_wait_message": True})

        await bot.menu_click(make_update(message), context)

        self.assertNotIn("support_wait_message", context.user_data)
        self.assertEqual(db.support_messages, [(77, "user", 123, "Need help")])
        self.assertEqual(db.events[-1]["event_name"], "support_sent")
        self.assertIsInstance(message.replies[-1][1], ReplyKeyboardMarkup)

    async def test_empty_support_message_restores_main_menu_without_ticket(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage("   ")
        context = SimpleNamespace(user_data={"support_wait_message": True})

        await bot.menu_click(make_update(message), context)

        self.assertNotIn("support_wait_message", context.user_data)
        self.assertEqual(db.support_messages, [])
        self.assertEqual(db.events, [])
        self.assertIsInstance(message.replies[-1][1], ReplyKeyboardMarkup)

    async def test_menu_button_during_support_input_cancels_input_without_ticket(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage("\u041c\u043e\u0439 VPN")
        context = SimpleNamespace(user_data={"support_wait_message": True})

        await bot.menu_click(make_update(message), context)

        self.assertNotIn("support_wait_message", context.user_data)
        self.assertEqual(db.support_messages, [])
        self.assertIsInstance(message.replies[0][1], ReplyKeyboardMarkup)
        self.assertIn("\u0412\u0432\u043e\u0434 \u043e\u0442\u043c\u0435\u043d\u0435\u043d", message.replies[0][0])
        self.assertIn("VX-000123", message.replies[-1][0])
        self.assertIn("Mini App", message.replies[-1][0])

    async def test_cancel_clears_rename_state_and_restores_main_menu(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage("cancel")
        context = SimpleNamespace(
            user_data={
                "rename_wait_subscription_id": 42,
                "support_wait_message": True,
                "buy_wait_phone": True,
            }
        )

        await bot.menu_click(make_update(message), context)

        self.assertNotIn("rename_wait_subscription_id", context.user_data)
        self.assertNotIn("support_wait_message", context.user_data)
        self.assertNotIn("buy_wait_phone", context.user_data)
        self.assertEqual(db.renamed, [])
        self.assertIsInstance(message.replies[-1][1], ReplyKeyboardMarkup)

    async def test_rename_request_hides_main_menu_for_text_input(self):
        bot = make_bot()
        query = FakeCallbackQuery("act|cfg_rename:42|_")
        context = SimpleNamespace(user_data={})

        await bot.inline_callback(make_callback_update(query), context)

        self.assertEqual(context.user_data["rename_wait_subscription_id"], 42)
        self.assertIsInstance(query.message.replies[-1][1], ReplyKeyboardRemove)

    async def test_rename_submission_restores_main_menu(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage("Work laptop")
        context = SimpleNamespace(user_data={"rename_wait_subscription_id": 42})

        await bot.menu_click(make_update(message), context)

        self.assertNotIn("rename_wait_subscription_id", context.user_data)
        self.assertEqual(db.renamed, [(123, 42, "Work laptop")])
        self.assertTrue(any(isinstance(reply_markup, ReplyKeyboardMarkup) for _text, reply_markup in message.replies))

    async def test_empty_rename_submission_restores_main_menu_without_rename(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage("   ")
        context = SimpleNamespace(user_data={"rename_wait_subscription_id": 42})

        await bot.menu_click(make_update(message), context)

        self.assertNotIn("rename_wait_subscription_id", context.user_data)
        self.assertEqual(db.renamed, [])
        self.assertIsInstance(message.replies[-1][1], ReplyKeyboardMarkup)

    async def test_menu_button_during_rename_input_cancels_rename(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage("\u041f\u0440\u043e\u0434\u043b\u0438\u0442\u044c")
        context = SimpleNamespace(user_data={"rename_wait_subscription_id": 42})

        await bot.menu_click(make_update(message), context)

        self.assertNotIn("rename_wait_subscription_id", context.user_data)
        self.assertEqual(db.renamed, [])
        self.assertIsInstance(message.replies[0][1], ReplyKeyboardMarkup)
        self.assertIn("\u0412\u0432\u043e\u0434 \u043e\u0442\u043c\u0435\u043d\u0435\u043d", message.replies[0][0])
        self.assertIn("Mini App", message.replies[-1][0])


if __name__ == "__main__":
    unittest.main()
