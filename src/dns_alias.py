from __future__ import annotations

import asyncio
import ipaddress
import secrets
from dataclasses import dataclass
from typing import Any

import aiohttp

from src.config import Settings


ASSIGNMENT_STEADY = "steady"
ASSIGNMENT_PLANNED = "planned"
ASSIGNMENT_PRESYNC = "presync"
ASSIGNMENT_CUTOVER = "cutover"
ASSIGNMENT_CLEANUP = "cleanup"
ASSIGNMENT_ROLLBACK = "rollback"


@dataclass(frozen=True)
class AliasRecordResult:
    fqdn: str
    target_ip: str
    ttl: int
    provider: str
    record_id: str | None = None
    change_id: str | None = None


@dataclass(frozen=True)
class AliasDeleteResult:
    fqdn: str
    provider: str
    deleted: bool
    record_id: str | None = None
    change_id: str | None = None


def normalize_alias_fqdn(value: str, settings: Settings) -> str:
    raw = str(value or "").strip().strip(".").lower()
    namespace = str(settings.vpn_alias_namespace or "").strip().strip(".").lower()
    if not raw:
        raise ValueError("Alias fqdn is required")
    if namespace and raw.endswith(f".{namespace}"):
        return raw
    if "." in raw:
        return raw
    if not namespace:
        raise ValueError("VPN alias namespace is not configured")
    return f"{raw}.{namespace}"


def generate_subscription_alias(settings: Settings) -> str:
    label = "u-" + secrets.token_urlsafe(9).replace("_", "").replace("-", "").lower()[:14]
    return normalize_alias_fqdn(label, settings)


def node_public_target_ip(node: dict[str, Any]) -> str:
    for key in ("public_ip", "backend_host"):
        candidate = str(node.get(key) or "").strip()
        if not candidate:
            continue
        try:
            ipaddress.ip_address(candidate)
            return candidate
        except ValueError:
            continue
    raise RuntimeError(f"Node {node.get('id')} has no routable public_ip/backend_host IPv4 target")


class DNSAliasManager:
    async def ensure_a_record(self, *, fqdn: str, target_ip: str, ttl: int, record_id: str | None = None) -> AliasRecordResult:
        raise NotImplementedError

    async def delete_a_record(self, *, fqdn: str, record_id: str | None = None) -> AliasDeleteResult:
        raise NotImplementedError


class NoopDNSAliasManager(DNSAliasManager):
    async def ensure_a_record(self, *, fqdn: str, target_ip: str, ttl: int, record_id: str | None = None) -> AliasRecordResult:
        return AliasRecordResult(
            fqdn=fqdn,
            target_ip=target_ip,
            ttl=max(60, int(ttl)),
            provider="noop",
            record_id=record_id,
            change_id=f"noop:{fqdn}:{target_ip}:{ttl}",
        )

    async def delete_a_record(self, *, fqdn: str, record_id: str | None = None) -> AliasDeleteResult:
        return AliasDeleteResult(
            fqdn=fqdn,
            provider="noop",
            deleted=bool(record_id or fqdn),
            record_id=record_id,
            change_id=f"noop:delete:{fqdn}:{record_id or ''}",
        )


