import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"
if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vxcloud_site.settings")

import django

django.setup()

from django.contrib.auth.models import User
from django.test import Client

from blog.models import SiteText
from backoffice.views import BOT_CONTENT_SECTIONS


def _bot_content_items():
    return [item for section in BOT_CONTENT_SECTIONS for item in section["items"]]


class BackofficeBotContentEditorUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.staff_user, _ = User.objects.get_or_create(
            username="ops_bot_content_staff",
            defaults={
                "email": "ops-bot-content@example.com",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        self.staff_user.is_staff = True
        self.staff_user.is_superuser = True
        self.staff_user.set_password("pass12345")
        self.staff_user.save()
        self.client = Client()
        assert self.client.login(username="ops_bot_content_staff", password="pass12345")

    def test_post_saves_and_clears_bot_overrides(self):
        SiteText.objects.update_or_create(key="bot.menu_buy", defaults={"value": "Старое значение"})

        response = self.client.post(
            "/ops/bot/content/",
            data={
                "menu_buy_access": "Новый текст кнопки",
                "copy_link_hint": "Новая подсказка",
                "menu_trial": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(SiteText.objects.get(key="bot.menu_buy_access").value, "Новый текст кнопки")
        self.assertFalse(SiteText.objects.filter(key="bot.menu_buy").exists())
        self.assertEqual(SiteText.objects.get(key="bot.copy_link_hint").value, "Новая подсказка")
        self.assertFalse(SiteText.objects.filter(key="bot.menu_trial").exists())

    def test_bot_menu_editor_exposes_current_menu_keys_only(self):
        menu_section = BOT_CONTENT_SECTIONS[0]
        keys = [item["key"] for item in menu_section["items"]]
        defaults = {item["key"]: item["default"] for item in menu_section["items"]}

        self.assertEqual(
            keys,
            [
                "menu_my_vpn",
                "menu_trial",
                "menu_buy_access",
                "menu_renew_access",
                "menu_support_simple",
                "menu_open_app",
            ],
        )
        self.assertEqual(defaults["menu_trial"], "🎁 7 дней бесплатно")
        self.assertEqual(defaults["menu_open_app"], "📱 Кабинет")
        self.assertNotIn("menu_site", keys)
        self.assertNotIn("back_button", keys)

    def test_bot_editor_hides_obsolete_instruction_site_keys(self):
        keys = {item["key"] for item in _bot_content_items()}

        for stale_key in {
            "back_button",
            "instructions_access_button",
            "instructions_full_guide_button",
            "instructions_install_button",
            "instructions_support_button",
            "instructions_video_button",
            "menu_site",
            "menu_site_response",
            "site_about_buttons",
            "site_about_response",
        }:
            self.assertNotIn(stale_key, keys)

        self.assertIn("menu_instructions_response", keys)
        self.assertIn("instructions_install_response", keys)

    def test_bot_editor_defaults_match_current_mini_app_first_copy(self):
        defaults = {item["key"]: item.get("default", "") for item in _bot_content_items()}

        self.assertEqual(
            defaults["menu_instructions_response"],
            "Инструкция\n\nВыберите устройство. Полная инструкция откроется в кабинете внутри Telegram.",
        )
        self.assertIn("После оплаты доступ появится в «🛡 Мой VPN»", defaults["stars_only_notice"])
        self.assertIn("срок обновится автоматически", defaults["stars_renew_notice"])
        self.assertEqual(defaults["invoice_description"], "Покупка доступа VXcloud через Telegram Stars.")
        self.assertEqual(defaults["invoice_renew_description"], "Продление доступа VXcloud через Telegram Stars.")
        self.assertIn("Номер обращения: #{ticket_id}", defaults["support_received_message"])
        self.assertIn("📱 Кабинет", defaults["support_received_message"])
        self.assertNotIn("мобильный баланс", defaults["stars_only_notice"].lower())
        self.assertNotIn("мобильный баланс", defaults["invoice_description"].lower())

    def test_post_clears_obsolete_bot_instruction_site_overrides(self):
        for stale_key in ("menu_site_response", "site_about_response", "instructions_video_button"):
            SiteText.objects.update_or_create(key=f"bot.{stale_key}", defaults={"value": "old"})

        response = self.client.post("/ops/bot/content/", data={})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(SiteText.objects.filter(key="bot.menu_site_response").exists())
        self.assertFalse(SiteText.objects.filter(key="bot.site_about_response").exists())
        self.assertFalse(SiteText.objects.filter(key="bot.instructions_video_button").exists())


if __name__ == "__main__":
    unittest.main()
