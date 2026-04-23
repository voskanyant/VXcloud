import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"
if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vxcloud_site.settings")

import django

django.setup()

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from cabinet.views import _delete_subscription_everywhere


class AccountSubscriptionDeleteUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user, _ = User.objects.get_or_create(
            username="account_delete_user",
            defaults={"email": "account_delete_user@example.com"},
        )
        self.user.set_password("pass12345")
        self.user.save()

        self.client = Client()
        assert self.client.login(username="account_delete_user", password="pass12345")
        self.bot_user = SimpleNamespace(id=777)
        self.subscription = SimpleNamespace(id=55)

    def test_delete_api_rejects_active_subscription(self):
        filter_mock = MagicMock()
        filter_mock.first.return_value = self.subscription

        with (
            patch("cabinet.views._resolve_account_bot_user", return_value=(None, self.bot_user)),
            patch("cabinet.views.BotSubscription.objects.filter", return_value=filter_mock),
            patch(
                "cabinet.views._delete_subscription_everywhere",
                return_value=(False, "Активный конфиг нельзя удалить."),
            ),
        ):
            response = self.client.post("/account-app/api/subscriptions/55/delete/", content_type="application/json")

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertIn("нельзя удалить", body["error"])

    def test_delete_api_allows_inactive_subscription(self):
        filter_mock = MagicMock()
        filter_mock.first.return_value = self.subscription

        with (
            patch("cabinet.views._resolve_account_bot_user", return_value=(None, self.bot_user)),
            patch("cabinet.views.BotSubscription.objects.filter", return_value=filter_mock),
            patch("cabinet.views._delete_subscription_everywhere", return_value=(True, None)),
        ):
            response = self.client.post("/account-app/api/subscriptions/55/delete/", content_type="application/json")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["subscription_id"], 55)

    def test_delete_everywhere_cleans_xui_and_node_clients_in_cluster_mode(self):
        subscription = SimpleNamespace(
            id=55,
            inbound_id=1,
            client_uuid="11111111-1111-1111-1111-111111111111",
            client_email="user@example.com",
            expires_at=timezone.now(),
            xui_sub_id="sub-1",
            alias_fqdn="u-test.connect.vxcloud.ru",
            dns_record_id="cf-record-1",
            delete=MagicMock(),
        )
        node_clients_qs = MagicMock()
        cluster_nodes = [{"id": 10}]

        with (
            patch("cabinet.views._subscription_state", return_value={"is_active": False}),
            patch("backoffice.views.bool_env", return_value=True),
            patch("backoffice.views._active_vpn_nodes_snapshot", return_value=cluster_nodes),
            patch("backoffice.views._delete_subscription_from_xui", return_value=[]),
            patch("backoffice.views._delete_subscription_alias_from_dns", new=AsyncMock(return_value=None)) as dns_delete,
            patch("cabinet.views.VPNNodeClient.objects.filter", return_value=node_clients_qs) as filter_mock,
        ):
            deleted, error_message = _delete_subscription_everywhere(subscription)

        self.assertTrue(deleted)
        self.assertIsNone(error_message)
        filter_mock.assert_called_once_with(subscription_id=55)
        node_clients_qs.delete.assert_called_once()
        subscription.delete.assert_called_once()
        dns_delete.assert_awaited_once_with(subscription)

    def test_delete_everywhere_aborts_when_xui_cleanup_reports_errors(self):
        subscription = SimpleNamespace(
            id=56,
            inbound_id=1,
            client_uuid="11111111-1111-1111-1111-111111111111",
            client_email="user@example.com",
            expires_at=timezone.now(),
            xui_sub_id="sub-1",
            delete=MagicMock(),
        )
        node_clients_qs = MagicMock()

        with (
            patch("cabinet.views._subscription_state", return_value={"is_active": False}),
            patch("backoffice.views.bool_env", return_value=False),
            patch("backoffice.views._delete_subscription_from_xui", return_value=["primary: boom"]),
            patch("cabinet.views.VPNNodeClient.objects.filter", return_value=node_clients_qs),
        ):
            deleted, error_message = _delete_subscription_everywhere(subscription)

        self.assertFalse(deleted)
        self.assertIn("3x-ui", error_message or "")
        node_clients_qs.delete.assert_not_called()
        subscription.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
