import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from src.config import Settings
from src.domain.subscriptions import activate_subscription


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="token",
        telegram_admin_id=1,
        database_url="postgresql://unused",
        xui_base_url="https://xui.local",
        xui_username="u",
        xui_password="p",
        xui_inbound_id=1,
        xui_sub_port=2096,
        vpn_public_host="vxcloud.ru",
        vpn_public_port=443,
        vpn_cluster_enabled=False,
        vpn_cluster_healthcheck_interval_seconds=30,
        vpn_cluster_sync_interval_seconds=60,
        vpn_cluster_sync_batch_size=200,
        vpn_rebalance_enabled=False,
        vpn_rebalance_interval_seconds=604800,
        vpn_rebalance_workflow_tick_seconds=60,
        vpn_rebalance_max_moves_per_node=50,
        vpn_rebalance_move_fraction=0.20,
        vpn_rebalance_cooldown_hours=168,
        vpn_rebalance_min_score_gap=2.5,
        vpn_alias_namespace="vpn.vxcloud.ru",
        vpn_alias_provider="cloudflare",
        vpn_alias_default_ttl=300,
        vpn_alias_cutover_ttl=60,
        vpn_alias_overlap_minutes=310,
        cloudflare_api_token=None,
        cloudflare_zone_id=None,
        vpn_tag="VXcloud",
        vpn_flow="xtls-rprx-vision",
        plan_days=30,
        plan_price_stars=250,
        card_payment_amount_minor=24900,
        card_payment_currency="RUB",
        max_devices_per_sub=1,
        price_text="Monthly plan",
        timezone="UTC",
        magic_link_shared_secret=None,
        magic_link_api_timeout_seconds=5,
        enforce_single_ip=False,
        single_ip_check_interval_seconds=20,
        single_ip_window_seconds=90,
        single_ip_block_seconds=120,
        xray_access_log_path="/var/log/xray/access.log",
    )


def _current_subscription(sub_id: int, *, user_id: int = 7) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    return {
        "id": sub_id,
        "user_id": user_id,
        "client_uuid": "00000000-0000-0000-0000-000000000001",
        "client_email": f"tg_{user_id}_seed",
        "expires_at": now + timedelta(days=10),
        "vless_url": "vless://existing",
        "xui_sub_id": "old-sub-id",
    }


def _xui_mock() -> MagicMock:
    xui = MagicMock()
    xui.parse_reality.return_value = SimpleNamespace(
        public_key="pubkey",
        short_id="abcd",
        sni="www.cloudflare.com",
        fingerprint="chrome",
    )
    xui.get_inbound = AsyncMock(return_value={"port": 443})
    xui.add_client = AsyncMock(return_value=None)
    xui.update_client = AsyncMock(return_value=None)
    xui.get_client_sub_id = AsyncMock(return_value="new-sub-id")
    return xui


class PayloadSelectionUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_renew_payload_targets_selected_subscription_when_owned(self):
        db = AsyncMock()
        db.claim_order_for_activation.return_value = {
            "id": 10,
            "user_id": 7,
            "status": "paid",
            "payload": "renew:7:123:1711:abc",
        }
        db.get_user_client_code.return_value = "VX-000007"
        db.get_user_identity.return_value = {
            "username": "user7",
            "first_name": "User",
            "client_code": "VX-000007",
        }
        db.get_subscription.return_value = _current_subscription(123)
        db.get_active_subscription.return_value = _current_subscription(999)

        result = await activate_subscription(10, db=db, xui=_xui_mock(), settings=_settings())

        db.get_subscription.assert_awaited_once_with(7, 123)
        db.get_active_subscription.assert_not_awaited()
        db.extend_subscription.assert_awaited_once()
        self.assertEqual(result.subscription_id, 123)
        self.assertFalse(result.created)
        self.assertFalse(result.idempotent)

    async def test_web_renew_payload_falls_back_to_active_when_selected_not_owned(self):
        db = AsyncMock()
        db.claim_order_for_activation.return_value = {
            "id": 11,
            "user_id": 7,
            "status": "paid",
            "payload": "web-renew:7:321:1711:abc",
        }
        db.get_user_client_code.return_value = "VX-000007"
        db.get_user_identity.return_value = {
            "username": "user7",
            "first_name": "User",
            "client_code": "VX-000007",
        }
        db.get_subscription.return_value = None
        db.get_active_subscription.return_value = _current_subscription(555)

        result = await activate_subscription(11, db=db, xui=_xui_mock(), settings=_settings())

        db.get_subscription.assert_awaited_once_with(7, 321)
        db.get_active_subscription.assert_awaited_once_with(7)
        db.extend_subscription.assert_awaited_once()
        self.assertEqual(result.subscription_id, 555)
        self.assertFalse(result.created)
        self.assertFalse(result.idempotent)

    async def test_buynew_payload_forces_new_config(self):
        db = AsyncMock()
        db.claim_order_for_activation.return_value = {
            "id": 12,
            "user_id": 7,
            "status": "paid",
            "payload": "buynew:7:1711:abc",
        }
        db.get_user_client_code.return_value = "VX-000007"
        db.get_user_identity.return_value = {
            "username": "user7",
            "first_name": "User",
            "client_code": "VX-000007",
        }
        db.get_active_subscription.return_value = _current_subscription(888)
        db.create_subscription.return_value = 7001

        result = await activate_subscription(12, db=db, xui=_xui_mock(), settings=_settings())

        db.get_active_subscription.assert_not_awaited()
        db.get_subscription.assert_not_awaited()
        db.create_subscription.assert_awaited_once()
        self.assertEqual(result.subscription_id, 7001)
        self.assertTrue(result.created)
        self.assertFalse(result.idempotent)

    async def test_web_newcfg_payload_forces_new_config(self):
        db = AsyncMock()
        db.claim_order_for_activation.return_value = {
            "id": 13,
            "user_id": 7,
            "status": "paid",
            "payload": "web-newcfg:7:1711:abc",
        }
        db.get_user_client_code.return_value = "VX-000007"
        db.get_user_identity.return_value = {
            "username": "user7",
            "first_name": "User",
            "client_code": "VX-000007",
        }
        db.get_active_subscription.return_value = _current_subscription(889)
        db.create_subscription.return_value = 7002

        result = await activate_subscription(13, db=db, xui=_xui_mock(), settings=_settings())

        db.get_active_subscription.assert_not_awaited()
        db.get_subscription.assert_not_awaited()
        db.create_subscription.assert_awaited_once()
        self.assertEqual(result.subscription_id, 7002)
        self.assertTrue(result.created)
        self.assertFalse(result.idempotent)


if __name__ == "__main__":
    unittest.main()
