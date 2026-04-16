import os
import sys
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
from django.core.management import call_command
from django.http import HttpResponse
from django.test import RequestFactory
from django.views.generic import UpdateView

from backoffice.views import (
    EdgeServerDeleteView,
    EdgeServerUpdateView,
    _normalize_edge_primary_state,
    ensure_local_main_node,
)


class BackofficeEdgeServerUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.staff_user, _ = User.objects.get_or_create(
            username="ops_edge_staff",
            defaults={"email": "ops-edge@example.com", "is_staff": True},
        )
        self.staff_user.is_staff = True
        self.staff_user.set_password("pass12345")
        self.staff_user.save()

    def _build_request(self, path: str, *, method: str = "post"):
        request_factory = getattr(self.factory, method.lower())
        request = request_factory(path)
        request.user = self.staff_user
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def test_normalize_edge_primary_state_prefers_explicit_primary(self):
        preferred = SimpleNamespace(pk=10, is_primary=True)
        exclude_mock = MagicMock()

        with patch("backoffice.views.EdgeServer.objects.exclude", return_value=exclude_mock):
            result = _normalize_edge_primary_state(preferred)

        self.assertIs(result, preferred)
        exclude_mock.update.assert_called_once_with(is_primary=False)

    def test_normalize_edge_primary_state_keeps_first_existing_primary(self):
        keeper = SimpleNamespace(pk=7)
        existing_primary_qs = MagicMock()
        existing_primary_qs.order_by.return_value = [keeper, SimpleNamespace(pk=8)]
        filter_primary_qs = MagicMock()
        filter_primary_qs.exclude.return_value = MagicMock()
        filter_primary_qs.exclude.return_value.update = MagicMock()

        with (
            patch("backoffice.views.EdgeServer.objects.filter", side_effect=[existing_primary_qs, filter_primary_qs]),
        ):
            result = _normalize_edge_primary_state()

        self.assertIs(result, keeper)
        filter_primary_qs.exclude.return_value.update.assert_called_once_with(is_primary=False)

    def test_edge_server_update_triggers_runtime_render(self):
        request = self._build_request("/ops/infra/edges/10/edit/")
        form = SimpleNamespace(instance=SimpleNamespace(updated_at=None))
        view = EdgeServerUpdateView()
        view.request = request
        view.object = form.instance

        with (
            patch.object(UpdateView, "form_valid", return_value=HttpResponse("ok")) as super_form_valid,
            patch("backoffice.views._render_local_haproxy_runtime", return_value=None) as render_mock,
            patch("backoffice.views._normalize_edge_primary_state") as normalize_mock,
        ):
            response = view.form_valid(form)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(super_form_valid.called)
        self.assertTrue(render_mock.called)
        self.assertTrue(normalize_mock.called)
        self.assertIsNotNone(form.instance.updated_at)

    def test_edge_server_delete_promotes_replacement_primary(self):
        request = self._build_request("/ops/infra/edges/10/delete/")
        fake_edge = SimpleNamespace(id=10, name="edge-1", is_primary=True, delete=MagicMock())
        replacement = SimpleNamespace(name="edge-2")
        view = EdgeServerDeleteView()
        view.request = request
        view.object = fake_edge

        with (
            patch.object(EdgeServerDeleteView, "get_object", return_value=fake_edge),
            patch("backoffice.views._promote_replacement_primary_on_delete", return_value=replacement) as promote_mock,
            patch("backoffice.views._render_local_haproxy_runtime", return_value=None) as render_mock,
        ):
            response = view.post(request, pk=10)

        self.assertEqual(response.status_code, 302)
        fake_edge.delete.assert_called_once()
        promote_mock.assert_called_once_with(10)
        render_mock.assert_called_once()

    def test_check_haproxy_edges_updates_health_snapshot(self):
        edge = SimpleNamespace(
            pk=1,
            name="edge-1",
            healthcheck_host="203.0.113.10",
            public_ip="203.0.113.10",
            public_host="connect.vxcloud.ru",
            healthcheck_port=443,
            frontend_port=443,
            is_active=True,
        )
        order_by_qs = [edge]
        filter_update_qs = MagicMock()

        with (
            patch("backoffice.management.commands.check_haproxy_edges.EdgeServer.objects.order_by", return_value=order_by_qs),
            patch("backoffice.management.commands.check_haproxy_edges.EdgeServer.objects.filter", return_value=filter_update_qs),
            patch("backoffice.management.commands.check_haproxy_edges.socket.create_connection", return_value=nullcontext()),
        ):
            call_command("check_haproxy_edges")

        update_kwargs = filter_update_qs.update.call_args.kwargs
        self.assertTrue(update_kwargs["last_health_ok"])
        self.assertEqual(update_kwargs["last_health_error"], "")
        self.assertIsNotNone(update_kwargs["last_health_at"])

    @patch.dict(
        os.environ,
        {
            "XUI_BASE_URL": "https://127.0.0.1:2053/panel",
            "XUI_USERNAME": "admin",
            "XUI_PASSWORD": "secret",
            "XUI_INBOUND_ID": "1",
            "VPN_PUBLIC_PORT": "443",
            "VPN_NODE_BACKEND_PORT": "29941",
            "MAIN_NODE_NAME": "node-local-test",
        },
        clear=False,
    )
    def test_ensure_local_main_node_uses_backend_port_env_not_public_port(self):
        filter_qs = MagicMock()
        filter_qs.order_by.return_value.first.return_value = None
        create_mock = MagicMock(return_value=SimpleNamespace(backend_port=29941))

        with (
            patch("backoffice.views.VPNNode.objects.filter", return_value=filter_qs),
            patch("backoffice.views.VPNNode.objects.create", create_mock),
        ):
            node = ensure_local_main_node()

        self.assertIsNotNone(node)
        self.assertEqual(node.backend_port, 29941)
        self.assertEqual(create_mock.call_args.kwargs["backend_port"], 29941)


if __name__ == "__main__":
    unittest.main()
