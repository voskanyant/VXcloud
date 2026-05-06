import os
import sys
import unittest
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
        self.assertEqual(payload["support"]["instructions_url"], "/instructions/")

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
        self.assertNotIn("Support hub", html)
        self.assertNotIn("Write in Telegram", html)
        self.assertNotIn("Open full guide", html)
        self.assertIn("VX-000007", html)
        self.assertIn("https://t.me/vxcloud_test_bot", html)

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
        self.assertEqual(error, "Выберите, какой конфиг продлить.")

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
