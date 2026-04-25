import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.bot import VPNBot
from src.config import Settings


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
        vpn_public_host="vxcloud.ru",
        vpn_public_port=29940,
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
        vpn_alias_namespace="connect.vxcloud.ru",
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
        xui_sub_path="/sub",
    )


class ResolveSubscriptionLinksClusterUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_existing_vless_and_vxcloud_feed_url(self):
        xui = AsyncMock()
        db = AsyncMock()
        bot = VPNBot(
            app=SimpleNamespace(),
            settings=_settings(cluster_enabled=True),
            db=db,
            xui=xui,
        )

        sub = {
            "id": 11,
            "vless_url": "vless://original",
            "client_uuid": "00000000-0000-0000-0000-000000000011",
            "inbound_id": 1,
            "feed_token": "feed-token-001",
            "is_active": True,
            "revoked_at": None,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=10),
        }

        vless_url, feed_url = await bot._resolve_subscription_links(user_id=1, sub=sub)

        self.assertEqual(vless_url, "vless://original")
        self.assertEqual(feed_url, "https://vxcloud.ru/account/feed/feed-token-001/")
        db.ensure_subscription_feed_token.assert_not_called()
        xui.get_client_sub_id.assert_not_called()

    async def test_feed_url_backfills_token_when_missing(self):
        xui = AsyncMock()
        db = AsyncMock()
        db.ensure_subscription_feed_token = AsyncMock(return_value="generated-feed-token")
        bot = VPNBot(
            app=SimpleNamespace(),
            settings=_settings(cluster_enabled=False),
            db=db,
            xui=xui,
        )

        sub = {
            "id": 12,
            "vless_url": "vless://original",
            "client_uuid": "00000000-0000-0000-0000-000000000012",
            "inbound_id": 7,
            "feed_token": "",
            "is_active": True,
            "revoked_at": None,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=10),
        }

        vless_url, feed_url = await bot._resolve_subscription_links(user_id=2, sub=sub)

        self.assertEqual(vless_url, "vless://original")
        self.assertEqual(feed_url, "https://vxcloud.ru/account/feed/generated-feed-token/")
        db.ensure_subscription_feed_token.assert_awaited_once_with(12)
        xui.get_client_sub_id.assert_not_called()

    async def test_feed_url_is_none_when_token_cannot_be_resolved(self):
        xui = AsyncMock()
        db = AsyncMock()
        db.ensure_subscription_feed_token = AsyncMock(return_value=None)
        bot = VPNBot(
            app=SimpleNamespace(),
            settings=_settings(cluster_enabled=True),
            db=db,
            xui=xui,
        )

        sub = {
            "id": 13,
            "vless_url": "vless://original",
            "client_uuid": "00000000-0000-0000-0000-000000000013",
            "inbound_id": 1,
            "feed_token": "",
            "is_active": True,
            "revoked_at": None,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=10),
        }

        _, feed_url = await bot._resolve_subscription_links(user_id=3, sub=sub)

        self.assertIsNone(feed_url)
        db.ensure_subscription_feed_token.assert_awaited_once_with(13)


if __name__ == "__main__":
    unittest.main()
