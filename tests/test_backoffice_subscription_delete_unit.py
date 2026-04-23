import os
import sys
import unittest
from datetime import timedelta
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
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.utils import timezone

from backoffice.views import BotSubscriptionDeleteView
from backoffice.views import _delete_subscription_from_xui, _run_async_from_sync


class BackofficeSubscriptionDeleteUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.staff_user, _ = User.objects.get_or_create(
            username="ops_subscription_delete_staff",
            defaults={"email": "ops-subscription-delete@example.com", "is_staff": True},
        )
        self.staff_user.is_staff = True
        self.staff_user.set_password("pass12345")
        self.staff_user.save()

    def _build_request(self):
        request = self.factory.post("/ops/bot/subscriptions/5/delete/")
        request.user = self.staff_user
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def test_delete_is_blocked_for_active_subscription(self):
        now = timezone.now()
        subscription = SimpleNamespace(
            id=5,
            display_name="Active config",
            client_email="active@example.com",
            is_active=True,
            expires_at=now + timedelta(days=2),
            revoked_at=None,
            delete=MagicMock(),
        )

        with patch.object(BotSubscriptionDeleteView, "get_object", return_value=subscription):
            response = BotSubscriptionDeleteView.as_view()(self._build_request(), pk=5)

        self.assertEqual(response.status_code, 200)
        subscription.delete.assert_not_called()

    def test_delete_removes_node_clients_and_subscription_when_inactive(self):
        now = timezone.now()
        subscription = SimpleNamespace(
            id=6,
            display_name="Expired config",
            client_email="expired@example.com",
            is_active=False,
            expires_at=now - timedelta(days=1),
            revoked_at=None,
            alias_fqdn="u-expired.connect.vxcloud.ru",
            dns_record_id="cf-record-6",
            delete=MagicMock(),
        )
        node_clients_qs = MagicMock()

        with (
            patch.object(BotSubscriptionDeleteView, "get_object", return_value=subscription),
            patch("backoffice.views._delete_subscription_from_xui", new=AsyncMock(return_value=[])),
            patch("backoffice.views._delete_subscription_alias_from_dns", new=AsyncMock(return_value=None)) as dns_delete,
            patch("backoffice.views.VPNNodeClient.objects.filter", return_value=node_clients_qs) as filter_mock,
        ):
            response = BotSubscriptionDeleteView.as_view()(self._build_request(), pk=6)

        self.assertEqual(response.status_code, 302)
        filter_mock.assert_called_with(subscription_id=6)
        node_clients_qs.delete.assert_called_once()
        subscription.delete.assert_called_once()
        dns_delete.assert_awaited_once_with(subscription)

    def test_delete_does_not_500_when_xui_delete_raises(self):
        now = timezone.now()
        subscription = SimpleNamespace(
            id=7,
            display_name="Broken delete config",
            client_email="broken-delete@example.com",
            is_active=False,
            expires_at=now - timedelta(days=1),
            revoked_at=None,
            delete=MagicMock(),
        )

        with (
            patch.object(BotSubscriptionDeleteView, "get_object", return_value=subscription),
            patch("backoffice.views._delete_subscription_from_xui", new=AsyncMock(side_effect=RuntimeError("boom"))),
        ):
            response = BotSubscriptionDeleteView.as_view()(self._build_request(), pk=7)

        self.assertEqual(response.status_code, 200)
        subscription.delete.assert_not_called()

    def test_delete_passes_cluster_nodes_snapshot_into_async_cleanup(self):
        now = timezone.now()
        subscription = SimpleNamespace(
            id=9,
            display_name="Cluster delete config",
            client_email="cluster-delete@example.com",
            is_active=False,
            expires_at=now - timedelta(days=1),
            revoked_at=None,
            delete=MagicMock(),
        )
        node_clients_qs = MagicMock()
        cluster_nodes = [{"id": 10, "xui_base_url": "https://node.local", "xui_username": "u", "xui_password": "p", "xui_inbound_id": 1}]
        delete_mock = AsyncMock(return_value=[])

        with (
            patch.object(BotSubscriptionDeleteView, "get_object", return_value=subscription),
            patch("backoffice.views.bool_env", return_value=True),
            patch("backoffice.views._active_vpn_nodes_snapshot", return_value=cluster_nodes),
            patch("backoffice.views._delete_subscription_from_xui", new=delete_mock),
            patch("backoffice.views.VPNNodeClient.objects.filter", return_value=node_clients_qs),
        ):
            response = BotSubscriptionDeleteView.as_view()(self._build_request(), pk=9)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(delete_mock.await_args.kwargs["cluster_nodes"], cluster_nodes)

    def test_delete_xui_treats_missing_client_as_success(self):
        now = timezone.now()
        subscription = SimpleNamespace(
            id=8,
            inbound_id=1,
            client_uuid="11111111-1111-1111-1111-111111111111",
            client_email="missing@example.com",
            expires_at=now - timedelta(days=1),
            xui_sub_id=None,
        )
        xui = MagicMock()
        xui.start = AsyncMock()
        xui.delete_client = AsyncMock(side_effect=RuntimeError("client not found"))
        xui.has_client = AsyncMock(return_value=False)
        xui.close = AsyncMock()

        def _fake_env_value(name: str, default: str = "") -> str:
            values = {
                "XUI_BASE_URL": "https://panel.local",
                "XUI_USERNAME": "user",
                "XUI_PASSWORD": "pass",
            }
            return values.get(name, default)

        with (
            patch("backoffice.views.bool_env", return_value=False),
            patch("backoffice.views.env_value", side_effect=_fake_env_value),
            patch("backoffice.views.XUIClient", return_value=xui),
        ):
            errors = _run_async_from_sync(_delete_subscription_from_xui(subscription))

        self.assertEqual(errors, [])
        xui.has_client.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
