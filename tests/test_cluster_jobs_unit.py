import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.cluster.jobs import _sync_manual_clients_from_canonical, healthcheck_tick, sync_tick
from src.xui_client import InboundClientState


class _FakeHealthXUI:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url
        self.username = username
        self.password = password

    async def start(self) -> None:
        if "down" in self.base_url:
            raise RuntimeError("node unavailable")

    async def close(self) -> None:
        return None

    async def get_inbound(self, inbound_id: int):  # noqa: ANN001
        return {"port": 29940, "id": inbound_id}

    def parse_reality(self, inbound):  # noqa: ANN001
        return SimpleNamespace(
            public_key="pubkey",
            short_id="ec40",
            sni="www.cloudflare.com",
            fingerprint="chrome",
        )


class _FakeManualSyncXUI:
    states: dict[str, list[InboundClientState]] = {}

    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def list_clients(self, inbound_id: int):  # noqa: ARG002
        return list(self.states.get(self.base_url, []))

    async def has_client(self, inbound_id: int, client_uuid: str, *, email: str | None = None):  # noqa: ARG002
        normalized_uuid = str(client_uuid).lower()
        normalized_email = str(email or "").strip().lower()
        return any(
            client.client_uuid.lower() == normalized_uuid
            or (normalized_email and client.email.strip().lower() == normalized_email)
            for client in self.states.get(self.base_url, [])
        )

    async def add_client(
        self,
        inbound_id: int,  # noqa: ARG002
        client_uuid: str,
        email: str,
        expiry: datetime,
        limit_ip: int = 0,
        flow: str = "",
        comment: str | None = None,
        sub_id: str | None = None,
        enable: bool = True,
    ) -> None:
        self.states.setdefault(self.base_url, []).append(
            InboundClientState(
                client_uuid=client_uuid,
                email=email,
                enabled=enable,
                expiry=expiry,
                limit_ip=limit_ip,
                flow=flow,
                sub_id=sub_id,
                comment=comment,
            )
        )

    async def update_client(
        self,
        inbound_id: int,  # noqa: ARG002
        client_uuid: str,
        email: str,
        expiry: datetime,
        limit_ip: int = 0,
        flow: str = "",
        comment: str | None = None,
        sub_id: str | None = None,
        enable: bool = True,
    ) -> None:
        clients = self.states.setdefault(self.base_url, [])
        for index, client in enumerate(clients):
            if client.client_uuid.lower() == str(client_uuid).lower():
                clients[index] = InboundClientState(
                    client_uuid=client_uuid,
                    email=email,
                    enabled=enable,
                    expiry=expiry,
                    limit_ip=limit_ip,
                    flow=flow,
                    sub_id=sub_id,
                    comment=comment,
                )
                return
        await self.add_client(
            inbound_id,
            client_uuid,
            email,
            expiry,
            limit_ip=limit_ip,
            flow=flow,
            comment=comment,
            sub_id=sub_id,
            enable=enable,
        )

    async def del_client(
        self,
        inbound_id: int,  # noqa: ARG002
        client_uuid: str,
        *,
        email: str | None = None,
        expiry: datetime | None = None,  # noqa: ARG002
        limit_ip: int = 0,  # noqa: ARG002
        flow: str = "",  # noqa: ARG002
        comment: str | None = None,  # noqa: ARG002
        sub_id: str | None = None,  # noqa: ARG002
    ) -> str:
        normalized_uuid = str(client_uuid).lower()
        normalized_email = str(email or "").strip().lower()
        self.states[self.base_url] = [
            client
            for client in self.states.get(self.base_url, [])
            if client.client_uuid.lower() != normalized_uuid
            and client.email.strip().lower() != normalized_email
        ]
        return "deleted"


class ClusterJobsUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_healthcheck_tick_marks_ok_and_failed_nodes(self):
        db = AsyncMock()
        db.get_active_vpn_nodes.return_value = [
            {
                "id": 1,
                "xui_base_url": "https://node-ok.local",
                "xui_username": "u1",
                "xui_password": "p1",
                "xui_inbound_id": 1,
                "is_active": True,
            },
            {
                "id": 2,
                "xui_base_url": "https://node-down.local",
                "xui_username": "u2",
                "xui_password": "p2",
                "xui_inbound_id": 1,
                "is_active": True,
            },
        ]

        with patch("src.cluster.jobs.XUIClient", new=_FakeHealthXUI):
            result = await healthcheck_tick(db)

        self.assertEqual(result["checked"], 2)
        self.assertEqual(result["ok"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(db.mark_node_health.await_count, 2)

    async def test_sync_tick_retries_duplicate_with_update(self):
        db = AsyncMock()
        db.get_cluster_sync_nodes.return_value = [
            {
                "id": 10,
                "xui_base_url": "https://node.local",
                "xui_username": "u",
                "xui_password": "p",
                "xui_inbound_id": 1,
                "is_active": True,
                "lb_enabled": True,
            }
        ]
        db.list_subscriptions_needing_sync.side_effect = [
            [
                {
                    "subscription_id": 101,
                    "client_uuid": "00000000-0000-0000-0000-000000000101",
                    "client_email": "tg_1_101",
                    "xui_sub_id": "sid-101",
                    "desired_enabled": True,
                    "desired_expires_at": datetime.now(timezone.utc) + timedelta(days=10),
                    "sync_state": "pending",
                }
            ],
            [],
        ]
        settings = SimpleNamespace(
            vpn_cluster_sync_batch_size=100,
            max_devices_per_sub=1,
            vpn_flow="xtls-rprx-vision",
        )

        with (
            patch(
                "src.cluster.jobs.create_client_on_node",
                new=AsyncMock(side_effect=RuntimeError("already exists")),
            ) as create_mock,
            patch(
                "src.cluster.jobs.update_client_on_node",
                new=AsyncMock(return_value={"xui_sub_id": "sid-101"}),
            ) as update_mock,
            patch(
                "src.cluster.jobs.delete_or_disable_client_on_node",
                new=AsyncMock(return_value={"xui_sub_id": "sid-101"}),
            ) as delete_mock,
            patch(
                "src.cluster.jobs._sync_manual_clients_from_canonical",
                new=AsyncMock(return_value={"processed": 0, "failed": 0}),
            ),
        ):
            result = await sync_tick(db, settings)

        self.assertEqual(result["nodes"], 1)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["ok"], 1)
        self.assertEqual(result["failed"], 0)
        create_mock.assert_awaited_once()
        update_mock.assert_awaited_once()
        delete_mock.assert_not_awaited()

        upsert_kwargs = db.upsert_vpn_node_client_state.await_args.kwargs
        self.assertEqual(upsert_kwargs["sync_state"], "ok")
        self.assertTrue(upsert_kwargs["desired_enabled"])

    async def test_manual_3xui_clients_are_mirrored_from_canonical_node(self):
        now = datetime.now(timezone.utc) + timedelta(days=7)
        db = AsyncMock()
        db.list_subscription_client_identities.return_value = []
        nodes = [
            {
                "id": 1,
                "xui_base_url": "https://node-1.local",
                "xui_username": "u1",
                "xui_password": "p1",
                "xui_inbound_id": 1,
                "is_active": True,
                "lb_enabled": True,
                "last_health_ok": True,
            },
            {
                "id": 2,
                "xui_base_url": "https://node-2.local",
                "xui_username": "u2",
                "xui_password": "p2",
                "xui_inbound_id": 1,
                "is_active": True,
                "lb_enabled": True,
                "last_health_ok": True,
            },
        ]
        _FakeManualSyncXUI.states = {
            "https://node-1.local": [
                InboundClientState(
                    client_uuid="00000000-0000-0000-0000-000000000201",
                    email="manual-import@example.com",
                    enabled=True,
                    expiry=now,
                    limit_ip=1,
                    flow="xtls-rprx-vision",
                    sub_id="manual-sub-201",
                )
            ],
            "https://node-2.local": [],
        }

        with patch("src.cluster.jobs.XUIClient", new=_FakeManualSyncXUI):
            result = await _sync_manual_clients_from_canonical(db, nodes)

        self.assertEqual(result["canonical_node_id"], 1)
        self.assertEqual(result["followers"], 1)
        self.assertEqual(result["manual_clients"], 1)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["failed"], 0)
        follower_clients = _FakeManualSyncXUI.states["https://node-2.local"]
        self.assertEqual(len(follower_clients), 1)
        self.assertEqual(follower_clients[0].email, "manual-import@example.com")


if __name__ == "__main__":
    unittest.main()