class CloudflareDNSAliasManager(DNSAliasManager):
    API_BASE = "https://api.cloudflare.com/client/v4"

    def __init__(self, *, api_token: str, zone_id: str) -> None:
        self._api_token = api_token
        self._zone_id = zone_id

    async def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.request(method, f"{self.API_BASE}{path}", params=params, json=payload) as response:
                body = await response.json(content_type=None)
                if response.status >= 400 or not body.get("success", False):
                    raise RuntimeError(f"Cloudflare DNS API error {response.status}: {body}")
                return body

    async def ensure_a_record(self, *, fqdn: str, target_ip: str, ttl: int, record_id: str | None = None) -> AliasRecordResult:
        normalized_ttl = max(60, int(ttl))
        if record_id:
            payload = {
                "type": "A",
                "name": fqdn,
                "content": target_ip,
                "ttl": normalized_ttl,
                "proxied": False,
            }
            body = await self._request("PUT", f"/zones/{self._zone_id}/dns_records/{record_id}", payload=payload)
            result = dict(body.get("result") or {})
            return AliasRecordResult(
                fqdn=fqdn,
                target_ip=target_ip,
                ttl=normalized_ttl,
                provider="cloudflare",
                record_id=str(result.get("id") or record_id),
                change_id=str(result.get("modified_on") or result.get("id") or record_id),
            )

        body = await self._request(
            "GET",
            f"/zones/{self._zone_id}/dns_records",
            params={"type": "A", "name": fqdn, "per_page": 100},
        )
        records = list(body.get("result") or [])
        if records:
            record = dict(records[0])
            return await self.ensure_a_record(
                fqdn=fqdn,
                target_ip=target_ip,
                ttl=normalized_ttl,
                record_id=str(record.get("id") or ""),
            )

        payload = {
            "type": "A",
            "name": fqdn,
            "content": target_ip,
            "ttl": normalized_ttl,
            "proxied": False,
        }
        created = await self._request("POST", f"/zones/{self._zone_id}/dns_records", payload=payload)
        result = dict(created.get("result") or {})
        return AliasRecordResult(
            fqdn=fqdn,
            target_ip=target_ip,
            ttl=normalized_ttl,
            provider="cloudflare",
            record_id=str(result.get("id") or ""),
            change_id=str(result.get("modified_on") or result.get("id") or ""),
        )

    async def delete_a_record(self, *, fqdn: str, record_id: str | None = None) -> AliasDeleteResult:
        target_record_id = str(record_id or "").strip()
        if not target_record_id:
            body = await self._request(
                "GET",
                f"/zones/{self._zone_id}/dns_records",
                params={"type": "A", "name": fqdn, "per_page": 100},
            )
            records = list(body.get("result") or [])
            if not records:
                return AliasDeleteResult(
                    fqdn=fqdn,
                    provider="cloudflare",
                    deleted=False,
                    record_id=None,
                    change_id=f"not-found:{fqdn}",
                )
            target_record_id = str(dict(records[0]).get("id") or "").strip()

        body = await self._request("DELETE", f"/zones/{self._zone_id}/dns_records/{target_record_id}")
        result = dict(body.get("result") or {})
        return AliasDeleteResult(
            fqdn=fqdn,
            provider="cloudflare",
            deleted=bool(result.get("id") or target_record_id),
            record_id=str(result.get("id") or target_record_id),
            change_id=str(result.get("id") or target_record_id),
        )


def build_dns_alias_manager(settings: Settings) -> DNSAliasManager:
    provider = str(settings.vpn_alias_provider or "").strip().lower()
    if provider == "cloudflare" and settings.cloudflare_api_token and settings.cloudflare_zone_id:
        return CloudflareDNSAliasManager(
            api_token=settings.cloudflare_api_token,
            zone_id=settings.cloudflare_zone_id,
        )
    return NoopDNSAliasManager()


async def ensure_subscription_alias_record(
    *,
    settings: Settings,
    alias_fqdn: str,
    node: dict[str, Any],
    ttl: int,
    record_id: str | None = None,
) -> AliasRecordResult:
    manager = build_dns_alias_manager(settings)
    target_ip = node_public_target_ip(node)
    return await manager.ensure_a_record(
        fqdn=normalize_alias_fqdn(alias_fqdn, settings),
        target_ip=target_ip,
        ttl=ttl,
        record_id=record_id,
    )


async def delete_subscription_alias_record(
    *,
    settings: Settings,
    alias_fqdn: str,
    record_id: str | None = None,
) -> AliasDeleteResult:
    manager = build_dns_alias_manager(settings)
    return await manager.delete_a_record(
        fqdn=normalize_alias_fqdn(alias_fqdn, settings),
        record_id=record_id,
    )


def run_sync(awaitable: Any) -> Any:
    return asyncio.get_event_loop().run_until_complete(awaitable)
