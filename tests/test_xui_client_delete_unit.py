import asyncio
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from src.xui_client import (
    NO_EXPIRY_SENTINEL,
    RESERVED_PLACEHOLDER_COMMENT,
    RESERVED_PLACEHOLDER_EMAIL,
    XUIClient,
)


class XUIClientDeleteUnitTests(unittest.TestCase):
    def test_last_client_delete_becomes_reserved_placeholder(self):
        client = XUIClient("https://panel.local", "user", "pass")
        client._post = AsyncMock(side_effect=RuntimeError("Something went wrong (no client remained in Inbound)"))
        client.update_client = AsyncMock()
        client.set_client_enabled = AsyncMock()

        result = asyncio.run(
            client.del_client(
                1,
                "11111111-1111-1111-1111-111111111111",
                email="user@example.com",
                expiry=datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
                limit_ip=1,
                flow="xtls-rprx-vision",
                sub_id="abc123",
            )
        )

        self.assertEqual(result, "placeholder")
        client.update_client.assert_awaited_once_with(
            1,
            "11111111-1111-1111-1111-111111111111",
            RESERVED_PLACEHOLDER_EMAIL,
            NO_EXPIRY_SENTINEL,
            limit_ip=0,
            flow="",
            comment=RESERVED_PLACEHOLDER_COMMENT,
            sub_id=None,
            enable=False,
        )
        client.set_client_enabled.assert_not_awaited()

    def test_non_last_client_delete_falls_back_to_disable(self):
        client = XUIClient("https://panel.local", "user", "pass")
        client._post = AsyncMock(side_effect=RuntimeError("random delete failure"))
        client.update_client = AsyncMock()
        client.set_client_enabled = AsyncMock()
        expiry = datetime(2026, 1, 1, tzinfo=timezone.utc)

        result = asyncio.run(
            client.del_client(
                1,
                "11111111-1111-1111-1111-111111111111",
                email="user@example.com",
                expiry=expiry,
                limit_ip=1,
                flow="xtls-rprx-vision",
                sub_id="abc123",
            )
        )

        self.assertEqual(result, "disabled")
        client.update_client.assert_not_awaited()
        client.set_client_enabled.assert_awaited_once()

    def test_client_traffic_stats_parse_inbound_list(self):
        client = XUIClient("https://panel.local", "user", "pass")
        client.list_inbounds = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "clientStats": [
                        {
                            "email": "client@example.com",
                            "uuid": "11111111-1111-1111-1111-111111111111",
                            "subId": "sub-1",
                            "up": 100,
                            "down": 200,
                            "allTime": 300,
                            "lastOnline": 1_777_777_777,
                            "enable": True,
                        }
                    ],
                }
            ]
        )

        rows = asyncio.run(client.list_client_traffic_stats(1))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].email, "client@example.com")
        self.assertEqual(rows[0].up_bytes, 100)
        self.assertEqual(rows[0].down_bytes, 200)
        self.assertEqual(rows[0].all_time_bytes, 300)
        self.assertTrue(rows[0].enabled)
        self.assertIsNotNone(rows[0].last_online)

    def test_update_client_retries_direct_settings_for_empty_client_id_panels(self):
        client = XUIClient("https://panel.local", "user", "pass")
        client._post = AsyncMock(side_effect=[RuntimeError("Something went wrong (empty client ID\n)"), {"success": True}])

        asyncio.run(
            client.set_client_enabled(
                1,
                "11111111-1111-1111-1111-111111111111",
                "client@example.com",
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                enable=True,
                limit_ip=0,
                flow="xtls-rprx-vision",
                comment="Client",
            )
        )

        self.assertEqual(client._post.await_count, 2)
        first_payload = client._post.await_args_list[0].args[1]
        second_payload = client._post.await_args_list[1].args[1]
        self.assertIn("clients", json.loads(first_payload["settings"]))
        direct_settings = json.loads(second_payload["settings"])
        self.assertEqual(direct_settings["id"], "11111111-1111-1111-1111-111111111111")
        self.assertEqual(direct_settings["email"], "client@example.com")
        self.assertNotIn("clients", direct_settings)


if __name__ == "__main__":
    unittest.main()
