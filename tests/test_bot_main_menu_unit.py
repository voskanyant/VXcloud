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

from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup

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
        self.reminders = []
        self.logged_reminders = []

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

    async def due_reminders(self):
        return self.reminders

    async def log_reminder(self, subscription_id: int, tag: str):
        self.logged_reminders.append((subscription_id, tag))
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


class FakeTelegramBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, *, chat_id, text, reply_markup=None):
        self.messages.append((chat_id, text, reply_markup))


def make_bot(db=None):
    settings = SimpleNamespace(
        card_payment_amount_minor=24900,
        card_payment_currency="RUB",
        plan_price_stars=250,
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


def active_subscription(subscription_id=42, *, name="Phone", days=10):
    return {
        "id": subscription_id,
        "display_name": name,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=days),
        "is_active": True,
        "revoked_at": None,
        "inbound_id": 7,
        "client_uuid": "11111111-1111-4111-8111-111111111111",
        "client_email": f"device-{subscription_id}@example.test",
        "feed_token": f"feed-{subscription_id}",
        "vless_url": f"vless://raw-{subscription_id}@example.test:443#raw",
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
        self.assertIn("VXcloud", text)
        self.assertIn("Кабинет внутри Telegram", text)
        self.assertIn("меню ниже", text)
        self.assertNotIn("Как подключить", text)
        self.assertNotIn("Бот помогает", text)
        reply_markup = message.replies[0][1]
        self.assertIsInstance(reply_markup, ReplyKeyboardMarkup)
        self.assertNotIsInstance(reply_markup, InlineKeyboardMarkup)
        labels = [button.text for row in reply_markup.keyboard for button in row]
        self.assertEqual(labels, ["🛡 Мой VPN", "🎁 7 дней бесплатно", "💳 Купить", "🔄 Продлить", "📖 Инструкция", "🆘 Поддержка", "📱 Кабинет"])
        open_app_button = reply_markup.keyboard[-1][0]
        self.assertIsNotNone(open_app_button.web_app)
        self.assertEqual(open_app_button.web_app.url, "https://vxcloud.ru/account-app/?embed=1")

    async def test_broken_cms_text_and_button_overrides_fall_back_to_defaults(self):
        bot = make_bot()
        bot._cms_content["menu_open_app_response"] = "ÐžÑ‚ÐºÑ€Ñ‹Ñ‚ÑŒ Mini App"
        bot._cms_buttons["menu_open_app"] = "ÐšÐ°Ð±Ð¸Ð½ÐµÑ‚"

        self.assertEqual(bot._content_text("menu_open_app_response", "Чистый текст"), "Чистый текст")
        self.assertEqual(bot._button_label("menu_open_app", "📱 Кабинет"), "📱 Кабинет")

    async def test_stale_english_cms_overrides_fall_back_to_russian_defaults(self):
        bot = make_bot()
        bot._cms_buttons.update(
            {
                "menu_my_vpn": "My VPN",
                "menu_trial": "7 days free",
                "menu_buy_access": "Buy access",
                "menu_renew_access": "Renew",
                "menu_instructions": "Instructions",
                "menu_support_simple": "Support",
                "menu_open_app": "Open app",
                "open_instructions": "How to connect",
            }
        )
        bot._cms_content["menu_open_app_response"] = "Open your account dashboard."
        bot._cms_content["menu_instructions_response"] = "How to connect\n\nChoose your device."
        bot._cms_content["custom_buttons"] = '[{"text": "Open guide", "url": "https://example.test"}]'

        labels = [label for _key, label in bot._menu_buttons()]
        self.assertEqual(labels, ["🛡 Мой VPN", "🎁 7 дней бесплатно", "💳 Купить", "🔄 Продлить", "📖 Инструкция", "🆘 Поддержка", "📱 Кабинет"])
        self.assertEqual(
            bot._content_text("menu_open_app_response", "Откройте кабинет."),
            "Откройте кабинет.",
        )
        self.assertIn("Инструкция", bot._node_response_text("menu_instructions"))
        self.assertEqual(bot._button_label("open_instructions", "Как подключить"), "Как подключить")
        self.assertIsNone(bot._node_inline_keyboard("custom"))

    async def test_old_plain_menu_overrides_do_not_remove_icons(self):
        bot = make_bot()
        bot._cms_buttons.update(
            {
                "menu_my_vpn": "Мой VPN",
                "menu_trial": "7 дней бесплатно",
                "menu_buy_access": "Купить",
                "menu_renew_access": "Продлить",
                "menu_instructions": "Инструкция",
                "menu_support_simple": "Поддержка",
                "menu_open_app": "Кабинет",
            }
        )

        labels = [label for _key, label in bot._menu_buttons()]

        self.assertEqual(labels, ["🛡 Мой VPN", "🎁 7 дней бесплатно", "💳 Купить", "🔄 Продлить", "📖 Инструкция", "🆘 Поддержка", "📱 Кабинет"])

    async def test_cms_inline_back_buttons_are_filtered_out(self):
        bot = make_bot()
        bot._cms_content["custom_buttons"] = '[{"text": "⬅️ Назад", "submenu": "menu_mysub"}, {"text": "QR", "action": "cfg_qr:42"}]'

        markup = bot._node_inline_keyboard("custom")

        self.assertIsNotNone(markup)
        self.assertEqual(len(markup.inline_keyboard), 1)
        self.assertEqual(len(markup.inline_keyboard[0]), 1)
        self.assertEqual(markup.inline_keyboard[0][0].text, "QR")

    async def test_legacy_instruction_text_routes_to_instruction_hub(self):
        bot = make_bot()
        message = FakeMessage("📖 Как подключить")

        await bot.menu_click(make_update(message), SimpleNamespace(user_data={}))

        text, markup = message.replies[-1]
        self.assertIn("Инструкция", text)
        self.assertIn("кабинете внутри Telegram", text)
        self.assertIsInstance(markup, InlineKeyboardMarkup)
        self.assertEqual(markup.inline_keyboard[0][0].text, "iPhone")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/?view=instructions&device=iphone&embed=1")
        self.assertNotIn("Используйте кнопки меню", text)

    async def test_cms_url_and_platform_only_values_are_still_allowed(self):
        bot = make_bot()
        bot._cms_content["site_url"] = "https://vxcloud.ru"
        bot._cms_content["invoice_price_label"] = "Telegram Stars"

        self.assertEqual(bot._content_text("site_url", "https://fallback.test"), "https://vxcloud.ru")
        self.assertEqual(bot._content_text("invoice_price_label", "Оплата звёздами"), "Telegram Stars")

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
        self.assertIn("Ваш VPN", text)
        self.assertIn("✅ Активных: 1", text)
        self.assertIn("Ближайшее окончание: Work laptop", text)
        self.assertIn("⏳ Скоро закончится: 1", text)
        self.assertIn("⚠️ Истекло: 1", text)
        self.assertIsInstance(message.replies[0][1], ReplyKeyboardMarkup)

    async def test_start_screen_shows_expired_status_without_active_subscriptions(self):
        db = FakeDB()
        db.subscription_list = [expired_subscription(42), expired_subscription(43)]
        bot = make_bot(db)
        message = FakeMessage()

        await bot._send_start_screen(message, user_id=123)

        text, reply_markup = message.replies[0]
        self.assertIn("Ваш VPN", text)
        self.assertIn("Активных доступов нет", text)
        self.assertIn("⚠️ Истекло: 2", text)
        self.assertIn("🔄 Продлить", text)
        self.assertIsInstance(reply_markup, ReplyKeyboardMarkup)
        self.assertNotIsInstance(reply_markup, InlineKeyboardMarkup)

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
        self.assertNotIn("Mini App", text)
        self.assertEqual(markup.inline_keyboard[0][0].text, "📱 Кабинет")
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
        self.assertIn("кабинет VXcloud", text)
        self.assertIn("браузер", text)
        self.assertNotIn("Mini App", text)
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "Открыть в браузере")

    async def test_buy_markup_uses_compact_payment_actions(self):
        bot = make_bot()

        markup = await bot._buy_offer_markup(user_id=123)

        self.assertIsNotNone(markup.inline_keyboard[0][0].web_app)
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/buy/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "⭐ Купить за Stars · 250 Stars")
        self.assertEqual(len(markup.inline_keyboard), 2)

    async def test_buy_copy_names_mini_app_as_card_checkout_surface(self):
        bot = make_bot()
        message = FakeMessage()

        await bot._show_buy_checkout_options(message, user_id=123)

        text = message.replies[-1][0]
        self.assertIn("Картой", text)
        self.assertIn("Stars", text)
        self.assertIn("🛡 Мой VPN", text)
        self.assertNotIn("бот пришлет", text)
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
        self.assertIn("активный доступ", text)
        self.assertIn("Устройство: Work laptop", text)
        self.assertIn("Купить ещё устройство", text)
        self.assertIn("Продлить этот доступ", text)
        self.assertNotIn("Можно купить еще один доступ", text)
        markup = message.replies[-1][1]
        self.assertEqual(markup.inline_keyboard[0][0].text, "💳 Купить ещё устройство · 249 RUB")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/buy/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "🔄 Продлить этот доступ")
        self.assertEqual(markup.inline_keyboard[1][0].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=42&embed=1")
        self.assertEqual(markup.inline_keyboard[2][0].text, "⭐ Купить ещё за Stars · 250 Stars")
        self.assertEqual(markup.inline_keyboard[2][0].callback_data, "act|buy_stars_continue|_")
        self.assertEqual(len(markup.inline_keyboard), 3)

    async def test_legacy_card_markups_keep_mini_app_primary(self):
        bot = make_bot()

        buy_markup = await bot._buy_card_markup(user_id=123)
        renew_markup = await bot._renew_card_markup(user_id=123, subscription_id=42)

        self.assertEqual(buy_markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/buy/?embed=1")
        self.assertEqual(len(buy_markup.inline_keyboard), 1)
        self.assertEqual(renew_markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=42&embed=1")
        self.assertEqual(len(renew_markup.inline_keyboard), 1)

    async def test_payment_ready_markups_keep_app_primary_and_qr_only(self):
        bot = make_bot()
        account_url = "https://vxcloud.ru/account/"

        paid_markup = bot._post_payment_ready_markup(42, account_url)
        renew_markup = bot._renew_success_markup(42, account_url)

        self.assertEqual(paid_markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertEqual(paid_markup.inline_keyboard[1][0].text, "QR")
        self.assertEqual(paid_markup.inline_keyboard[1][0].callback_data, "act|cfg_qr:42|_")
        self.assertEqual(len(paid_markup.inline_keyboard), 2)
        self.assertEqual(renew_markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertEqual(renew_markup.inline_keyboard[1][0].text, "QR")
        self.assertEqual(renew_markup.inline_keyboard[1][0].callback_data, "act|cfg_qr:42|_")
        self.assertEqual(len(renew_markup.inline_keyboard), 2)

    async def test_payment_success_copy_is_compact_and_action_oriented(self):
        bot = make_bot()

        new_text = bot._payment_success_text(is_renew=False)
        renew_text = bot._payment_success_text(is_renew=True, expiry_text="10/05/2026 12:00")

        self.assertEqual(new_text, "Новый доступ готов\n\nОткройте кабинет или QR.")
        self.assertEqual(
            renew_text,
            "Доступ продлён\nДействует до: 10/05/2026 12:00\n\nОткройте кабинет или QR.",
        )
        self.assertNotIn("Ниже вы можете", new_text)
        self.assertNotIn("Ниже вы можете", renew_text)

    async def test_stars_invoice_copy_is_short_and_mode_specific(self):
        bot = make_bot()

        buy_notice = bot._stars_notice_text(is_renew=False)
        renew_notice = bot._stars_notice_text(is_renew=True)
        buy_description = bot._stars_invoice_description(is_renew=False)
        renew_description = bot._stars_invoice_description(is_renew=True)

        self.assertIn("Оплата Stars", buy_notice)
        self.assertIn("🛡 Мой VPN", buy_notice)
        self.assertIn("срок обновится автоматически", renew_notice)
        self.assertIn("Покупка доступа", buy_description)
        self.assertIn("Продление доступа", renew_description)
        self.assertNotIn("мобильный баланс", buy_notice.lower())
        self.assertNotIn("мобильный баланс", buy_description.lower())
        self.assertNotIn("Для iPhone", renew_notice)

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
        text = message.replies[-1][0]
        self.assertIn("\u0414\u043e\u0441\u0442\u0443\u043f \u0433\u043e\u0442\u043e\u0432", text)
        self.assertIn("QR", text)
        self.assertIn("\u0441\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443", text)
        self.assertNotIn("https://vxcloud.ru/account/feed/token/", text)
        self.assertNotIn("vless://", text)
        markup = message.replies[-1][1]
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443 \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0438")
        self.assertEqual(
            markup.inline_keyboard[1][0].api_kwargs["copy_text"]["text"],
            "https://vxcloud.ru/account/feed/token/",
        )
        self.assertEqual(markup.inline_keyboard[2][0].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=42&embed=1")
        self.assertEqual(markup.inline_keyboard[3][0].text, "📖 Как подключить")
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

        self.assertIn("\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443", message.replies[-1][1].inline_keyboard[1][0].text)
        self.assertNotIn("vless://", message.replies[-1][0])
        self.assertNotIn("Connection link", message.replies[-1][0])

    async def test_trial_success_markup_uses_mini_app_config_first(self):
        bot = make_bot()

        markup = bot._trial_success_markup(42)

        self.assertEqual(markup.inline_keyboard[0][0].text, "📱 Открыть кабинет")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "act|cfg_qr:42|_")
        self.assertEqual(markup.inline_keyboard[2][0].callback_data, "nav|menu_instructions|_")

    async def test_trial_success_copy_is_compact_and_shows_expiry(self):
        bot = make_bot()
        expires_at = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)

        text = bot._trial_success_text(expires_at)

        self.assertIn("7 дней бесплатно активированы", text)
        self.assertIn("Действует до: 10/05/2026 12:00", text)
        self.assertIn("Откройте кабинет, QR или инструкцию.", text)
        self.assertNotIn("Ниже вы можете", text)
        self.assertNotIn("сразу открыть доступ", text)

    async def test_trial_offer_markup_uses_clean_contextual_actions(self):
        bot = make_bot()

        markup = bot._trial_offer_markup()

        self.assertEqual(markup.inline_keyboard[0][0].text, "🎁 Активировать 7 дней")
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "act|trial_activate|_")
        self.assertEqual(len(markup.inline_keyboard), 1)

    async def test_trial_offer_copy_is_short_and_cabinet_first(self):
        bot = make_bot()
        message = FakeMessage()

        await bot._show_trial_offer(message, user_id=123)

        text = message.replies[-1][0]
        self.assertIn("7 дней бесплатно", text)
        self.assertIn("в кабинете", text)
        self.assertNotIn("бот пришлет", text)

    async def test_trial_used_state_is_app_first_buy(self):
        db = FakeDB()
        db.has_subscription = True
        bot = make_bot(db)
        message = FakeMessage()

        await bot._show_trial_offer(message, user_id=123)

        text = message.replies[-1][0]
        self.assertIn("7 дней уже использованы", text)
        self.assertIn("Stars", text)
        self.assertIn("за Stars", text)
        self.assertNotIn("Telegram Stars", text)
        markup = message.replies[-1][1]
        self.assertEqual(markup.inline_keyboard[0][0].text, "💳 Купить картой · 249 RUB")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/buy/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "act|buy_new|_")
        self.assertEqual(len(markup.inline_keyboard), 2)

    async def test_trial_used_with_active_access_points_to_current_subscription(self):
        db = FakeDB()
        db.has_subscription = True
        db.active_subscription = active_subscription(42, name="Phone", days=5)
        bot = make_bot(db)
        message = FakeMessage()

        await bot._show_trial_offer(message, user_id=123)

        text = message.replies[-1][0]
        self.assertIn("7 дней уже использованы", text)
        self.assertIn("активный доступ", text)
        self.assertIn("Устройство: Phone", text)
        self.assertIn("Действует до", text)
        self.assertNotIn("Можно купить доступ", text)
        markup = message.replies[-1][1]
        self.assertEqual(markup.inline_keyboard[0][0].text, "📱 Открыть кабинет")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "QR")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "act|cfg_qr:42|_")
        self.assertEqual(markup.inline_keyboard[1][1].text, "🔄 Продлить")
        self.assertEqual(markup.inline_keyboard[1][1].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=42&embed=1")

    async def test_trial_activation_failure_is_clear_and_keeps_state_clean(self):
        bot = make_bot()
        query = FakeCallbackQuery("act|trial_activate|_")
        context = SimpleNamespace(user_data={})

        async def fail_trial(*args, **kwargs):
            del args, kwargs
            raise RuntimeError("node unavailable")

        bot._create_trial_for_user = fail_trial

        with self.assertLogs("src.bot", level="ERROR") as logs:
            await bot.inline_callback(make_callback_update(query), context)

        self.assertNotIn("trial_activating", context.user_data)
        self.assertIn("Trial activation failed user_id=123", "\n".join(logs.output))
        self.assertEqual(query.answers[-1], (None, False))
        self.assertEqual(len(query.message.replies), 2)
        pending_text, pending_markup = query.message.replies[0]
        failure_text, failure_markup = query.message.replies[1]
        self.assertIn("Активирую пробный доступ", pending_text)
        self.assertIsInstance(pending_markup, ReplyKeyboardMarkup)
        self.assertIn("Не удалось активировать 7 дней бесплатно", failure_text)
        self.assertIn("поддержку", failure_text)
        self.assertIsInstance(failure_markup, InlineKeyboardMarkup)
        self.assertEqual(failure_markup.inline_keyboard[0][0].callback_data, "act|support_start|_")
        self.assertNotIn("node", failure_text.lower())

    async def test_my_vpn_list_has_direct_subscription_actions(self):
        bot = make_bot()
        subscriptions = [{"id": 42, "display_name": "Work laptop"}]

        markup = bot._configs_list_markup(subscriptions)

        self.assertEqual(markup.inline_keyboard[0][0].text, "1. • Work laptop")
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "act|cfg_open:42|_")
        action_row = markup.inline_keyboard[1]
        self.assertEqual(action_row[0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertEqual(action_row[1].callback_data, "act|cfg_qr:42|_")
        self.assertEqual(action_row[2].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=42&embed=1")
        self.assertEqual(len(markup.inline_keyboard), 2)

    async def test_my_vpn_list_sorts_active_first_and_shows_status_badges(self):
        bot = make_bot()
        subscriptions = [
            expired_subscription(11),
            active_subscription(12, name="Laptop", days=10),
            active_subscription(13, name="Phone", days=1),
        ]

        text = bot._configs_list_text(client_code="VX-000123", subscriptions=subscriptions)
        markup = bot._configs_list_markup(subscriptions)

        self.assertIn("активных: 2", text)
        self.assertIn("скоро закончится: 1", text)
        self.assertIn("истекло: 1", text)
        self.assertIn("Нажмите устройство", text)
        self.assertLess(text.index("скоро закончится Phone"), text.index("активен Laptop"))
        self.assertLess(text.index("активен Laptop"), text.index("истек Old phone"))
        self.assertEqual(markup.inline_keyboard[0][0].text, "1. ⏳ Phone")
        self.assertEqual(markup.inline_keyboard[2][0].text, "2. ✅ Laptop")
        self.assertEqual(markup.inline_keyboard[4][0].text, "3. ⚠️ Old phone")

    async def test_my_vpn_list_puts_renew_first_for_expired_devices(self):
        bot = make_bot()
        subscriptions = [expired_subscription(42)]

        markup = bot._configs_list_markup(subscriptions)

        self.assertEqual(markup.inline_keyboard[0][0].text, "1. ⚠️ Old phone")
        action_row = markup.inline_keyboard[1]
        self.assertEqual(action_row[0].text, "🔄 Продлить")
        self.assertEqual(action_row[0].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=42&embed=1")
        self.assertEqual(action_row[1].text, "📱 Кабинет")
        self.assertEqual(action_row[1].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertEqual(action_row[2].text, "QR")
        self.assertEqual(action_row[2].callback_data, "act|cfg_qr:42|_")

    async def test_my_vpn_single_subscription_opens_card_directly(self):
        db = FakeDB()
        db.subscription_list = [active_subscription(42, name="Phone")]
        bot = make_bot(db)
        message = FakeMessage()
        context = SimpleNamespace(user_data={})

        await bot._send_mysub_for_message(message, user_id=123, context=context)

        self.assertEqual(context.user_data["selected_subscription_id"], 42)
        self.assertEqual(len(message.replies), 1)
        text, markup = message.replies[0]
        self.assertIn("Устройство: Phone", text)
        self.assertNotIn("Выберите устройство", text)
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")

    async def test_my_vpn_empty_state_points_to_mini_app_buy(self):
        bot = make_bot()

        text = bot._configs_list_text(client_code="VX-000123", subscriptions=[])
        markup = bot._configs_list_markup([])

        self.assertIn("VX-000123", text)
        self.assertLess(text.index("Пока нет устройств"), text.index("ID: VX-000123"))
        self.assertIn("7 дней бесплатно", text)
        self.assertIn("купите доступ", text)
        self.assertIn("QR", text)
        self.assertEqual(markup.inline_keyboard[0][0].text, "🎁 7 дней бесплатно")
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "act|start_trial|_")
        self.assertEqual(markup.inline_keyboard[1][0].text, "💳 Купить картой · 249 RUB")
        self.assertEqual(markup.inline_keyboard[1][0].web_app.url, "https://vxcloud.ru/account-app/buy/?embed=1")
        self.assertEqual(markup.inline_keyboard[2][0].text, "⭐ Купить за Stars · 250 Stars")
        self.assertEqual(markup.inline_keyboard[2][0].callback_data, "act|buy_new|_")

    async def test_legacy_myvpn_command_uses_current_empty_my_vpn_flow(self):
        bot = make_bot()
        message = FakeMessage()
        context = SimpleNamespace(user_data={})

        await bot.myvpn(make_update(message), context)

        text, markup = message.replies[-1]
        self.assertIn("Мой VPN", text)
        self.assertIn("Пока нет устройств", text)
        self.assertIn("7 дней бесплатно", text)
        self.assertNotIn("Купить новый доступ", text)
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "act|start_trial|_")

    async def test_legacy_myvpn_command_opens_current_subscription_card(self):
        db = FakeDB()
        db.subscription_list = [active_subscription(42, name="Phone")]
        bot = make_bot(db)
        message = FakeMessage()
        context = SimpleNamespace(user_data={})

        await bot.myvpn(make_update(message), context)

        self.assertEqual(context.user_data["selected_subscription_id"], 42)
        text, markup = message.replies[-1]
        self.assertIn("Устройство: Phone", text)
        self.assertIn("Статус: ✅ активен", text)
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")

    async def test_customer_slash_commands_clear_text_input_state(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage()
        context = SimpleNamespace(
            user_data={
                "support_wait_message": True,
                "rename_wait_subscription_id": 42,
                "buy_wait_phone": True,
                "buy_wait_name": True,
                "buy_phone": "+79990000000",
            }
        )

        await bot.renew(make_update(message), context)

        self.assertNotIn("support_wait_message", context.user_data)
        self.assertNotIn("rename_wait_subscription_id", context.user_data)
        self.assertNotIn("buy_wait_phone", context.user_data)
        self.assertNotIn("buy_wait_name", context.user_data)
        self.assertNotIn("buy_phone", context.user_data)
        self.assertEqual(db.support_messages, [])
        self.assertEqual(db.renamed, [])
        self.assertIn("Продлевать пока нечего", message.replies[-1][0])

    async def test_my_vpn_command_clears_rename_state_before_opening_card(self):
        db = FakeDB()
        db.subscription_list = [active_subscription(42, name="Phone")]
        bot = make_bot(db)
        message = FakeMessage()
        context = SimpleNamespace(user_data={"rename_wait_subscription_id": 42})

        await bot.mysub(make_update(message), context)

        self.assertNotIn("rename_wait_subscription_id", context.user_data)
        self.assertEqual(db.renamed, [])
        self.assertEqual(context.user_data["selected_subscription_id"], 42)
        self.assertIn("Устройство: Phone", message.replies[-1][0])

    async def test_config_card_delete_uses_confirmation_callback(self):
        bot = make_bot()

        markup = await bot._config_card_markup(
            user_id=123,
            subscription_id=42,
            copy_text="https://vxcloud.ru/account/feed/token/",
            can_delete=True,
        )

        self.assertEqual(markup.inline_keyboard[0][0].text, "📱 Открыть кабинет")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "QR")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "act|cfg_qr:42|_")
        self.assertEqual(markup.inline_keyboard[1][1].text, "🔄 Продлить")
        self.assertEqual(markup.inline_keyboard[1][1].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=42&embed=1")
        self.assertEqual(markup.inline_keyboard[2][0].text, "\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443")
        self.assertEqual(markup.inline_keyboard[3][0].text, "\u041f\u0435\u0440\u0435\u0438\u043c\u0435\u043d\u043e\u0432\u0430\u0442\u044c")
        self.assertEqual(markup.inline_keyboard[3][1].text, "\u0423\u0434\u0430\u043b\u0438\u0442\u044c")
        self.assertEqual(markup.inline_keyboard[3][1].callback_data, "act|cfg_delete_request:42|_")
        self.assertEqual(markup.inline_keyboard[4][0].text, "Назад")
        self.assertEqual(markup.inline_keyboard[4][0].callback_data, "act|cfg_back|_")
        self.assertEqual(len(markup.inline_keyboard), 5)

    async def test_expired_config_card_puts_renewal_first(self):
        bot = make_bot()

        markup = await bot._config_card_markup(
            user_id=123,
            subscription_id=42,
            copy_text="https://vxcloud.ru/account/feed/token/",
            can_delete=True,
            renewal_first=True,
        )

        self.assertEqual(markup.inline_keyboard[0][0].text, "🔄 Продлить")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=42&embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "📱 Открыть кабинет")
        self.assertEqual(markup.inline_keyboard[1][0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertEqual(markup.inline_keyboard[1][1].text, "QR")
        self.assertEqual(markup.inline_keyboard[1][1].callback_data, "act|cfg_qr:42|_")
        self.assertEqual(markup.inline_keyboard[3][1].callback_data, "act|cfg_delete_request:42|_")
        self.assertEqual(markup.inline_keyboard[4][0].text, "Назад")
        self.assertEqual(markup.inline_keyboard[4][0].callback_data, "act|cfg_back|_")
        self.assertEqual(len(markup.inline_keyboard), 5)

    async def test_config_card_text_is_compact_and_does_not_print_access_link(self):
        db = FakeDB()
        db.subscriptions[42] = active_subscription(42, name="Phone")
        bot = make_bot(db)

        text, primary_link, _raw = await bot._config_card_text(123, db.subscriptions[42], client_code="VX-000123")

        self.assertIn("Устройство: Phone", text)
        self.assertIn("VX-000123", text)
        self.assertIn("QR", text)
        self.assertIn("Скопировать ссылку", text)
        self.assertEqual(primary_link, "https://vxcloud.ru/account/feed/feed-42/")
        self.assertNotIn("https://vxcloud.ru/account/feed/feed-42/", text)
        self.assertNotIn("vless://", text)

    async def test_config_back_returns_to_my_vpn_list(self):
        db = FakeDB()
        db.subscription_list = [active_subscription(42, name="Phone")]
        bot = make_bot(db)
        query = FakeCallbackQuery("act|cfg_back|_")

        await bot.inline_callback(make_callback_update(query), SimpleNamespace(user_data={}))

        self.assertIn("Мой VPN", query.edits[-1][0])
        self.assertIn("Phone", query.edits[-1][0])
        self.assertEqual(query.edits[-1][1].inline_keyboard[0][0].callback_data, "act|cfg_open:42|_")

    async def test_expired_config_card_text_points_to_renewal(self):
        db = FakeDB()
        db.subscriptions[42] = expired_subscription(42)
        bot = make_bot(db)

        text, _primary_link, _raw = await bot._config_card_text(123, db.subscriptions[42], client_code="VX-000123")

        self.assertIn("Статус: ⚠️ истек", text)
        self.assertIn("Доступ истёк", text)
        self.assertIn("🔄 Продлить", text)
        self.assertIn("снова включить VPN", text)
        self.assertNotIn("QR и кнопка", text)

    async def test_expiring_config_card_text_recommends_early_renewal(self):
        db = FakeDB()
        db.subscriptions[42] = active_subscription(42, name="Phone", days=1)
        bot = make_bot(db)

        text, _primary_link, _raw = await bot._config_card_text(123, db.subscriptions[42], client_code="VX-000123")

        self.assertIn("Статус: ⏳ скоро закончится", text)
        self.assertIn("Продлите заранее", text)
        self.assertIn("VPN не отключился", text)
        self.assertNotIn("QR и кнопка", text)

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
        self.assertNotIn("https://vxcloud.ru/account/feed/feed-token/", query.message.photos[0][1])
        self.assertNotIn("vless://", query.message.photos[0][1])
        self.assertIsInstance(query.message.photos[0][2], InlineKeyboardMarkup)
        self.assertEqual(query.message.photos[0][2].inline_keyboard[0][0].text, "📱 Открыть кабинет")

    async def test_expired_qr_caption_warns_and_puts_renewal_first(self):
        db = FakeDB()
        db.subscriptions[42] = {
            **expired_subscription(42),
            "feed_token": "feed-token",
            "vless_url": "vless://raw-config@example.test:443#raw",
        }
        bot = make_bot(db)

        def fake_build_qr(data, title):
            del data, title
            return FakeQrImage()

        bot._build_styled_qr = fake_build_qr
        query = FakeCallbackQuery("act|cfg_qr:42|_")

        await bot.inline_callback(make_callback_update(query), SimpleNamespace(user_data={}))

        self.assertEqual(len(query.message.photos), 1)
        _photo, caption, markup = query.message.photos[0]
        self.assertIn("Доступ истёк", caption)
        self.assertIn("после продления", caption)
        self.assertIsInstance(markup, InlineKeyboardMarkup)
        self.assertEqual(markup.inline_keyboard[0][0].text, "🔄 Продлить")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=42&embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "📱 Открыть кабинет")

    async def test_delete_request_shows_confirmation_without_deleting(self):
        db = FakeDB()
        db.subscriptions[42] = expired_subscription()
        bot = make_bot(db)
        query = FakeCallbackQuery("act|cfg_delete_request:42|_")

        await bot.inline_callback(make_callback_update(query), SimpleNamespace(user_data={}))

        self.assertEqual(db.deleted, [])
        self.assertEqual(bot.xui.deleted, [])
        self.assertIn("\u0423\u0434\u0430\u043b\u0438\u0442\u044c Old phone?", query.edits[-1][0])
        self.assertIn("Это устройство больше не будет отображаться", query.edits[-1][0])
        self.assertIn("Активный доступ удалить нельзя", query.edits[-1][0])
        self.assertNotIn("3x-ui", query.edits[-1][0])
        self.assertNotIn("VPN-нод", query.edits[-1][0])
        self.assertNotIn("конфигурация", query.edits[-1][0])
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
            ("Активный доступ удалить нельзя", True),
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
        self.assertEqual(query.answers[-1], ("Устройство удалено", False))
        self.assertEqual(query.edits[-1][1].inline_keyboard[-1][0].callback_data, "act|buy_new|_")

    async def test_reminder_defaults_use_access_wording_not_config_wording(self):
        db = FakeDB()
        db.reminders = [
            {
                "id": 42,
                "telegram_id": 999,
                "display_name": "Phone",
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=12),
            }
        ]
        bot = make_bot(db)
        telegram_bot = FakeTelegramBot()
        bot.app.bot = telegram_bot

        await bot.reminder_tick()

        self.assertEqual(db.logged_reminders, [(42, "1d")])
        self.assertEqual(len(telegram_bot.messages), 1)
        _chat_id, text, markup = telegram_bot.messages[0]
        self.assertIn("Доступ VXcloud скоро закончится", text)
        self.assertIn("Устройство: Phone", text)
        self.assertIn("Продлите заранее", text)
        self.assertIsInstance(markup, InlineKeyboardMarkup)
        self.assertEqual(markup.inline_keyboard[0][0].text, "🔄 Продлить")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=42&embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].text, "📱 Кабинет")
        self.assertEqual(markup.inline_keyboard[1][0].web_app.url, "https://vxcloud.ru/account-app/config/42/?embed=1")
        self.assertNotIn("конфиг", text.lower())

    async def test_expired_reminder_has_direct_renew_action(self):
        db = FakeDB()
        db.reminders = [
            {
                "id": 43,
                "telegram_id": 999,
                "display_name": "",
                "expires_at": datetime.now(timezone.utc) - timedelta(hours=1),
            }
        ]
        bot = make_bot(db)
        telegram_bot = FakeTelegramBot()
        bot.app.bot = telegram_bot

        await bot.reminder_tick()

        self.assertEqual(db.logged_reminders, [(43, "expired")])
        _chat_id, text, markup = telegram_bot.messages[0]
        self.assertIn("Доступ VXcloud истёк", text)
        self.assertIn("Устройство #43", text)
        self.assertIn("снова включить VPN", text)
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/renew/?subscription_id=43&embed=1")
        self.assertNotIn("/buy", text)

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
        self.assertIn("Продлить доступ", message.replies[-1][0])
        self.assertIn("Выберите устройство", message.replies[-1][0])
        markup = message.replies[-1][1]
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "act|renew_select:11|_")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "act|renew_select:12|_")
        self.assertEqual(markup.inline_keyboard[-1][0].web_app.url, "https://vxcloud.ru/account-app/renew/?embed=1")

    async def test_renew_selection_sorts_active_first_and_shows_status_badges(self):
        db = FakeDB()
        db.subscription_list = [
            expired_subscription(11),
            active_subscription(12, name="Laptop", days=10),
            active_subscription(13, name="Phone", days=1),
        ]
        bot = make_bot(db)
        message = FakeMessage()
        context = SimpleNamespace(user_data={})

        await bot._show_renew_offer(message, user_id=123, context=context)

        text = message.replies[-1][0]
        self.assertLess(text.index("скоро закончится Phone"), text.index("активен Laptop"))
        self.assertLess(text.index("активен Laptop"), text.index("истек Old phone"))
        markup = message.replies[-1][1]
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "act|renew_select:13|_")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "act|renew_select:12|_")
        self.assertEqual(markup.inline_keyboard[2][0].callback_data, "act|renew_select:11|_")

    async def test_renew_without_active_access_is_app_first_buy(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage()
        context = SimpleNamespace(user_data={})

        await bot._show_renew_offer(message, user_id=123, context=context)

        text = message.replies[-1][0]
        self.assertIn("Продлевать пока нечего", text)
        self.assertIn("7 дней бесплатно", text)
        self.assertIn("новый доступ", text)
        markup = message.replies[-1][1]
        self.assertEqual(markup.inline_keyboard[0][0].text, "🎁 7 дней бесплатно")
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "act|start_trial|_")
        self.assertEqual(markup.inline_keyboard[1][0].text, "💳 Купить картой · 249 RUB")
        self.assertEqual(markup.inline_keyboard[1][0].web_app.url, "https://vxcloud.ru/account-app/buy/?embed=1")
        self.assertEqual(markup.inline_keyboard[2][0].callback_data, "act|buy_new|_")
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
        self.assertEqual(markup.inline_keyboard[1][0].text, "⭐ Продлить за Stars · 250 Stars")
        self.assertEqual(markup.inline_keyboard[2][0].text, "Назад")
        self.assertEqual(markup.inline_keyboard[2][0].callback_data, "act|renew_back|_")
        self.assertEqual(len(markup.inline_keyboard), 3)

    async def test_renew_back_returns_to_subscription_selection_when_multiple(self):
        db = FakeDB()
        db.subscription_list = [
            {**expired_subscription(11), "display_name": "Phone"},
            {**expired_subscription(12), "display_name": "Laptop"},
        ]
        bot = make_bot(db)
        query = FakeCallbackQuery("act|renew_back|_")
        context = SimpleNamespace(user_data={"selected_subscription_id": 12})

        await bot.inline_callback(make_callback_update(query), context)

        self.assertNotIn("selected_subscription_id", context.user_data)
        self.assertIn("Выберите устройство", query.edits[-1][0])
        self.assertEqual(query.edits[-1][1].inline_keyboard[0][0].callback_data, "act|renew_select:11|_")
        self.assertEqual(query.edits[-1][1].inline_keyboard[1][0].callback_data, "act|renew_select:12|_")

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
        self.assertIn("Картой", text)
        self.assertIn("Stars", text)
        self.assertNotIn("на сайте", text)

    async def test_instructions_hub_uses_short_webapp_device_choices(self):
        bot = make_bot()

        markup = bot._node_inline_keyboard("menu_instructions")

        self.assertEqual(bot._node_response_text("menu_instructions"), "\u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f\n\n\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u043e. \u041f\u043e\u043b\u043d\u0430\u044f \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f \u043e\u0442\u043a\u0440\u043e\u0435\u0442\u0441\u044f \u0432 \u043a\u0430\u0431\u0438\u043d\u0435\u0442\u0435 \u0432\u043d\u0443\u0442\u0440\u0438 Telegram.")
        self.assertEqual(markup.inline_keyboard[0][0].text, "iPhone")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/?view=instructions&device=iphone&embed=1")
        self.assertEqual(markup.inline_keyboard[1][0].web_app.url, "https://vxcloud.ru/account-app/?view=instructions&device=android&embed=1")
        self.assertEqual(markup.inline_keyboard[2][0].web_app.url, "https://vxcloud.ru/account-app/?view=instructions&device=desktop&embed=1")
        self.assertEqual(markup.inline_keyboard[3][0].web_app.url, "https://vxcloud.ru/account-app/?view=instructions&embed=1")
        self.assertEqual(len(markup.inline_keyboard), 4)

    async def test_legacy_install_instructions_open_full_guide_in_mini_app(self):
        bot = make_bot()

        markup = bot._node_inline_keyboard("instructions_install")

        self.assertEqual(
            bot._node_response_text("instructions_install"),
            "\u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f\n\n\u041e\u0442\u043a\u0440\u043e\u0439\u0442\u0435 \u043f\u043e\u043b\u043d\u0443\u044e \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044e \u0432 \u043a\u0430\u0431\u0438\u043d\u0435\u0442\u0435. \u0422\u0430\u043c \u0441\u043e\u0431\u0440\u0430\u043d\u044b \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u044f, QR \u0438 \u0434\u0430\u043d\u043d\u044b\u0435 \u0434\u043e\u0441\u0442\u0443\u043f\u0430.",
        )
        self.assertEqual(markup.inline_keyboard[0][0].text, "Полная инструкция")
        self.assertEqual(markup.inline_keyboard[0][0].web_app.url, "https://vxcloud.ru/account-app/?view=instructions&embed=1")
        self.assertIsNone(markup.inline_keyboard[0][0].url)
        self.assertEqual(markup.inline_keyboard[1][0].text, "Назад")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "nav|menu_instructions|_")
        self.assertEqual(len(markup.inline_keyboard), 2)

    async def test_support_hub_offers_quick_message_and_mini_app(self):
        bot = make_bot()

        markup = bot._support_hub_markup()

        self.assertEqual(markup.inline_keyboard[0][0].text, "✍️ Написать")
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "act|support_start|_")
        self.assertEqual(markup.inline_keyboard[1][0].text, "📱 Поддержка в кабинете")
        self.assertEqual(markup.inline_keyboard[1][0].web_app.url, "https://vxcloud.ru/account-app/?view=support&embed=1")
        self.assertEqual(len(markup.inline_keyboard), 2)

    async def test_show_support_hub_uses_contextual_inline_markup(self):
        bot = make_bot()
        message = FakeMessage()

        await bot._show_support_hub(message, user_id=123)

        self.assertIn("\u0412\u0430\u0448 ID: VX-000123", message.replies[0][0])
        self.assertIn("\u041e\u043f\u0438\u0448\u0438\u0442\u0435 \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u0443 \u043e\u0434\u043d\u0438\u043c \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435\u043c", message.replies[0][0])
        self.assertIn("Поддержка", message.replies[0][0])
        self.assertIsInstance(message.replies[0][1], InlineKeyboardMarkup)
        self.assertEqual(message.replies[0][1].inline_keyboard[1][0].web_app.url, "https://vxcloud.ru/account-app/?view=support&embed=1")

    async def test_support_start_hides_main_menu_and_shows_cancel_keyboard(self):
        bot = make_bot()
        query = FakeCallbackQuery("act|support_start|_")
        context = SimpleNamespace(user_data={})

        await bot.inline_callback(make_callback_update(query), context)

        self.assertTrue(context.user_data["support_wait_message"])
        self.assertEqual(bot.db.events[-1]["event_name"], "support_started")
        self.assertIn("\u043e\u0434\u043d\u0438\u043c \u0442\u0435\u043a\u0441\u0442\u043e\u043c", query.message.replies[-1][0])
        self.assertIn("Отмена", query.message.replies[-1][0])
        markup = query.message.replies[-1][1]
        self.assertIsInstance(markup, ReplyKeyboardMarkup)
        self.assertEqual([[button.text for button in row] for row in markup.keyboard], [["Отмена"]])

    async def test_support_message_submission_restores_main_menu(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage("Need help")
        context = SimpleNamespace(user_data={"support_wait_message": True})

        await bot.menu_click(make_update(message), context)

        self.assertNotIn("support_wait_message", context.user_data)
        self.assertEqual(db.support_messages, [(77, "user", 123, "Need help")])
        self.assertEqual(db.events[-1]["event_name"], "support_sent")
        self.assertIn("Номер обращения: #77", message.replies[-1][0])
        self.assertIn("\u041e\u0442\u0432\u0435\u0442 \u043f\u0440\u0438\u0434\u0435\u0442 \u0441\u044e\u0434\u0430", message.replies[-1][0])
        self.assertIn("📱 Кабинет", message.replies[-1][0])
        self.assertIn("\u0412\u0430\u0448 ID: VX-000123", message.replies[-1][0])
        self.assertIsInstance(message.replies[-1][1], ReplyKeyboardMarkup)

    async def test_support_received_copy_is_ticket_oriented_and_menu_safe(self):
        bot = make_bot()

        text = bot._support_received_text(ticket_id=77, client_code="VX-000123")

        self.assertIn("Номер обращения: #77", text)
        self.assertIn("Ответ придет сюда в Telegram", text)
        self.assertIn("Историю обращений", text)
        self.assertIn("📱 Кабинет", text)
        self.assertIn("Ваш ID: VX-000123", text)
        self.assertNotIn("Mini App", text)

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

    async def test_too_long_support_message_keeps_input_state_and_cancel_keyboard(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage("x" * 2001)
        context = SimpleNamespace(user_data={"support_wait_message": True})

        await bot.menu_click(make_update(message), context)

        self.assertTrue(context.user_data["support_wait_message"])
        self.assertEqual(db.support_messages, [])
        self.assertEqual(db.events, [])
        text, markup = message.replies[-1]
        self.assertIn("Сообщение слишком длинное", text)
        self.assertIn("2000", text)
        self.assertIn("Отмена", text)
        self.assertIsInstance(markup, ReplyKeyboardMarkup)
        self.assertEqual([[button.text for button in row] for row in markup.keyboard], [["Отмена"]])

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
        self.assertIn("7 дней бесплатно", message.replies[-1][0])

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

    async def test_rename_request_hides_main_menu_and_shows_cancel_keyboard(self):
        bot = make_bot()
        query = FakeCallbackQuery("act|cfg_rename:42|_")
        context = SimpleNamespace(user_data={})

        await bot.inline_callback(make_callback_update(query), context)

        self.assertEqual(context.user_data["rename_wait_subscription_id"], 42)
        self.assertIn("Отмена", query.message.replies[-1][0])
        markup = query.message.replies[-1][1]
        self.assertIsInstance(markup, ReplyKeyboardMarkup)
        self.assertEqual([[button.text for button in row] for row in markup.keyboard], [["Отмена"]])

    async def test_rename_submission_restores_main_menu(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage("Work\n   laptop")
        context = SimpleNamespace(user_data={"rename_wait_subscription_id": 42})

        await bot.menu_click(make_update(message), context)

        self.assertNotIn("rename_wait_subscription_id", context.user_data)
        self.assertEqual(db.renamed, [(123, 42, "Work laptop")])
        self.assertTrue(any(isinstance(reply_markup, ReplyKeyboardMarkup) for _text, reply_markup in message.replies))

    async def test_too_long_rename_keeps_input_state_and_cancel_keyboard(self):
        db = FakeDB()
        bot = make_bot(db)
        message = FakeMessage("x" * 41)
        context = SimpleNamespace(user_data={"rename_wait_subscription_id": 42})

        await bot.menu_click(make_update(message), context)

        self.assertEqual(context.user_data["rename_wait_subscription_id"], 42)
        self.assertEqual(db.renamed, [])
        text, markup = message.replies[-1]
        self.assertIn("Имя слишком длинное", text)
        self.assertIn("40", text)
        self.assertIn("Отмена", text)
        self.assertIsInstance(markup, ReplyKeyboardMarkup)
        self.assertEqual([[button.text for button in row] for row in markup.keyboard], [["Отмена"]])

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
        self.assertIn("7 дней бесплатно", message.replies[-1][0])


if __name__ == "__main__":
    unittest.main()
