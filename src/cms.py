from __future__ import annotations

from typing import Any

import aiohttp


class DirectusCMS:
    def __init__(
        self,
        base_url: str,
        token: str,
        content_collection: str,
        button_collection: str,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.content_collection = content_collection
        self.button_collection = button_collection
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        headers = {"Authorization": f"Bearer {self.token}"}
        self._session = aiohttp.ClientSession(headers=headers)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()

    async def fetch_content(self) -> dict[str, str]:
        rows = await self._fetch_items(self.content_collection, "key,value")
        out: dict[str, str] = {}
        for row in rows:
            key = str(row.get("key", "")).strip()
            value = row.get("value")
            if key and isinstance(value, str):
                out[key] = value
        return out

    async def fetch_buttons(self) -> dict[str, str]:
        rows = await self._fetch_items(self.button_collection, "key,label")
        out: dict[str, str] = {}
        for row in rows:
            key = str(row.get("key", "")).strip()
            label = row.get("label")
            if key and isinstance(label, str):
                out[key] = label
        return out

    async def _fetch_items(self, collection: str, fields: str) -> list[dict[str, Any]]:
        assert self._session is not None
        params = {"fields": fields, "limit": "-1"}
        async with self._session.get(f"{self.base_url}/items/{collection}", params=params) as resp:
            data = await resp.json(content_type=None)
            if resp.status >= 400:
                raise RuntimeError(f"Directus request failed ({resp.status}): {data}")
            rows = data.get("data")
            if not isinstance(rows, list):
                raise RuntimeError(f"Directus response has no list data for collection '{collection}': {data}")
            return [r for r in rows if isinstance(r, dict)]
