from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from src.cluster.rebalance import preview_rebalance_plan


def _settings(**overrides):
    base = dict(
        timezone="UTC",
        vpn_rebalance_cooldown_hours=168,
        vpn_rebalance_max_moves_per_node=50,
        vpn_rebalance_move_fraction=0.20,
        vpn_rebalance_min_score_gap=2.5,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _node(
    node_id: int,
    *,
    pool: str = "default",
    active_assigned: int = 0,
    observed_enabled: int = 0,
    weekly_traffic_bytes: int = 0,
    peak_concurrency: int = 0,
    p95_concurrency: int = 0,
    p95_probe_latency_ms: int = 0,
    health_failures: int = 0,
    moves_in_week: int = 0,
    weight: int = 100,
    bandwidth_capacity_mbps: int = 1000,
    connection_capacity: int = 10000,
    lb_enabled: bool = True,
    is_active: bool = True,
    needs_backfill: bool = False,
    last_health_ok: bool = True,
) -> dict:
    return {
        "id": node_id,
        "name": f"node-{node_id}",
        "compatibility_pool": pool,
        "active_assigned_subscriptions": active_assigned,
        "observed_enabled_clients": observed_enabled,
        "weekly_traffic_bytes": weekly_traffic_bytes,
        "peak_concurrency": peak_concurrency,
        "p95_concurrency": p95_concurrency,
        "p95_probe_latency_ms": p95_probe_latency_ms,
        "health_failures": health_failures,
        "moves_in_week": moves_in_week,
        "backend_weight": weight,
        "bandwidth_capacity_mbps": bandwidth_capacity_mbps,
        "connection_capacity": connection_capacity,
        "lb_enabled": lb_enabled,
        "is_active": is_active,
        "needs_backfill": needs_backfill,
        "last_health_ok": last_health_ok,
        "last_reality_public_key": "pubkey",
        "last_reality_short_id": "abcd1234",
        "last_reality_sni": "www.apple.com",
        "last_reality_fingerprint": "chrome",
    }


class RebalancePreviewUnitTests(IsolatedAsyncioTestCase):
    async def test_preview_plans_move_within_same_pool(self):
        db = AsyncMock()
        db.list_node_assignment_metrics.return_value = [
            _node(
                1,
                active_assigned=20,
                observed_enabled=18,
                weekly_traffic_bytes=80 * 1024 * 1024 * 1024,
                peak_concurrency=30,
                p95_concurrency=24,
                p95_probe_latency_ms=120,
            ),
            _node(
                2,
                active_assigned=3,
                observed_enabled=2,
                weekly_traffic_bytes=4 * 1024 * 1024 * 1024,
                peak_concurrency=4,
                p95_concurrency=3,
                p95_probe_latency_ms=20,
            ),
            _node(
                3,
                pool="premium",
                active_assigned=1,
                observed_enabled=1,
                weekly_traffic_bytes=1 * 1024 * 1024 * 1024,
                peak_concurrency=1,
                p95_concurrency=1,
                p95_probe_latency_ms=15,
            ),
        ]
        db.list_rebalance_candidates.side_effect = [
            [
                {
                    "id": 101,
                    "display_name": "heavy-user",
                    "client_email": "heavy@example.com",
                    "alias_fqdn": "u-heavy.connect.vxcloud.ru",
                    "vless_url": "vless://heavy",
                }
            ],
            [],
        ]

        preview = await preview_rebalance_plan(db, _settings())

        self.assertEqual(preview["summary"]["planned_moves"], 1)
        self.assertEqual(preview["summary"]["eligible_nodes"], 3)
        self.assertEqual(preview["summary"]["compatible_pools"], 2)
        self.assertEqual(len(preview["moves"]), 1)
        self.assertEqual(preview["moves"][0]["subscription_id"], 101)
        self.assertEqual(preview["moves"][0]["from_node_id"], 1)
        self.assertEqual(preview["moves"][0]["to_node_id"], 2)
        self.assertEqual(preview["moves"][0]["compatibility_pool"], "default")

    async def test_preview_respects_min_score_gap(self):
        db = AsyncMock()
        db.list_node_assignment_metrics.return_value = [
            _node(
                1,
                active_assigned=5,
                observed_enabled=5,
                weekly_traffic_bytes=5 * 1024 * 1024 * 1024,
                peak_concurrency=5,
                p95_concurrency=5,
                p95_probe_latency_ms=25,
            ),
            _node(
                2,
                active_assigned=4,
                observed_enabled=4,
                weekly_traffic_bytes=4 * 1024 * 1024 * 1024,
                peak_concurrency=4,
                p95_concurrency=4,
                p95_probe_latency_ms=20,
            ),
        ]
        db.list_rebalance_candidates.return_value = [
            {
                "id": 102,
                "display_name": "stable-user",
                "client_email": "stable@example.com",
                "alias_fqdn": "u-stable.connect.vxcloud.ru",
                "vless_url": "vless://stable",
            }
        ]

        preview = await preview_rebalance_plan(db, _settings(vpn_rebalance_min_score_gap=50.0))

        self.assertEqual(preview["summary"]["planned_moves"], 0)
        self.assertEqual(preview["moves"], [])
