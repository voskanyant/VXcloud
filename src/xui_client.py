from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import aiohttp


@dataclass
class InboundRealityInfo:
    public_key: str
    short_id: str
    sni: str
    fingerprint: str


class XUIClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
        await self.login()

    async def close(self) -> None:
        if self._session:
            await self._session.close()

    async def login(self) -> None:
        assert self._session is not None
        payload = {"username": self.username, "password": self.password}
        async with self._session.post(f"{self.base_url}/login", json=payload, ssl=False) as resp:
            data = await resp.json(content_type=None)
            if not data.get("success"):
                raise RuntimeError(f"x-ui login failed: {data}")

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        assert self._session is not None
        async with self._session.post(f"{self.base_url}{path}", json=payload, ssl=False) as resp:
            data = await resp.json(content_type=None)
            if not data.get("success"):
                raise RuntimeError(f"x-ui request failed for {path}: {data}")
            return data

    async def _get(self, path: str) -> dict[str, Any]:
        assert self._session is not None
        async with self._session.get(f"{self.base_url}{path}", ssl=False) as resp:
            data = await resp.json(content_type=None)
            if not data.get("success"):
                raise RuntimeError(f"x-ui request failed for {path}: {data}")
            return data

    async def get_inbound(self, inbound_id: int) -> dict[str, Any]:
        data = await self._get(f"/panel/api/inbounds/get/{inbound_id}")
        return data["obj"]

    async def add_client(
        self,
        inbound_id: int,
        client_uuid: str,
        email: str,
        expiry: datetime,
        limit_ip: int = 0,
    ) -> None:
        expiry_ms = int(expiry.timestamp() * 1000)
        client = {
            "id": client_uuid,
            "email": email,
            "limitIp": limit_ip,
            "totalGB": 0,
            "expiryTime": expiry_ms,
            "enable": True,
            "flow": "",
        }
        settings = json.dumps({"clients": [client]}, separators=(",", ":"))
        await self._post("/panel/api/inbounds/addClient", {"id": inbound_id, "settings": settings})

    async def update_client(
        self,
        inbound_id: int,
        client_uuid: str,
        email: str,
        expiry: datetime,
        limit_ip: int = 0,
    ) -> None:
        expiry_ms = int(expiry.timestamp() * 1000)
        client = {
            "id": client_uuid,
            "email": email,
            "limitIp": limit_ip,
            "totalGB": 0,
            "expiryTime": expiry_ms,
            "enable": True,
            "flow": "",
        }
        settings = json.dumps({"clients": [client]}, separators=(",", ":"))
        await self._post(f"/panel/api/inbounds/updateClient/{client_uuid}", {"id": inbound_id, "settings": settings})

    @staticmethod
    def parse_reality(inbound_obj: dict[str, Any]) -> InboundRealityInfo:
        stream_settings_raw = inbound_obj.get("streamSettings", "{}")
        stream_settings = json.loads(stream_settings_raw) if isinstance(stream_settings_raw, str) else stream_settings_raw
        reality = stream_settings.get("realitySettings", {})
        rs = reality.get("settings", {})
        public_key = rs.get("publicKey", "")
        short_ids = reality.get("shortIds", []) or [""]
        server_names = reality.get("serverNames", []) or [""]
        fingerprint = reality.get("fingerprint", "chrome")
        if not public_key:
            raise RuntimeError("Could not read reality public key from inbound streamSettings")
        return InboundRealityInfo(
            public_key=public_key,
            short_id=short_ids[0],
            sni=server_names[0],
            fingerprint=fingerprint,
        )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
