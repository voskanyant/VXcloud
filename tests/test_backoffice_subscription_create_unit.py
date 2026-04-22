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

from src.xui_client import NO_EXPIRY_SENTINEL

from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.utils import timezone

from cabinet.models import BotUser
from backoffice.views import BotSubscriptionCreateView, _create_subscription_on_xui, _run_async_from_sync


class _FakeBotUserQuerySet:
    model = BotUser

    def __init__(self, user):
        self.user = user

    def get(self, **kwargs):
        lookup_value = kwargs.get("pk")
        if lookup_value is None:
            lookup_value = kwargs.get("id")
        if int(lookup_value) != int(self.user.id):
            raise LookupError("bot user not found")
        return self.user

    def all(self):
        return self

    def __iter__(self):
        return iter([self.user])

    def iterator(self):
        return iter([self.user])

    def count(self):
        return 1


class BackofficeSubscriptionCreateUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.staff_user = SimpleNamespace(
            id=101,
            username="ops_subscription_create_staff",
            email="ops-subscription-create@example.com",
            is_staff=True,
            is_authenticated=True,
        )

    def _attach_session_and_messages(self, request):
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def _build_request(self, *, user_id: int, display_name: str, expires_at: str):
        request = self.factory.post(
            "/ops/bot/subscriptions/new/",
            {"user_id": str(user_id), "display_name": display_name, "expires_at": expires_at},
        )
        request.user = self.staff_user
        return self._attach_session_and_messages(request)

    def _build_get_request(self):
        request = self.factory.get("/ops/bot/subscriptions/new/")
        request.user = self.staff_user
        return self._attach_session_and_messages(request)

    def test_create_view_get_renders_form(self):
        fake_user = SimpleNamespace(id=1, username="tester", first_name="Test", client_code="VX-000001")
        with patch("backoffice.forms.BotUser.objects.order_by", return_value=_FakeBotUserQuerySet(fake_user)):
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
        fake_user = SimpleNamespace(id=1, username="tester", first_name="Test", client_code="VX-000001")

        with (
            patch("backoffice.forms.BotUser.objects.order_by", return_value=_FakeBotUserQuerySet(fake_user)),
            patch("backoffice.views._load_subscription_runtime", new=AsyncMock(return_value=runtime)),
            patch("backoffice.views._create_subscription_on_xui", new=provision_mock),
            patch(
                "backoffice.views.env_value",
                side_effect=lambda name, default="": {
                    "VPN_PUBLIC_HOST": "vxcloud.ru",
                    "VPN_TAG": "VXcloud",
                    "VPN_FLOW": "xtls-rprx-vision",
                }.get(name, default),
            ),
            patch("backoffice.views.int_env", side_effect=lambda name, default: 29940 if name == "VPN_PUBLIC_PORT" else default),
            patch("backoffice.views.bool_env", return_value=False),
            patch("backoffice.views.BotSubscription.save", new=MagicMock()),
        ):
            response = BotSubscriptionCreateView.as_view()(
                self._build_request(user_id=1, display_name="my VPN", expires_at=expires_at)
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(provision_mock.await_args.kwargs["display_name"], "my VPN")
        self.assertEqual(provision_mock.await_args.kwargs["enabled"], True)

    def test_create_subscription_in_cluster_mode_assigns_best_node_and_uses_alias_host(self):
        now = timezone.now()
        expires_at = timezone.localtime(now + timedelta(days=16)).strftime("%Y-%m-%dT%H:%M")
        runtime = {
            "inbound_id": 1,
            "inbound_port": 443,
            "reality": SimpleNamespace(
                public_key="pub",
                short_id="ec40",
                sni="www.apple.com",
                fingerprint="chrome",
            ),
        }
        fake_user = SimpleNamespace(id=1, username="tester", first_name="Test", client_code="VX-000001")
        assigned_node_snapshot = {
            "id": 10,
            "name": "node-10",
            "backend_host": "de1.vxcloud.ru",
            "backend_port": 443,
            "public_ip": "116.202.10.113",
            "compatibility_pool": "default",
            "xui_base_url": "https://node.local",
            "xui_username": "u",
            "xui_password": "p",
            "xui_inbound_id": 1,
        }
        created_client = {"node_id": 10, "ok": True, "xui_sub_id": "sub-ops-001"}
        saved_objects: list[SimpleNamespace] = []

        def fake_save(instance, *args, **kwargs):
            if getattr(instance, "id", None) in (None, 0):
                instance.id = 777
            saved_objects.append(instance)

        with (
            patch("backoffice.forms.BotUser.objects.order_by", return_value=_FakeBotUserQuerySet(fake_user)),
            patch("backoffice.views._load_subscription_runtime", new=AsyncMock(return_value=runtime)),
            patch("backoffice.views._pick_best_assignment_node_snapshot", return_value=(assigned_node_snapshot, 11.5, {"traffic": 4.2})),
            patch("backoffice.views.create_client_on_node", new=AsyncMock(return_value=created_client)) as create_mock,
            patch(
                "backoffice.views.ensure_subscription_alias_record",
                new=AsyncMock(return_value=SimpleNamespace(record_id="dns-1", provider="cloudflare", change_id="chg-1", ttl=300)),
            ),
            patch("backoffice.views.VPNNodeClient.objects.update_or_create", return_value=(SimpleNamespace(), True)),
            patch(
                "backoffice.views.env_value",
                side_effect=lambda name, default="": {
                    "VPN_PUBLIC_HOST": "connect.vxcloud.ru",
                    "VPN_TAG": "VXcloud",
                    "VPN_FLOW": "xtls-rprx-vision",
                }.get(name, default),
            ),
            patch("backoffice.views.int_env", side_effect=lambda name, default: 443 if name == "VPN_PUBLIC_PORT" else default),
            patch("backoffice.views.bool_env", side_effect=lambda name, default=False: True if name == "VPN_CLUSTER_ENABLED" else default),
            patch("backoffice.views.BotSubscription.save", new=fake_save),
        ):
            response = BotSubscriptionCreateView.as_view()(
                self._build_request(user_id=1, display_name="my VPN", expires_at=expires_at)
            )

        self.assertEqual(response.status_code, 302)
        create_mock.assert_awaited_once()
        self.assertTrue(saved_objects)
        saved = saved_objects[0]
        self.assertEqual(saved.assigned_node_id, 10)
        self.assertEqual(saved.current_node_id, 10)
        self.assertEqual(saved.assignment_source, "backoffice_alias")
        self.assertEqual(saved.migration_state, "ready")
        self.assertEqual(saved.assignment_state, "steady")
        self.assertTrue(saved.alias_fqdn.endswith(".vpn.vxcloud.ru"))
        self.assertIn(f"@{saved.alias_fqdn}:443", saved.vless_url)
        self.assertTrue(saved.feed_token)

    def test_create_subscription_without_expiry_uses_no_expiry_semantics(self):
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
        saved_objects: list[SimpleNamespace] = []
        fake_user = SimpleNamespace(id=1, username="tester", first_name="Test", client_code="VX-000001")

        def fake_save(instance, *args, **kwargs):
            if getattr(instance, "id", None) in (None, 0):
                instance.id = 501
            saved_objects.append(
                SimpleNamespace(
                    expires_at=getattr(instance, "expires_at", None),
                    is_active=getattr(instance, "is_active", None),
                    feed_token=getattr(instance, "feed_token", None),
                )
            )

        with (
            patch("backoffice.forms.BotUser.objects.order_by", return_value=_FakeBotUserQuerySet(fake_user)),
            patch("backoffice.views._load_subscription_runtime", new=AsyncMock(return_value=runtime)),
            patch("backoffice.views._create_subscription_on_xui", new=provision_mock),
            patch(
                "backoffice.views.env_value",
                side_effect=lambda name, default="": {
                    "VPN_PUBLIC_HOST": "vxcloud.ru",
                    "VPN_TAG": "VXcloud",
                    "VPN_FLOW": "xtls-rprx-vision",
                }.get(name, default),
            ),
            patch("backoffice.views.int_env", side_effect=lambda name, default: 29940 if name == "VPN_PUBLIC_PORT" else default),
            patch("backoffice.views.bool_env", return_value=False),
            patch("backoffice.views.BotSubscription.save", new=fake_save),
            patch("backoffice.views.BotSubscription.objects.get") as subscription_get_mock,
        ):
            subscription_get_mock.return_value = SimpleNamespace(
                id=501,
                display_name="my VPN",
                client_email="tg_1_example",
                expires_at=NO_EXPIRY_SENTINEL,
                vless_url="vless://example",
                feed_token="feed-token-501",
                assigned_node=None,
                assignment_source="backoffice_single_node",
                migration_state="single_node",
            )
            response = BotSubscriptionCreateView.as_view()(
                self._build_request(user_id=1, display_name="my VPN", expires_at="")
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(provision_mock.await_args.kwargs["expires_at"], None)
        self.assertEqual(provision_mock.await_args.kwargs["enabled"], True)
        self.assertTrue(saved_objects)
        self.assertEqual(saved_objects[0].expires_at, NO_EXPIRY_SENTINEL)
        self.assertTrue(saved_objects[0].is_active)
        self.assertTrue(saved_objects[0].feed_token)

    def test_ops_create_uses_backoffice_ip_limit_default_zero(self):
        xui = MagicMock()
        xui.start = AsyncMock()
        xui.add_client = AsyncMock()
        xui.get_client_sub_id = AsyncMock(return_value="sub-ops-001")
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
            results = _run_async_from_sync(
                _create_subscription_on_xui(
                    client_uuid="11111111-1111-1111-1111-111111111111",
                    client_email="ops@example.com",
                    display_name="ops-created",
                    expires_at=timezone.now(),
                    enabled=True,
                )
            )

        self.assertEqual(results[0]["ok"], True)
        self.assertEqual(xui.add_client.await_args.kwargs["limit_ip"], 0)


if __name__ == "__main__":
    unittest.main()
