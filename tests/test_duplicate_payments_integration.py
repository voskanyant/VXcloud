import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.bot import VPNBot
from src.config import Settings
from src.db import DB


class FakePool:
    def __init__(self) -> None:
        self.events: dict[tuple[str, str], dict[str, object]] = {}

    async def fetchrow(self, query: str, *args):
        if "INSERT INTO payment_events" in query:
            provider, event_id, body_json = args
            key = (provider, event_id)
            if key in self.events:
                return None
            self.events[key] = {
                "id": len(self.events) + 1,
                "provider": provider,
                "event_id": event_id,
                "body": json.loads(body_json),
                "processed": False,
            }
            return {"id": self.events[key]["id"]}

        if "UPDATE payment_events" in query and "processed_at" in query:
            provider, event_id = args
            event = self.events.get((provider, event_id))
            if not event:
                return None
            event["processed"] = True
            return {"id": event["id"]}

        raise AssertionError(f"Unexpected query: {query}")


class FakeMessage:
    def __init__(self, successful_payment):
        self.successful_payment = successful_payment
        self.replies: list[str] = []

    async def reply_text(self, text, reply_markup=None):
        self.replies.append(text)


class DuplicatePaymentsIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_stars_duplicate_charge_id_is_ignored_and_subscription_is_returned(self):
        settings = Settings(
            telegram_bot_token="t",
            telegram_admin_id=0,
            database_url="postgresql://unused",
            xui_base_url="https://xui.local",
            xui_username="u",
            xui_password="p",
            xui_inbound_id=1,
            xui_sub_port=2096,
            vpn_public_host="vpn.local",
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
            vpn_tag="VPN",
            vpn_flow="xtls-rprx-vision",
            plan_days=30,
            plan_price_stars=250,
            card_payment_amount_minor=24900,
            card_payment_currency="RUB",
            max_devices_per_sub=1,
            price_text="Monthly",
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

        db = AsyncMock()
        db.get_order_by_payload.return_value = {
            "id": 1001,
            "user_id": 555,
            "status": "pending",
        }
        db.get_user_client_code.return_value = None
        db.is_charge_processed.return_value = True

        bot = VPNBot(app=SimpleNamespace(), settings=settings, db=db, xui=AsyncMock(), cms=None)
        bot.mysub = AsyncMock()

        payment = SimpleNamespace(
            invoice_payload="payload-1",
            telegram_payment_charge_id="tg_charge_123",
            provider_payment_charge_id="prov_123",
        )
        message = FakeMessage(successful_payment=payment)
        update = SimpleNamespace(message=message)

        await bot.successful_payment(update, SimpleNamespace())

        self.assertTrue(message.replies)
        bot.mysub.assert_awaited_once()
        db.mark_order_paid_if_pending.assert_not_called()

    async def test_card_duplicate_event_id_flow_insert_then_duplicate(self):
        db = DB("postgresql://unused")
        db.pool = FakePool()

        first_new = await db.insert_payment_event_if_new("reference", "evt-card-1", {"status": "success"})
        marked = await db.mark_payment_event_processed("reference", "evt-card-1")
        second_new = await db.insert_payment_event_if_new("reference", "evt-card-1", {"status": "success"})

        self.assertTrue(first_new)
        self.assertTrue(marked)
        self.assertFalse(second_new)


if __name__ == "__main__":
    unittest.main()
