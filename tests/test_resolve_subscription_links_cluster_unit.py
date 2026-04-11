import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.bot import VPNBot
from src.config import Settings


def _settings(*, cluster_enabled: bool, sub_path: str = "/sub") -> Settings:
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
        xui_sub_path=sub_path,
    )


class ResolveSubscriptionLinksClusterUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_cluster_mode_uses_db_xui_sub_id_without_single_node_query(self):
        xui = AsyncMock()
        bot = VPNBot(
            app=SimpleNamespace(),
            settings=_settings(cluster_enabled=True),
            db=AsyncMock(),
            xui=xui,
            cms=None,
        )
        bot._restore_xui_profile_for_subscription = AsyncMock(return_value=("vless://restored", "restored-sub"))

        sub = {
            "id": 11,
            "vless_url": "vless://original",
            "client_uuid": "00000000-0000-0000-0000-000000000011",
            "inbound_id": 1,
            "xui_sub_id": "cluster-sub-001",
            "is_active": True,
            "revoked_at": None,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=10),
        }

        vless_url, sub_url = await bot._resolve_subscription_links(user_id=1, sub=sub)

        self.assertEqual(vless_url, "vless://original")
        self.assertEqual(sub_url, "https://vxcloud.ru:2096/sub/cluster-sub-001")
        xui.get_client_sub_id.assert_not_called()
        bot._restore_xui_profile_for_subscription.assert_not_awaited()

    async def test_single_node_mode_keeps_restore_flow(self):
        xui = AsyncMock()
        xui.get_client_sub_id = AsyncMock(return_value=None)
        bot = VPNBot(
            app=SimpleNamespace(),
            settings=_settings(cluster_enabled=False),
            db=AsyncMock(),
            xui=xui,
            cms=None,
        )
        bot._restore_xui_profile_for_subscription = AsyncMock(return_value=("vless://restored", "restored-sub"))

        sub = {
            "id": 12,
            "vless_url": "vless://original",
            "client_uuid": "00000000-0000-0000-0000-000000000012",
            "inbound_id": 7,
            "xui_sub_id": "db-sub-id",
            "is_active": True,
            "revoked_at": None,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=10),
        }

        vless_url, sub_url = await bot._resolve_subscription_links(user_id=2, sub=sub)

        self.assertEqual(vless_url, "vless://restored")
        self.assertEqual(sub_url, "https://vxcloud.ru:2096/sub/restored-sub")
        xui.get_client_sub_id.assert_awaited_once_with(7, "00000000-0000-0000-0000-000000000012")
        bot._restore_xui_profile_for_subscription.assert_awaited_once()

    async def test_subscription_links_use_configured_sub_path(self):
        xui = AsyncMock()
        bot = VPNBot(
            app=SimpleNamespace(),
            settings=_settings(cluster_enabled=True, sub_path="/8fK2mQp9xL7vR3nA5sD4wB1z"),
            db=AsyncMock(),
            xui=xui,
            cms=None,
        )

        sub = {
            "id": 13,
            "vless_url": "vless://original",
            "client_uuid": "00000000-0000-0000-0000-000000000013",
            "inbound_id": 1,
            "xui_sub_id": "cluster-sub-003",
            "is_active": True,
            "revoked_at": None,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=10),
        }

        _, sub_url = await bot._resolve_subscription_links(user_id=3, sub=sub)

        self.assertEqual(
            sub_url,
            "https://vxcloud.ru:2096/8fK2mQp9xL7vR3nA5sD4wB1z/cluster-sub-003",
        )


if __name__ == "__main__":
    unittest.main()
