import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from src.config import Settings
from src.domain.subscriptions import activate_subscription


def _settings(*, cluster_enabled: bool) -> Settings:
    return Settings(
        telegram_bot_token="token",
        telegram_admin_id=1,
        database_url="postgresql://unused",
        xui_base_url="https://xui.local",
        xui_username="u",
        xui_password="p",
        xui_inbound_id=1,
        xui_sub_port=2096,
        vpn_public_host="connect.vxcloud.ru",
        vpn_public_port=443,
        vpn_cluster_enabled=cluster_enabled,
        vpn_cluster_healthcheck_interval_seconds=30,
        vpn_cluster_sync_interval_seconds=60,
        vpn_cluster_sync_batch_size=200,
        vpn_rebalance_enabled=cluster_enabled,
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
        cms_base_url=None,
        cms_token=None,
        cms_content_collection="bot_content",
        cms_button_collection="bot_buttons",
        cms_cache_ttl_seconds=60,
        magic_link_shared_secret=None,
        magic_link_api_timeout_seconds=5,
        enforce_single_ip=False,
        single_ip_check_interval_seconds=20,
        single_ip_window_seconds=90,
        single_ip_block_seconds=120,
        xray_access_log_path="/var/log/xray/access.log",
    )


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
    xui.get_client_sub_id = AsyncMock(return_value="single-node-sub-id")
    return xui


class ActivateSubscriptionClusterModeUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_node_mode_keeps_single_node_link_and_assignment_empty(self):
        now = datetime.now(timezone.utc)
        db = AsyncMock()
        db.claim_order_for_activation.return_value = {
            "id": 501,
            "user_id": 7,
            "status": "paid",
            "payload": "renew:7:777:1711:abc",
        }
        db.get_user_client_code.return_value = "VX-000007"
        db.get_user_identity.return_value = {
            "username": "user7",
            "first_name": "User",
            "client_code": "VX-000007",
        }
        db.get_subscription.return_value = {
            "id": 777,
            "user_id": 7,
            "client_uuid": "00000000-0000-0000-0000-000000000001",
            "client_email": "tg_7_seed",
            "expires_at": now + timedelta(days=10),
            "vless_url": "vless://existing",
            "xui_sub_id": "sub-old",
        }
        db.get_active_subscription.return_value = None
        db.ensure_subscription_feed_token = AsyncMock(return_value="feed-token-777")

        result = await activate_subscription(
            501,
            db=db,
            xui=_xui_mock(),
            settings=_settings(cluster_enabled=False),
        )

        self.assertEqual(result.subscription_id, 777)
        self.assertFalse(result.created)
        self.assertFalse(result.idempotent)
        db.extend_subscription.assert_awaited_once()
        extend_kwargs = db.extend_subscription.await_args.kwargs
        self.assertIsNone(extend_kwargs["assigned_node_id"])
        self.assertEqual(extend_kwargs["migration_state"], "ready")
        self.assertIn("@connect.vxcloud.ru:443", result.vless_url)
        self.assertEqual(result.feed_token, "feed-token-777")

    async def test_cluster_mode_assigns_one_best_node_and_uses_alias_link(self):
        db = AsyncMock()
        db.claim_order_for_activation.return_value = {
            "id": 601,
            "user_id": 9,
            "status": "paid",
            "payload": "buynew:9:1711:abc",
        }
        db.get_user_client_code.return_value = "VX-000009"
        db.get_user_identity.return_value = {
            "username": "user9",
            "first_name": "User",
            "client_code": "VX-000009",
        }
        db.get_active_subscription.return_value = None
        db.create_subscription.return_value = 9001
        db.ensure_subscription_feed_token = AsyncMock(return_value="feed-token-9001")

        assigned_node = {
            "id": 1,
            "name": "node-1-main",
            "backend_host": "de1.vxcloud.ru",
            "backend_port": 443,
            "public_ip": "116.202.10.113",
            "compatibility_pool": "default",
            "xui_base_url": "https://node-1.local",
            "xui_username": "u1",
            "xui_password": "p1",
            "xui_inbound_id": 1,
        }
        inbound = {"port": 443, "id": 1}
        reality = SimpleNamespace(
            public_key="cluster-pubkey",
            short_id="ec40",
            sni="www.cloudflare.com",
            fingerprint="chrome",
        )

        with (
            patch(
                "src.domain.subscriptions._pick_subscription_node",
                new=AsyncMock(return_value=(assigned_node, inbound, reality, 1, "scored_best")),
            ),
            patch(
                "src.domain.subscriptions.create_client_on_node",
                new=AsyncMock(return_value={"node_id": 1, "ok": True, "xui_sub_id": "cluster-sub-id"}),
            ) as create_mock,
            patch(
                "src.domain.subscriptions.ensure_subscription_alias_record",
                new=AsyncMock(return_value=SimpleNamespace(record_id="dns-1", provider="cloudflare", change_id="chg-1", ttl=300)),
            ),
        ):
            result = await activate_subscription(
                601,
                db=db,
                xui=_xui_mock(),
                settings=_settings(cluster_enabled=True),
            )

        create_mock.assert_awaited_once()
        create_kwargs = db.create_subscription.await_args.kwargs
        self.assertEqual(create_kwargs["assigned_node_id"], 1)
        self.assertEqual(create_kwargs["current_node_id"], 1)
        self.assertEqual(create_kwargs["assignment_source"], "new")
        self.assertEqual(create_kwargs["migration_state"], "ready")
        self.assertEqual(create_kwargs["assignment_state"], "steady")
        self.assertTrue(str(create_kwargs["alias_fqdn"]).endswith(".vpn.vxcloud.ru"))
        self.assertIn(f"@{create_kwargs['alias_fqdn']}:443", create_kwargs["vless_url"])
        self.assertEqual(result.vless_url, create_kwargs["vless_url"])
        self.assertEqual(result.feed_token, "feed-token-9001")
        self.assertTrue(result.created)
        self.assertFalse(result.idempotent)


if __name__ == "__main__":
    unittest.main()
