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

from backoffice.views import BotSubscriptionExpiryUpdateView, _push_subscription_expiry_to_xui, _run_async_from_sync


class BackofficeSubscriptionExpiryUpdateUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.staff_user, _ = User.objects.get_or_create(
            username="backoffice_staff_user",
            defaults={"email": "backoffice_staff_user@example.com", "is_staff": True},
        )
        self.staff_user.is_staff = True
        self.staff_user.set_password("pass12345")
        self.staff_user.save()

    def _build_request(self, expires_at: str):
        request = self.factory.post("/ops/bot/subscriptions/55/edit/", {"expires_at": expires_at})
        request.user = self.staff_user

        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()

        setattr(request, "_messages", FallbackStorage(request))
        return request

    def test_post_accepts_aware_form_datetime_without_500(self):
        current = timezone.now()
        subscription = SimpleNamespace(
            id=55,
            display_name="Test config",
            client_email="test@example.com",
            expires_at=current,
            is_active=True,
            revoked_at=None,
            updated_at=current,
            save=MagicMock(),
        )
        target_local = timezone.localtime(current + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")
        view = BotSubscriptionExpiryUpdateView.as_view()

        with (
            patch.object(BotSubscriptionExpiryUpdateView, "_subscription", return_value=subscription),
            patch("backoffice.views._push_subscription_expiry_to_xui", new=AsyncMock(return_value=[])),
        ):
            response = view(self._build_request(target_local), pk=55)

        self.assertEqual(response.status_code, 302)
        subscription.save.assert_called_once()
        self.assertTrue(subscription.is_active)

    def test_post_marks_subscription_inactive_when_expiry_is_in_past(self):
        current = timezone.now()
        subscription = SimpleNamespace(
            id=56,
            display_name="Expired config",
            client_email="expired@example.com",
            expires_at=current,
            is_active=True,
            revoked_at=None,
            updated_at=current,
            save=MagicMock(),
        )
        target_local = timezone.localtime(current - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
        view = BotSubscriptionExpiryUpdateView.as_view()

        with (
            patch.object(BotSubscriptionExpiryUpdateView, "_subscription", return_value=subscription),
            patch("backoffice.views._push_subscription_expiry_to_xui", new=AsyncMock(return_value=[])),
        ):
            response = view(self._build_request(target_local), pk=56)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(subscription.is_active)
        subscription.save.assert_called_once()

    def test_post_accepts_us_ampm_datetime_without_500(self):
        current = timezone.now()
        subscription = SimpleNamespace(
            id=57,
            display_name="US format config",
            client_email="us-format@example.com",
            expires_at=current,
            is_active=True,
            revoked_at=None,
            updated_at=current,
            save=MagicMock(),
        )
        target_local = timezone.localtime(current + timedelta(days=15)).strftime("%m/%d/%Y %I:%M %p")
        view = BotSubscriptionExpiryUpdateView.as_view()

        with (
            patch.object(BotSubscriptionExpiryUpdateView, "_subscription", return_value=subscription),
            patch("backoffice.views._push_subscription_expiry_to_xui", new=AsyncMock(return_value=[])),
        ):
            response = view(self._build_request(target_local), pk=57)

        self.assertEqual(response.status_code, 302)
        subscription.save.assert_called_once()

    def test_post_does_not_500_when_cluster_node_has_bad_inbound_id(self):
        current = timezone.now()
        subscription = SimpleNamespace(
            id=58,
            display_name="Broken node config",
            client_uuid="11111111-1111-1111-1111-111111111111",
            client_email="broken-node@example.com",
            inbound_id=1,
            expires_at=current,
            is_active=True,
            revoked_at=None,
            updated_at=current,
            save=MagicMock(),
        )
        target_local = timezone.localtime(current + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
        view = BotSubscriptionExpiryUpdateView.as_view()
        broken_node = [
            {
                "id": 10,
                "xui_base_url": "https://node.local",
                "xui_username": "u",
                "xui_password": "p",
                "xui_inbound_id": None,
            }
        ]

        with (
            patch.object(BotSubscriptionExpiryUpdateView, "_subscription", return_value=subscription),
            patch("backoffice.views.bool_env", return_value=True),
            patch("backoffice.views._active_vpn_nodes_snapshot", return_value=broken_node),
        ):
            response = view(self._build_request(target_local), pk=58)

        self.assertEqual(response.status_code, 302)
        subscription.save.assert_called_once()

    def test_post_updates_node_sync_desired_and_observed_state(self):
        current = timezone.now()
        subscription = SimpleNamespace(
            id=60,
            display_name="Sync update config",
            client_email="sync-update@example.com",
            expires_at=current,
            is_active=True,
            revoked_at=None,
            updated_at=current,
            save=MagicMock(),
        )
        target_local = timezone.localtime(current + timedelta(days=4)).strftime("%Y-%m-%dT%H:%M")
        view = BotSubscriptionExpiryUpdateView.as_view()
        node_clients_qs = MagicMock()

        with (
            patch.object(BotSubscriptionExpiryUpdateView, "_subscription", return_value=subscription),
            patch("backoffice.views.VPNNodeClient.objects.filter", return_value=node_clients_qs) as filter_mock,
            patch("backoffice.views._push_subscription_expiry_to_xui", new=AsyncMock(return_value=[])),
        ):
            response = view(self._build_request(target_local), pk=60)

        self.assertEqual(response.status_code, 302)
        self.assertGreaterEqual(node_clients_qs.update.call_count, 2)
        filter_mock.assert_called_with(subscription_id=60)

    def test_post_passes_cluster_nodes_snapshot_into_async_push(self):
        current = timezone.now()
        subscription = SimpleNamespace(
            id=61,
            display_name="Cluster push config",
            client_email="cluster-push@example.com",
            expires_at=current,
            is_active=True,
            revoked_at=None,
            updated_at=current,
            save=MagicMock(),
        )
        target_local = timezone.localtime(current + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        view = BotSubscriptionExpiryUpdateView.as_view()
        cluster_nodes = [{"id": 10, "xui_base_url": "https://node.local", "xui_username": "u", "xui_password": "p", "xui_inbound_id": 1}]
        push_mock = AsyncMock(return_value=[])

        with (
            patch.object(BotSubscriptionExpiryUpdateView, "_subscription", return_value=subscription),
            patch("backoffice.views.bool_env", return_value=True),
            patch("backoffice.views._active_vpn_nodes_snapshot", return_value=cluster_nodes),
            patch("backoffice.views._push_subscription_expiry_to_xui", new=push_mock),
        ):
            response = view(self._build_request(target_local), pk=61)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(push_mock.await_args.kwargs["cluster_nodes"], cluster_nodes)

    def test_post_does_not_500_when_xui_push_raises(self):
        current = timezone.now()
        subscription = SimpleNamespace(
            id=59,
            display_name="Push fail config",
            client_email="push-fail@example.com",
            expires_at=current,
            is_active=True,
            revoked_at=None,
            updated_at=current,
            save=MagicMock(),
        )
        target_local = timezone.localtime(current + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        view = BotSubscriptionExpiryUpdateView.as_view()

        with (
            patch.object(BotSubscriptionExpiryUpdateView, "_subscription", return_value=subscription),
            patch("backoffice.views._push_subscription_expiry_to_xui", new=AsyncMock(side_effect=RuntimeError("boom"))),
        ):
            response = view(self._build_request(target_local), pk=59)

        self.assertEqual(response.status_code, 302)
        subscription.save.assert_called_once()

    def test_ops_expiry_push_uses_backoffice_ip_limit_default_zero(self):
        current = timezone.now()
        subscription = SimpleNamespace(
            id=62,
            display_name="Backoffice no-ip-limit",
            client_uuid="11111111-1111-1111-1111-111111111111",
            client_email="ops-no-limit@example.com",
            inbound_id=1,
            expires_at=current,
            is_active=True,
            revoked_at=None,
        )
        xui = MagicMock()
        xui.start = AsyncMock()
        xui.set_client_enabled = AsyncMock()
        xui.close = AsyncMock()

        def _fake_env_value(name: str, default: str = "") -> str:
            values = {
                "XUI_BASE_URL": "https://panel.local",
                "XUI_USERNAME": "user",
                "XUI_PASSWORD": "pass",
                "VPN_FLOW": "xtls-rprx-vision",
            }
            return values.get(name, default)

        with (
            patch("backoffice.views.bool_env", return_value=False),
            patch("backoffice.views.env_value", side_effect=_fake_env_value),
            patch(
                "backoffice.views.int_env",
                side_effect=lambda name, default: 1 if name == "XUI_INBOUND_ID" else 0 if name == "BACKOFFICE_MAX_DEVICES_PER_SUB" else default,
            ),
            patch("backoffice.views.XUIClient", return_value=xui),
        ):
            errors = _run_async_from_sync(_push_subscription_expiry_to_xui(subscription, current))

        self.assertEqual(errors, [])
        self.assertEqual(xui.set_client_enabled.await_args.kwargs["limit_ip"], 0)


if __name__ == "__main__":
    unittest.main()
