import os
import sys
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"
if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vxcloud_site.settings")

import django

django.setup()

from django.contrib.auth.models import User
from django.db import DatabaseError
from django.test import Client, RequestFactory
from django.utils import timezone
from unittest.mock import patch

from cabinet.views import (
    _build_public_absolute_url,
    _resolve_renew_target_subscription_id,
    _vpn_public_host,
    _vpn_public_port,
)


class AccountAppStateResilienceUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user, created = User.objects.get_or_create(
            username="account_state_resilience",
            defaults={"email": "account_state_resilience@example.com"},
        )
        self.user.set_password("pass12345")
        self.user.save()
        self.client = Client()
        assert self.client.login(username="account_state_resilience", password="pass12345")
        self.factory = RequestFactory()

    def test_account_state_returns_empty_dashboard_when_bot_backend_errors(self):
        with patch("cabinet.views._resolve_account_bot_user", side_effect=DatabaseError("users table unavailable")):
            response = self.client.get("/account-app/api/state/?view=dashboard")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["view"], "dashboard")
        dashboard = payload["dashboard"]
        self.assertEqual(dashboard["user"]["username"], "account_state_resilience")
        self.assertEqual(dashboard["access_count"], 0)
        self.assertEqual(dashboard["subscriptions"], [])
        self.assertEqual(dashboard["stats"]["active_configs"], 0)
        self.assertEqual(dashboard["telegram"]["linked"], False)

    def test_build_public_absolute_url_prefers_forwarded_https(self):
        request = self.factory.get(
            "/account/",
            HTTP_HOST="vxcloud.ru",
            HTTP_X_FORWARDED_PROTO="https",
        )
        self.assertEqual(
            _build_public_absolute_url(request, "/auth/telegram/login/"),
            "https://vxcloud.ru/auth/telegram/login/",
        )

    def test_account_state_returns_link_payload_for_link_view(self):
        with patch.dict("os.environ", {"TELEGRAM_BOT_USERNAME": "vxcloud_test_bot"}):
            response = self.client.get("/account-app/api/state/?view=link")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["view"], "link")
        self.assertIn("link_code", payload["link"])
        self.assertIn("https://t.me/vxcloud_test_bot?start=link_", payload["link"]["deep_link"])

    def test_account_state_returns_support_payload_for_support_view(self):
        with patch.dict("os.environ", {"TELEGRAM_BOT_USERNAME": "vxcloud_test_bot"}):
            response = self.client.get("/account-app/api/state/?view=support")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["view"], "support")
        self.assertEqual(payload["support"]["title"], "Поддержка")
        self.assertIn("Telegram", payload["support"]["subtitle"])
        self.assertEqual(payload["support"]["telegram_url"], "https://t.me/vxcloud_test_bot")
        self.assertEqual(payload["support"]["instructions_url"], "/account-app/?view=instructions&embed=1")

    def test_account_state_support_payload_includes_client_code(self):
        with patch("cabinet.views._resolve_account_bot_user") as resolve_mock:
            resolve_mock.return_value = (
                None,
                SimpleNamespace(id=7, client_code="VX-000007"),
            )
            response = self.client.get("/account-app/api/state/?view=support")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["support"]["client_code"], "VX-000007")

    def test_account_state_returns_instructions_payload_for_instructions_view(self):
        response = self.client.get("/account-app/api/state/?view=instructions&device=iphone&embed=1")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["view"], "instructions")
        self.assertEqual(payload["instructions"]["title"], "Подключение")
        self.assertEqual(
            payload["instructions"]["subtitle"],
            "Скопируйте ссылку подписки и импортируйте ее в VPN-приложение.",
        )
        self.assertEqual(payload["instructions"]["device"], "iphone")
        self.assertEqual(
            payload["instructions"]["devices"][0]["url"],
            "/account-app/?view=instructions&device=iphone&embed=1",
        )
        self.assertEqual(payload["instructions"]["dashboard_url"], "/account-app/?embed=1")
        self.assertEqual(payload["instructions"]["support_url"], "/account-app/?view=support&embed=1")
        self.assertIsNone(payload["instructions"]["primary_subscription"])
        self.assertEqual(payload["instructions"]["access_count"], 0)

    def test_account_state_instructions_payload_includes_primary_subscription_cta(self):
        bot_user = SimpleNamespace(id=7, client_code="VX-000007")
        subscription = SimpleNamespace(
            id=42,
            display_name="Phone",
            expires_at=timezone.now() + timedelta(days=7),
            is_active=True,
            revoked_at=None,
            user=bot_user,
            vless_url="vless://example",
            feed_token="feed-token",
        )
        with patch("cabinet.views._resolve_account_bot_user", return_value=(None, bot_user)):
            with patch("cabinet.views._list_subscriptions_for_bot_user", return_value=[subscription]):
                response = self.client.get("/account-app/api/state/?view=instructions&device=android&embed=1")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["instructions"]["access_count"], 1)
        self.assertEqual(payload["instructions"]["primary_subscription"]["id"], 42)
        self.assertEqual(payload["instructions"]["primary_subscription"]["display_name"], "Phone")
        self.assertEqual(payload["instructions"]["primary_subscription"]["config_url"], "/account/config/42/")
        self.assertIn("/account/feed/feed-token/", payload["instructions"]["primary_subscription"]["feed_url"])

    def test_account_app_support_view_renders_support_hub(self):
        with patch.dict("os.environ", {"TELEGRAM_BOT_USERNAME": "vxcloud_test_bot"}):
            with patch("cabinet.views._resolve_account_bot_user") as resolve_mock:
                resolve_mock.return_value = (
                    None,
                    SimpleNamespace(id=7, client_code="VX-000007"),
                )
                with patch("cabinet.views._get_subscription_snapshot_for_bot_user", return_value=(None, False, None)):
                    with patch("cabinet.views._list_subscriptions_for_bot_user", return_value=[]):
                        response = self.client.get("/account-app/?view=support&embed=1")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Поддержка VXcloud", html)
        self.assertIn("Написать в Telegram", html)
        self.assertIn("Открыть инструкцию", html)
        self.assertIn("/account-app/?view=instructions&amp;embed=1", html)
        self.assertNotIn('href="/instructions/"', html)
        self.assertNotIn("Support hub", html)
        self.assertNotIn("Write in Telegram", html)
        self.assertNotIn("Open full guide", html)
        self.assertIn("VX-000007", html)
        self.assertIn("https://t.me/vxcloud_test_bot", html)

    def test_account_app_instructions_view_renders_device_guide(self):
        with patch("cabinet.views._resolve_account_bot_user") as resolve_mock:
            resolve_mock.return_value = (
                None,
                SimpleNamespace(id=7, client_code="VX-000007"),
            )
            with patch("cabinet.views._get_subscription_snapshot_for_bot_user", return_value=(None, False, None)):
                with patch("cabinet.views._list_subscriptions_for_bot_user", return_value=[]):
                    response = self.client.get("/account-app/?view=instructions&device=android&embed=1")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Подключение", html)
        self.assertIn("Скопируйте ссылку подписки", html)
        self.assertIn("Android", html)
        self.assertIn("v2rayNG", html)
        self.assertIn("account-page-shell-instructions", html)
        self.assertIn("account-instructions-device-actions", html)
        self.assertIn("account-step-list", html)
        self.assertIn("<li>Откройте свой доступ", html)
        self.assertIn("/account-app/?view=instructions&amp;device=iphone&amp;embed=1", html)
        self.assertNotIn("Кабинет VXcloud", html)
        self.assertNotIn("Ваши доступы", html)
        self.assertNotIn("Open full guide", html)

    def test_account_app_instructions_view_has_copy_link_cta_when_access_exists(self):
        bot_user = SimpleNamespace(id=7, client_code="VX-000007")
        subscription = SimpleNamespace(
            id=42,
            display_name="Phone",
            expires_at=timezone.now() + timedelta(days=7),
            is_active=True,
            revoked_at=None,
            user=bot_user,
            vless_url="vless://example",
            feed_token="feed-token",
        )
        with patch("cabinet.views._resolve_account_bot_user", return_value=(None, bot_user)):
            with patch("cabinet.views._get_subscription_snapshot_for_bot_user", return_value=(subscription, True, None)):
                with patch("cabinet.views._list_subscriptions_for_bot_user", return_value=[subscription]):
                    response = self.client.get("/account-app/?view=instructions&device=iphone&embed=1")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Скопировать ссылку", html)
        self.assertIn("js-copy-config", html)
        self.assertIn("/account/feed/feed-token/", html)
        self.assertIn("data-copy-text=", html)

    def test_account_app_dashboard_copy_is_localized(self):
        bot_user = SimpleNamespace(id=7, client_code="VX-000007")
        subscription = SimpleNamespace(
            id=42,
            display_name="Phone",
            expires_at=timezone.now() + timedelta(days=7),
            is_active=True,
            revoked_at=None,
            user=bot_user,
            vless_url="vless://example",
            feed_token="feed-token",
        )
        with patch("cabinet.views._resolve_account_bot_user", return_value=(None, bot_user)):
            with patch("cabinet.views._get_subscription_snapshot_for_bot_user", return_value=(subscription, True, None)):
                with patch("cabinet.views._list_subscriptions_for_bot_user", return_value=[subscription]):
                    response = self.client.get("/account-app/?embed=1")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Мой VPN", html)
        self.assertIn("Ваши доступы", html)
        self.assertIn("Скопировать ссылку", html)
        self.assertIn("Подключение через ссылку", html)
        self.assertIn("импорт из буфера", html)
        self.assertNotIn("VXcloud account", html)
        self.assertNotIn("Devices", html)
        self.assertNotIn("Subscription URL", html)
        self.assertNotIn("online", html)

    def test_account_app_dashboard_active_user_gets_access_first(self):
        bot_user = SimpleNamespace(id=7, client_code="VX-000007")
        subscription = SimpleNamespace(
            id=42,
            display_name="Phone",
            expires_at=timezone.now() + timedelta(days=7),
            is_active=True,
            revoked_at=None,
            user=bot_user,
            vless_url="vless://example",
            feed_token="feed-token",
        )
        with patch("cabinet.views._resolve_account_bot_user", return_value=(None, bot_user)):
            with patch("cabinet.views._get_subscription_snapshot_for_bot_user", return_value=(subscription, True, None)):
                with patch("cabinet.views._list_subscriptions_for_bot_user", return_value=[subscription]):
                    response = self.client.get("/account-app/?embed=1")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        actions_html = html.split('class="account-mini-actions"', 1)[1].split("</section>", 1)[0]
        self.assertIn("/open-app/?mode=ios-auto", actions_html)
        self.assertIn("u=http%3A%2F%2Ftestserver%2Faccount%2Ffeed%2Ffeed-token%2F", actions_html)
        self.assertIn("/account-app/config/42/", actions_html)
        self.assertLess(actions_html.index("Подключить"), actions_html.index("QR и доступ"))

    def test_account_app_dashboard_empty_state_is_trial_first_when_bot_exists(self):
        bot_user = SimpleNamespace(id=7, client_code="VX-000007")
        with patch.dict("os.environ", {"TELEGRAM_BOT_USERNAME": "vxcloud_test_bot"}):
            with patch("cabinet.views._resolve_account_bot_user", return_value=(None, bot_user)):
                with patch("cabinet.views._get_subscription_snapshot_for_bot_user", return_value=(None, False, None)):
                    with patch("cabinet.views._list_subscriptions_for_bot_user", return_value=[]):
                        response = self.client.get("/account-app/?embed=1")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("https://t.me/vxcloud_test_bot?start=trial", html)
        empty_html = html.split('class="account-mini-empty"', 1)[1].split("</div>", 1)[0]
        self.assertIn("Без карты", empty_html)
        self.assertLess(empty_html.index("7 дней бесплатно"), empty_html.index("Купить доступ"))

    def test_account_app_config_copy_is_localized(self):
        bot_user = SimpleNamespace(id=7, client_code="VX-000007")
        subscription = SimpleNamespace(
            id=42,
            display_name="Phone",
            expires_at=timezone.now() + timedelta(days=7),
            is_active=True,
            revoked_at=None,
            user=bot_user,
            vless_url="vless://example",
            feed_token="feed-token",
        )
        with patch("cabinet.views._resolve_account_bot_user", return_value=(None, bot_user)):
            with patch("cabinet.views._get_subscription_snapshot_for_bot_user", return_value=(subscription, True, None)):
                with patch("cabinet.views._list_subscriptions_for_bot_user", return_value=[subscription]):
                    response = self.client.get("/account-app/config/42/?embed=1")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("QR для импорта", html)
        self.assertIn("Скопировать ссылку", html)
        self.assertIn("Основной способ подключения", html)
        self.assertIn("импорт из буфера", html)
        self.assertIn("Состояние", html)
        self.assertIn("Состояние доступа", html)
        self.assertIn("Все доступы", html)
        self.assertIn("Ссылка подписки", html)
        self.assertIn("account-page-shell-config", html)
        self.assertIn("account-config-link-section", html)
        self.assertIn("account-config-status-section", html)
        self.assertNotIn("QR import", html)
        self.assertNotIn("Subscription URL", html)
        self.assertNotIn("Status", html)

    def test_account_app_install_detects_device_and_lists_requested_apps(self):
        bot_user = SimpleNamespace(id=7, client_code="VX-000007")
        subscription = SimpleNamespace(
            id=42,
            display_name="Phone",
            expires_at=timezone.now() + timedelta(days=7),
            is_active=True,
            revoked_at=None,
            user=bot_user,
            vless_url="vless://example",
            feed_token="feed-token",
        )
        with patch("cabinet.views._resolve_account_bot_user", return_value=(None, bot_user)):
            with patch("cabinet.views._list_subscriptions_for_bot_user", return_value=[subscription]):
                response = self.client.get("/account-app/install/42/?embed=1")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Подключить Phone", html)
        self.assertIn("Большинства этих приложений нет в российском App Store", html)
        self.assertIn("https://support.apple.com/en-us/118283", html)
        self.assertIn("Streisand", html)
        self.assertIn('"manual_note"', html)
        self.assertIn("v2box://install-sub", html)
        self.assertIn("\"autostart\": true", html)
        self.assertNotIn("shouldAutoStart", html)
        self.assertIn("V2Box", html)
        self.assertIn("Shadowrocket", html)
        self.assertIn("v2rayNG", html)
        self.assertIn("V2RayRun", html)
        self.assertIn("Furious", html)
        self.assertIn("У меня другое приложение", html)
        self.assertIn("/open-app/?mode=ios-auto", html)
        self.assertIn("data-access-url=\"http://testserver/account/feed/feed-token/\"", html)
        self.assertNotIn("Конфиг и QR", html)
        self.assertNotIn("Состояние конфига", html)
        self.assertNotIn("Все конфиги", html)

    def test_open_app_auto_import_preserves_nested_encoded_url(self):
        response = self.client.get(
            "/open-app/",
            {
                "mode": "ios-auto",
                "u": "https://vxcloud.ru/account/feed/feed-token/",
            },
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        streisand_url = "streisand://import/https://vxcloud.ru/account/feed/feed-token/#VXcloud"
        v2box_url = "v2box://install-sub?url=https%3A%2F%2Fvxcloud.ru%2Faccount%2Ffeed%2Ffeed-token%2F&amp;name=VXcloud"
        shadowrocket_url = "shadowrocket://add/https%3A%2F%2Fvxcloud.ru%2Faccount%2Ffeed%2Ffeed-token%2F"
        v2raytun_url = "v2raytun://import/https://vxcloud.ru/account/feed/feed-token/"
        happ_url = "happ://add/https://vxcloud.ru/account/feed/feed-token/"
        hiddify_url = "hiddify://install-config/?url=https%3A%2F%2Fvxcloud.ru%2Faccount%2Ffeed%2Ffeed-token%2F"
        self.assertIn(streisand_url, html)
        self.assertIn(v2box_url, html)
        self.assertIn(shadowrocket_url, html)
        self.assertIn(v2raytun_url, html)
        self.assertIn(happ_url, html)
        self.assertIn(hiddify_url, html)
        self.assertLess(html.find(streisand_url), html.find(v2box_url))
        self.assertLess(html.find(v2box_url), html.find(shadowrocket_url))
        self.assertLess(html.find(shadowrocket_url), html.find(v2raytun_url))
        self.assertLess(html.find(v2raytun_url), html.find(happ_url))
        self.assertLess(html.find(happ_url), html.find(hiddify_url))
        self.assertIn("попробуем открыть приложение еще раз", html)
        self.assertIn("canRetryLink", html)
        self.assertIn("v2box://", html)
        self.assertIn("retriedLinks", html)
        self.assertIn("visibilitychange", html)
        self.assertNotIn("streisandRetried", html)
        self.assertNotIn("streisandWarmupPending", html)
        self.assertNotIn("window.location.href = 'streisand://'", html)
        self.assertIn("Configs -> VXcloud -> Home -> Connect", html)
        self.assertNotIn("url=https://vxcloud.ru/account/feed/feed-token/", html)

    def test_vpn_public_endpoint_helpers_fallback_to_env(self):
        with patch.object(sys.modules["cabinet.views"].settings, "VPN_PUBLIC_HOST", ""), patch.object(
            sys.modules["cabinet.views"].settings, "VPN_PUBLIC_PORT", ""
        ), patch.dict(
            "os.environ",
            {"VPN_PUBLIC_HOST": "vxcloud.ru", "VPN_PUBLIC_PORT": "29940"},
            clear=False,
        ):
            self.assertEqual(_vpn_public_host(), "vxcloud.ru")
            self.assertEqual(_vpn_public_port(), 29940)

    def test_renew_without_selection_requires_choice_when_multiple_configs(self):
        bot_user = SimpleNamespace(id=7)
        subscriptions = [SimpleNamespace(id=11), SimpleNamespace(id=12)]
        with patch("cabinet.views._list_renewable_subscriptions_for_bot_user", return_value=subscriptions):
            target_id, error = _resolve_renew_target_subscription_id(bot_user, None)

        self.assertIsNone(target_id)
        self.assertEqual(error, "Выберите, какой доступ продлить.")

    def test_renew_without_selection_allows_single_config(self):
        bot_user = SimpleNamespace(id=7)
        with patch(
            "cabinet.views._list_renewable_subscriptions_for_bot_user",
            return_value=[SimpleNamespace(id=42)],
        ):
            target_id, error = _resolve_renew_target_subscription_id(bot_user, None)

        self.assertEqual(target_id, 42)
        self.assertIsNone(error)

    def test_renew_with_selection_targets_owned_config(self):
        bot_user = SimpleNamespace(id=7)
        subscriptions = [SimpleNamespace(id=11), SimpleNamespace(id=12)]
        with patch("cabinet.views._list_renewable_subscriptions_for_bot_user", return_value=subscriptions):
            target_id, error = _resolve_renew_target_subscription_id(bot_user, 12)

        self.assertEqual(target_id, 12)
        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
