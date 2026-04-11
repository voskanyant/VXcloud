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

from backoffice.views import BotSubscriptionCreateView


class BackofficeSubscriptionCreateUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.staff_user, _ = User.objects.get_or_create(
            username="ops_subscription_create_staff",
            defaults={"email": "ops-subscription-create@example.com", "is_staff": True},
        )
        self.staff_user.is_staff = True
        self.staff_user.set_password("pass12345")
        self.staff_user.save()

    def _build_request(self, *, user_id: int, display_name: str, expires_at: str):
        request = self.factory.post(
            "/ops/bot/subscriptions/new/",
            {"user_id": str(user_id), "display_name": display_name, "expires_at": expires_at},
        )
        request.user = self.staff_user
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def _build_get_request(self):
        request = self.factory.get("/ops/bot/subscriptions/new/")
        request.user = self.staff_user
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def test_create_view_get_renders_form(self):
        response = BotSubscriptionCreateView.as_view()(self._build_get_request())
        self.assertEqual(response.status_code, 200)

    def test_create_subscription_from_ops_single_node(self):
        now = timezone.now()
        expires_at = timezone.localtime(now + timedelta(days=16)).strftime("%Y-%m-%dT%H:%M")
        runtime = {
            "inbound_id": 1,
            "inbound_port": 29940,
            "reality": SimpleNamespace(
                public_key="pub",
                short_id="ec40",
                sni="www.apple.com",
                fingerprint="chrome",
            ),
        }
        provision_mock = AsyncMock(return_value=[{"node_id": 0, "ok": True, "xui_sub_id": "sub-ops-001"}])

        with (
            patch("backoffice.forms.BotUser.objects.filter") as user_filter_mock,
            patch(
                "backoffice.views.get_object_or_404",
                return_value=SimpleNamespace(id=1, username="tester", first_name="Test", client_code="VX-000001"),
            ),
            patch("backoffice.views._load_subscription_runtime", new=AsyncMock(return_value=runtime)),
            patch("backoffice.views._create_subscription_on_xui", new=provision_mock),
            patch("backoffice.views.env_value", side_effect=lambda name, default="": {
                "VPN_PUBLIC_HOST": "vxcloud.ru",
                "VPN_TAG": "VXcloud",
                "VPN_FLOW": "xtls-rprx-vision",
            }.get(name, default)),
            patch("backoffice.views.int_env", side_effect=lambda name, default: 29940 if name == "VPN_PUBLIC_PORT" else default),
            patch("backoffice.views.bool_env", return_value=False),
            patch("backoffice.views.BotSubscription.save", new=MagicMock()),
        ):
            user_filter_mock.return_value.exists.return_value = True
            response = BotSubscriptionCreateView.as_view()(
                self._build_request(user_id=1, display_name="my VPN", expires_at=expires_at)
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(provision_mock.await_args.kwargs["display_name"], "my VPN")
        self.assertEqual(provision_mock.await_args.kwargs["enabled"], True)

    def test_create_subscription_does_not_500_when_cluster_sync_state_write_fails(self):
        now = timezone.now()
        expires_at = timezone.localtime(now + timedelta(days=16)).strftime("%Y-%m-%dT%H:%M")
        runtime = {
            "inbound_id": 1,
            "inbound_port": 29940,
            "reality": SimpleNamespace(
                public_key="pub",
                short_id="ec40",
                sni="www.apple.com",
                fingerprint="chrome",
            ),
        }
        cluster_nodes = [{"id": 10, "xui_base_url": "https://node.local", "xui_username": "u", "xui_password": "p", "xui_inbound_id": 1}]
        provision_mock = AsyncMock(return_value=[{"node_id": 10, "ok": True, "xui_sub_id": "sub-ops-001"}])
        filter_mock = MagicMock()
        filter_mock.first.side_effect = RuntimeError("vpn_node_clients write failed")

        with (
            patch("backoffice.forms.BotUser.objects.filter") as user_filter_mock,
            patch(
                "backoffice.views.get_object_or_404",
                return_value=SimpleNamespace(id=1, username="tester", first_name="Test", client_code="VX-000001"),
            ),
            patch("backoffice.views._load_subscription_runtime", new=AsyncMock(return_value=runtime)),
            patch("backoffice.views._create_subscription_on_xui", new=provision_mock),
            patch("backoffice.views._active_vpn_nodes_snapshot", return_value=cluster_nodes),
            patch("backoffice.views.VPNNodeClient.objects.filter", return_value=filter_mock),
            patch(
                "backoffice.views.env_value",
                side_effect=lambda name, default="": {
                    "VPN_PUBLIC_HOST": "vxcloud.ru",
                    "VPN_TAG": "VXcloud",
                    "VPN_FLOW": "xtls-rprx-vision",
                }.get(name, default),
            ),
            patch("backoffice.views.int_env", side_effect=lambda name, default: 29940 if name == "VPN_PUBLIC_PORT" else default),
            patch("backoffice.views.bool_env", side_effect=lambda name, default=False: True if name == "VPN_CLUSTER_ENABLED" else default),
            patch("backoffice.views.BotSubscription.save", new=MagicMock()),
        ):
            user_filter_mock.return_value.exists.return_value = True
            response = BotSubscriptionCreateView.as_view()(
                self._build_request(user_id=1, display_name="my VPN", expires_at=expires_at)
            )

        self.assertEqual(response.status_code, 302)


if __name__ == "__main__":
    unittest.main()
