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
from django.test import RequestFactory

from backoffice.views import BotUserCreateView, BotUserPasswordResetView


class BackofficeUserAdminUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.staff_user, _ = User.objects.get_or_create(
            username="ops_user_admin_staff",
            defaults={"email": "ops-user-admin@example.com", "is_staff": True},
        )
        self.staff_user.is_staff = True
        self.staff_user.set_password("pass12345")
        self.staff_user.save()

    def _attach_state(self, request):
        request.user = self.staff_user
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def test_create_view_generates_password_and_allows_blank_email(self):
        request = self._attach_state(
            self.factory.post(
                "/ops/bot/users/new/",
                {
                    "username": "betauser",
                    "first_name": "Beta User",
                    "email": "",
                    "password": "",
                },
            )
        )
        fake_auth_user = SimpleNamespace(id=123)
        fake_bot_user = SimpleNamespace(id=77, client_code="", save=MagicMock())

        with (
            patch("backoffice.forms.User.objects.filter") as user_filter,
            patch("backoffice.views.generate_admin_password", return_value="AutoPass234"),
            patch("backoffice.views.User.objects.create_user", return_value=fake_auth_user) as create_user,
            patch("backoffice.views.BotUser.objects.create", return_value=fake_bot_user) as create_bot_user,
        ):
            user_filter.return_value.exists.return_value = False
            response = BotUserCreateView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        create_user.assert_called_once_with(
            username="betauser",
            email="",
            password="AutoPass234",
            first_name="Beta User",
        )
        create_bot_user.assert_called_once()
        self.assertEqual(create_bot_user.call_args.kwargs["telegram_id"], -(10**12 + 123))
        fake_bot_user.save.assert_called_once_with(update_fields=["client_code"])
        self.assertEqual(fake_bot_user.client_code, "VX-000077")

    def test_password_reset_generates_password_for_site_only_user(self):
        request = self._attach_state(
            self.factory.post(
                "/ops/bot/users/5/password/",
                {
                    "password": "",
                },
            )
        )
        bot_user = SimpleNamespace(id=5, telegram_id=-(10**12 + 555), username="siteuser", first_name="Site User")
        auth_user = MagicMock()
        auth_user.username = "siteuser"

        with (
            patch("backoffice.views.get_object_or_404", return_value=bot_user),
            patch("backoffice.views._site_auth_user_for_bot_user", return_value=auth_user),
            patch("backoffice.views.generate_admin_password", return_value="ResetPass234"),
        ):
            response = BotUserPasswordResetView.as_view()(request, pk=5)

        self.assertEqual(response.status_code, 302)
        auth_user.set_password.assert_called_once_with("ResetPass234")
        auth_user.save.assert_called_once_with(update_fields=["password"])


if __name__ == "__main__":
    unittest.main()
