from __future__ import annotations

import asyncio
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


@dataclass(frozen=True)
class InboundClientState:
    client_uuid: str
    email: str
    enabled: bool
    expiry: datetime
    limit_ip: int
    flow: str
    sub_id: str | None = None
    comment: str | None = None


class XUIClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._timeout = aiohttp.ClientTimeout(total=20)
        self._max_retries = 2
        self._retry_delay_seconds = 0.6
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession(
            cookie_jar=aiohttp.CookieJar(unsafe=True),
            timeout=self._timeout,
        )
        await self.login()

    async def close(self) -> None:
        if self._session:
            await self._session.close()

    async def login(self) -> None:
        assert self._session is not None
        payload = {"username": self.username, "password": self.password}
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with self._session.post(f"{self.base_url}/login", json=payload, ssl=False) as resp:
                    data = await resp.json(content_type=None)
                    if resp.status >= 500:
                        raise RuntimeError(f"x-ui login server error ({resp.status}): {data}")
                    if not data.get("success"):
                        raise RuntimeError(f"x-ui login failed: {data}")
                    return
            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                await asyncio.sleep(self._retry_delay_seconds * (attempt + 1))
        assert last_error is not None
        raise last_error

    @staticmethod
    def _needs_relogin(status_code: int, data: Any) -> bool:
        if status_code in {401, 403}:
            return True
        if not isinstance(data, dict):
            return False
        if data.get("success") is True:
            return False
        serialized = json.dumps(data, ensure_ascii=False).lower()
        return "login" in serialized or "auth" in serialized or "cookie" in serialized

    async def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        assert self._session is not None
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            should_retry = attempt < self._max_retries
            try:
                req_kwargs: dict[str, Any] = {"ssl": False}
                if payload is not None:
                    req_kwargs["json"] = payload

                async with self._session.request(method, url, **req_kwargs) as resp:
                    data = await resp.json(content_type=None)

                    if self._needs_relogin(resp.status, data):
                        if should_retry:
                            await self.login()
                            continue
                        raise RuntimeError(f"x-ui request auth failed for {path}: {data}")

                    if resp.status >= 500:
                        raise RuntimeError(f"x-ui request server error for {path} ({resp.status}): {data}")

                    if not isinstance(data, dict) or not data.get("success"):
                        raise RuntimeError(f"x-ui request failed for {path}: {data}")

                    return data
            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
                last_error = exc
                if not should_retry:
                    break
                await asyncio.sleep(self._retry_delay_seconds * (attempt + 1))

        assert last_error is not None
        raise last_error

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json("POST", path, payload=payload)

    async def _get(self, path: str) -> dict[str, Any]:
        return await self._request_json("GET", path)

    async def get_inbound(self, inbound_id: int) -> dict[str, Any]:
        data = await self._get(f"/panel/api/inbounds/get/{inbound_id}")
        return data["obj"]

    async def get_client_sub_id(self, inbound_id: int, client_uuid: str) -> str | None:
        inbound = await self.get_inbound(inbound_id)
        clients = self._parse_inbound_clients(inbound)
        for c in clients:
            if str(c.get("id", "")).lower() == client_uuid.lower():
                sub_id = c.get("subId")
                return str(sub_id) if sub_id else None
        return None

    async def has_client(self, inbound_id: int, client_uuid: str, *, email: str | None = None) -> bool:
        inbound = await self.get_inbound(inbound_id)
        clients = self._parse_inbound_clients(inbound)
        normalized_uuid = str(client_uuid).lower()
        normalized_email = str(email or "").strip().lower()
        for client in clients:
            if str(client.get("id", "")).lower() == normalized_uuid:
                return True
            if normalized_email and str(client.get("email", "")).strip().lower() == normalized_email:
                return True
        return False

    @staticmethod
    def _parse_inbound_clients(inbound: dict[str, Any]) -> list[dict[str, Any]]:
        settings_raw = inbound.get("settings", "{}")
        settings = json.loads(settings_raw) if isinstance(settings_raw, str) else settings_raw
        clients = settings.get("clients", [])
        return clients if isinstance(clients, list) else []

    @staticmethod
    def _coerce_expiry(value: Any) -> datetime:
        try:
            expiry_ms = int(value or 0)
        except (TypeError, ValueError):
            expiry_ms = 0
        if expiry_ms <= 0:
            return datetime.fromtimestamp(0, tz=timezone.utc)
        return datetime.fromtimestamp(expiry_ms / 1000, tz=timezone.utc)

    async def list_clients(self, inbound_id: int) -> list[InboundClientState]:
        inbound = await self.get_inbound(inbound_id)
        states: list[InboundClientState] = []
        for client in self._parse_inbound_clients(inbound):
            client_uuid = str(client.get("id", "")).strip()
            email = str(client.get("email", "")).strip()
            if not client_uuid or not email:
                continue
            sub_id_raw = client.get("subId")
            comment_raw = client.get("comment")
            states.append(
                InboundClientState(
                    client_uuid=client_uuid,
                    email=email,
                    enabled=bool(client.get("enable", True)),
                    expiry=self._coerce_expiry(client.get("expiryTime")),
                    limit_ip=int(client.get("limitIp", 0) or 0),
                    flow=str(client.get("flow", "") or ""),
                    sub_id=str(sub_id_raw) if sub_id_raw else None,
                    comment=str(comment_raw) if comment_raw else None,
                )
            )
        return states

    @staticmethod
    def _build_client_payload(
        *,
        client_uuid: str,
        email: str,
        expiry: datetime,
        enable: bool,
        limit_ip: int,
        flow: str = "",
        sub_id: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        expiry_ms = int(expiry.timestamp() * 1000)
        client: dict[str, Any] = {
            "id": client_uuid,
            "email": email,
            "limitIp": limit_ip,
            "totalGB": 0,
            "expiryTime": expiry_ms,
            "enable": bool(enable),
            "flow": str(flow or ""),
        }
        if sub_id:
            client["subId"] = sub_id
        if comment:
            client["comment"] = comment[:64]
        return client

    async def add_client(
        self,
        inbound_id: int,
        client_uuid: str,
        email: str,
        expiry: datetime,
        limit_ip: int = 0,
        flow: str = "",
        comment: str | None = None,
        sub_id: str | None = None,
        enable: bool = True,
    ) -> None:
        client = self._build_client_payload(
            client_uuid=client_uuid,
            email=email,
            expiry=expiry,
            enable=enable,
            limit_ip=limit_ip,
            flow=flow,
            sub_id=sub_id,
            comment=comment,
        )
        settings = json.dumps({"clients": [client]}, separators=(",", ":"))
        await self._post("/panel/api/inbounds/addClient", {"id": inbound_id, "settings": settings})

    async def update_client(
        self,
        inbound_id: int,
        client_uuid: str,
        email: str,
        expiry: datetime,
        limit_ip: int = 0,
        flow: str = "",
        comment: str | None = None,
        sub_id: str | None = None,
        enable: bool = True,
    ) -> None:
        client = self._build_client_payload(
            client_uuid=client_uuid,
            email=email,
            expiry=expiry,
            enable=enable,
            limit_ip=limit_ip,
            flow=flow,
            sub_id=sub_id,
            comment=comment,
        )
        settings = json.dumps({"clients": [client]}, separators=(",", ":"))
        await self._post(f"/panel/api/inbounds/updateClient/{client_uuid}", {"id": inbound_id, "settings": settings})

    async def set_client_enabled(
        self,
        inbound_id: int,
        client_uuid: str,
        email: str,
        expiry: datetime,
        *,
        enable: bool,
        limit_ip: int = 0,
        flow: str = "",
        comment: str | None = None,
        sub_id: str | None = None,
    ) -> None:
        client = self._build_client_payload(
            client_uuid=client_uuid,
            email=email,
            expiry=expiry,
            enable=enable,
            limit_ip=limit_ip,
            flow=flow,
            sub_id=sub_id,
            comment=comment,
        )
        settings = json.dumps({"clients": [client]}, separators=(",", ":"))
        await self._post(f"/panel/api/inbounds/updateClient/{client_uuid}", {"id": inbound_id, "settings": settings})

    async def del_client(
        self,
        inbound_id: int,
        client_uuid: str,
        *,
        email: str | None = None,
        expiry: datetime | None = None,
        limit_ip: int = 0,
        flow: str = "",
        comment: str | None = None,
        sub_id: str | None = None,
    ) -> str:
        try:
            await self._post(f"/panel/api/inbounds/{inbound_id}/delClient/{client_uuid}", {})
            return "deleted"
        except Exception:
            if not email or expiry is None:
                raise
            await self.set_client_enabled(
                inbound_id,
                client_uuid,
                email,
                expiry,
                enable=False,
                limit_ip=limit_ip,
                flow=flow,
                comment=comment,
                sub_id=sub_id,
            )
            return "disabled"

    async def delete_client(
        self,
        inbound_id: int,
        client_uuid: str,
        *,
        email: str | None = None,
        expiry: datetime | None = None,
        limit_ip: int = 0,
        flow: str = "",
        comment: str | None = None,
        sub_id: str | None = None,
    ) -> str:
        return await self.del_client(
            inbound_id,
            client_uuid,
            email=email,
            expiry=expiry,
            limit_ip=limit_ip,
            flow=flow,
            comment=comment,
            sub_id=sub_id,
        )

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
