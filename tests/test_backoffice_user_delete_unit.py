import os
import sys
import unittest
from datetime import timedelta
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
from django.utils import timezone

from backoffice.views import BotUserDeleteView


class BackofficeUserDeleteUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.staff_user, _ = User.objects.get_or_create(
            username="ops_delete_staff",
            defaults={"email": "ops-delete@example.com", "is_staff": True},
        )
        self.staff_user.is_staff = True
        self.staff_user.set_password("pass12345")
        self.staff_user.save()

    def _build_request(self):
        request = self.factory.post("/ops/bot/users/5/delete/")
        request.user = self.staff_user
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def test_delete_is_blocked_when_active_subscriptions_exist(self):
        bot_user = SimpleNamespace(id=5, telegram_id=78050167, delete=MagicMock())
        counts = {
            "subscriptions": 2,
            "active_subscriptions": 1,
            "orders": 4,
            "node_clients": 2,
            "support_tickets": 1,
            "support_messages": 3,
            "linked_accounts": 1,
        }

        with (
            patch.object(BotUserDeleteView, "get_object", return_value=bot_user),
            patch.object(BotUserDeleteView, "_related_counts", return_value=counts),
        ):
            response = BotUserDeleteView.as_view()(self._build_request(), pk=5)

        self.assertEqual(response.status_code, 200)
        bot_user.delete.assert_not_called()

    def test_related_counts_treat_expired_subscriptions_as_inactive(self):
        bot_user = SimpleNamespace(id=5, telegram_id=78050167)
        now = timezone.now()
        expired_sub_1 = SimpleNamespace(id=101, is_active=True, expires_at=now - timedelta(days=1), revoked_at=None)
        expired_sub_2 = SimpleNamespace(id=102, is_active=True, expires_at=now - timedelta(minutes=5), revoked_at=None)

        class _FakeListQuerySet(list):
            pass

        subscriptions_qs = _FakeListQuerySet([expired_sub_1, expired_sub_2])

        with (
            patch("backoffice.views.BotSubscription.objects.filter", return_value=subscriptions_qs),
            patch("backoffice.views.BotOrder.objects.filter") as order_filter,
            patch("backoffice.views.VPNNodeClient.objects.filter") as node_filter,
            patch("backoffice.views.SupportTicket.objects.filter") as ticket_filter,
            patch("backoffice.views.SupportMessage.objects.filter") as message_filter,
            patch("backoffice.views.LinkedAccount.objects.filter") as linked_filter,
        ):
            order_filter.return_value.count.return_value = 0
            node_filter.return_value.count.return_value = 0
            ticket_filter.return_value.count.return_value = 0
            message_filter.return_value.count.return_value = 0
            linked_filter.return_value.count.return_value = 0

            view = BotUserDeleteView()
            counts = view._related_counts(bot_user)

        self.assertEqual(counts["subscriptions"], 2)
        self.assertEqual(counts["active_subscriptions"], 0)


if __name__ == "__main__":
    unittest.main()
