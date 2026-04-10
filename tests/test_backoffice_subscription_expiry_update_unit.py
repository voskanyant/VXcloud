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

from backoffice.views import BotSubscriptionExpiryUpdateView


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


if __name__ == "__main__":
    unittest.main()
