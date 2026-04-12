import os
import sys
import unittest
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
from django.http import HttpResponse
from django.test import RequestFactory
from django.views.generic import UpdateView

from backoffice.views import VPNNodeDeleteView, VPNNodeUpdateView, _render_local_haproxy_runtime


class BackofficeVPNNodeAutoRenderUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.staff_user, _ = User.objects.get_or_create(
            username="ops_vpn_node_staff",
            defaults={"email": "ops-vpn-node@example.com", "is_staff": True},
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

    def test_render_local_haproxy_runtime_uses_shared_runtime_output_path(self):
        completed = SimpleNamespace(returncode=0, stdout="ok", stderr="")

        with patch("backoffice.views.subprocess.run", return_value=completed) as run_mock:
            error = _render_local_haproxy_runtime()

        self.assertIsNone(error)
        command = run_mock.call_args.args[0]
        self.assertIn("--output-path", command)
        self.assertIn(str(PROJECT_ROOT / "ops" / "haproxy" / "runtime" / "haproxy.cfg"), command)
        self.assertIn("--skip-validate", command)
        self.assertIn("--skip-reload", command)

    def test_vpn_node_update_triggers_runtime_render(self):
        request = self._build_request("/ops/infra/nodes/10/edit/")
        form = SimpleNamespace(instance=SimpleNamespace(updated_at=None))
        view = VPNNodeUpdateView()
        view.request = request

        with (
            patch.object(UpdateView, "form_valid", return_value=HttpResponse("ok")) as super_form_valid,
            patch("backoffice.views._render_local_haproxy_runtime", return_value=None) as render_mock,
        ):
            response = view.form_valid(form)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(super_form_valid.called)
        self.assertTrue(render_mock.called)
        self.assertIsNotNone(form.instance.updated_at)

    def test_vpn_node_delete_triggers_runtime_render(self):
        request = self._build_request("/ops/infra/nodes/10/delete/")
        fake_node = SimpleNamespace(id=10, delete=MagicMock())
        view = VPNNodeDeleteView()
        view.request = request
        view.object = fake_node

        with (
            patch.object(VPNNodeDeleteView, "get_object", return_value=fake_node),
            patch("backoffice.views.VPNNodeClient.objects.filter") as filter_mock,
            patch("backoffice.views._render_local_haproxy_runtime", return_value=None) as render_mock,
        ):
            response = view.post(request, pk=10)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(filter_mock.return_value.delete.called)
        fake_node.delete.assert_called_once()
        render_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
