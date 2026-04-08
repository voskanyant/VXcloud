import os
import sys
import unittest
from pathlib import Path
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

from cabinet.views import _build_public_absolute_url


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


if __name__ == "__main__":
    unittest.main()
