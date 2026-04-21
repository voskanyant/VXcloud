from __future__ import annotations

import base64
from urllib.parse import quote

from src.config import Settings
from src.dns_alias import normalize_alias_fqdn
from src.vless import build_vless_url
from src.xui_client import InboundRealityInfo


def subscription_alias_for(
    *,
    settings: Settings,
    subscription: dict[str, object] | None = None,
) -> str | None:
    alias = str((subscription or {}).get("alias_fqdn") or "").strip()
    if not alias:
        return None
    return normalize_alias_fqdn(alias, settings)


def subscription_endpoint_for_node(
    *,
    settings: Settings,
    node: dict[str, object] | None,
    subscription: dict[str, object] | None = None,
) -> tuple[str, int]:
    alias = subscription_alias_for(settings=settings, subscription=subscription)
    host = alias or str((node or {}).get("node_fqdn") or (node or {}).get("backend_host") or settings.vpn_public_host).strip()
    port_raw = (node or {}).get("backend_port")
    try:
        port = int(port_raw) if port_raw not in (None, "") else int(settings.vpn_public_port)
    except (TypeError, ValueError):
        port = int(settings.vpn_public_port)
    return host, port


def build_subscription_vless_url(
    *,
    settings: Settings,
    node: dict[str, object] | None,
    client_uuid: str,
    reality: InboundRealityInfo,
    subscription: dict[str, object] | None = None,
) -> str:
    host, port = subscription_endpoint_for_node(settings=settings, node=node, subscription=subscription)
    return build_vless_url(
        uuid=client_uuid,
        host=host,
        port=port,
        tag=settings.vpn_tag,
        public_key=reality.public_key,
        short_id=reality.short_id,
        sni=reality.sni,
        fingerprint=reality.fingerprint,
        flow=settings.vpn_flow,
    )


def build_bot_feed_url(*, site_url: str, feed_token: str) -> str:
    base = str(site_url or "").strip().rstrip("/")
    token = quote(str(feed_token).strip(), safe="")
    return f"{base}/account/feed/{token}/"


def encode_subscription_payload(links: list[str]) -> bytes:
    body = "\n".join(str(item).strip() for item in links if str(item).strip())
    return base64.b64encode(body.encode("utf-8"))
