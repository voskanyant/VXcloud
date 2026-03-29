import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from src.domain.subscriptions import activate_subscription


class ActivateSubscriptionIdempotencyUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_second_call_on_activated_order_is_idempotent_and_does_not_extend(self):
        now = datetime.now(timezone.utc)
        existing_expires_at = now + timedelta(days=10)

        db = AsyncMock()
        db.claim_order_for_activation.return_value = None
        db.get_order_by_id.return_value = {
            "id": 101,
            "user_id": 77,
            "status": "activated",
        }
        db.get_user_client_code.return_value = None
        db.get_active_subscription.return_value = {
            "id": 501,
            "expires_at": existing_expires_at,
            "vless_url": "vless://already",
            "xui_sub_id": "sub-777",
        }
        db.get_latest_subscription.return_value = None

        xui = AsyncMock()
        settings = AsyncMock()

        result = await activate_subscription(101, db=db, xui=xui, settings=settings)

        self.assertTrue(result.idempotent)
        self.assertFalse(result.created)
        self.assertEqual(result.subscription_id, 501)
        self.assertEqual(result.expires_at, existing_expires_at)

        xui.get_inbound.assert_not_called()
        db.extend_subscription.assert_not_called()
        db.create_subscription.assert_not_called()


if __name__ == "__main__":
    unittest.main()
