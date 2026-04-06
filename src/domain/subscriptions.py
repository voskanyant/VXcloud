from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from src.cluster.provisioner import ensure_client_on_all_active_nodes
from src.client_naming import build_xui_client_name
from src.config import Settings
from src.db import DB
from src.vless import build_vless_url
from src.xui_client import XUIClient

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActivationResult:
    user_id: int
    subscription_id: int
    expires_at: datetime
    vless_url: str
    xui_sub_id: str | None
    created: bool
    idempotent: bool


def _payment_provider_for_order(order: dict[str, object]) -> str:
    card_provider = order.get("card_provider")
    if card_provider:
        return str(card_provider)
    payment_method = str(order.get("payment_method") or "").strip().lower()
    if payment_method in {"card", "stars"}:
        return payment_method
    return payment_method or "unknown"


def _event_id_for_order(order: dict[str, object]) -> str:
    return str(order.get("provider_payment_charge_id") or order.get("telegram_payment_charge_id") or "")


def _log_provision_event(
    *,
    order_id: int,
    client_code: str | None,
    provider: str,
    event_id: str,
    provision_state: str,
    paid_to_ready_ms: int | None = None,
) -> None:
    payload: dict[str, object] = {
        "event": "subscription_provision",
        "order_id": order_id,
        "client_code": client_code or "",
        "provider": provider,
        "event_id": event_id,
        "provision_state": provision_state,
    }
    if paid_to_ready_ms is not None:
        payload["paid_to_ready_ms"] = paid_to_ready_ms
    LOGGER.info(json.dumps(payload, ensure_ascii=False))


def _deterministic_sub_id(client_uuid: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"vxcloud:{client_uuid}").hex


def _cluster_node_client(node: dict[str, Any]) -> XUIClient:
    return XUIClient(
        str(node["xui_base_url"]).rstrip("/"),
        str(node["xui_username"]),
        str(node["xui_password"]),
    )


def _cluster_node_inbound_id(node: dict[str, Any], fallback_inbound_id: int) -> int:
    raw = node.get("xui_inbound_id")
    if raw is None:
        return int(fallback_inbound_id)
    return int(raw)


async def _pick_canonical_node_with_inbound(
    *,
    db: DB,
    settings: Settings,
) -> tuple[dict[str, Any], dict[str, Any], Any, int]:
    nodes = await db.get_active_vpn_nodes(lb_only=True)
    if not nodes:
        raise RuntimeError("Cluster mode is enabled, but no active lb_enabled VPN nodes are configured")

    ordered = sorted(nodes, key=lambda node: (0 if bool(node.get("last_health_ok")) else 1, int(node.get("id", 0))))
    errors: list[str] = []
    for node in ordered:
        node_id = int(node.get("id", 0))
        inbound_id = _cluster_node_inbound_id(node, settings.xui_inbound_id)
        node_xui = _cluster_node_client(node)
        try:
            await node_xui.start()
            inbound = await node_xui.get_inbound(inbound_id)
            reality = node_xui.parse_reality(inbound)
            await db.mark_node_health(
                node_id=node_id,
                ok=True,
                error=None,
                reality_public_key=reality.public_key,
                reality_short_id=reality.short_id,
                reality_sni=reality.sni,
                reality_fingerprint=reality.fingerprint,
            )
            return node, inbound, reality, inbound_id
        except Exception as exc:
            error_text = str(exc)
            errors.append(f"node#{node_id}: {error_text}")
            await db.mark_node_health(node_id=node_id, ok=False, error=error_text)
        finally:
            await node_xui.close()

    raise RuntimeError(f"Could not fetch inbound/reality from any lb_enabled node: {'; '.join(errors)}")


def _cluster_failure_error(ensure_result: dict[str, Any]) -> RuntimeError:
    failed_nodes = [
        f"node#{item.get('node_id')}: {item.get('error')}"
        for item in ensure_result.get("results", [])
        if not item.get("ok")
    ]
    details = "; ".join(failed_nodes) if failed_nodes else "unknown cluster sync error"
    return RuntimeError(f"Cluster provisioning failed on lb_enabled nodes: {details}")


async def activate_subscription(
    order_id: int,
    *,
    db: DB,
    xui: XUIClient,
    settings: Settings,
) -> ActivationResult:
    claimed_order = await db.claim_order_for_activation(order_id)
    order = claimed_order or await db.get_order_by_id(order_id)
    if not order:
        raise RuntimeError(f"Order not found: {order_id}")

    user_id = int(order["user_id"])
    payload_value = str(order.get("payload") or "")
    force_new_config = payload_value.startswith("buynew:") or payload_value.startswith("web-newcfg:")
    selected_subscription_id: int | None = None
    if payload_value.startswith("renew:") or payload_value.startswith("web-renew:"):
        parts = payload_value.split(":")
        if len(parts) >= 4:
            try:
                candidate_id = int(parts[2])
            except ValueError:
                candidate_id = 0
            if candidate_id > 0:
                selected_subscription_id = candidate_id
    client_code = await db.get_user_client_code(user_id)
    provider = _payment_provider_for_order(order)
    event_id = _event_id_for_order(order)
    _log_provision_event(
        order_id=order_id,
        client_code=client_code,
        provider=provider,
        event_id=event_id,
        provision_state="start",
    )

    if claimed_order is None:
        status = str(order.get("status") or "")
        if status not in {"activating", "activated"}:
            raise RuntimeError(f"Order {order_id} is not eligible for activation (status={status})")
        sub = await db.get_active_subscription(user_id)
        if sub is None:
            sub = await db.get_latest_subscription(user_id)
        if sub is None:
            raise RuntimeError(f"Order {order_id} is marked {status}, but subscription is not found")
        _log_provision_event(
            order_id=order_id,
            client_code=client_code,
            provider=provider,
            event_id=event_id,
            provision_state="idempotent_ready",
        )
        return ActivationResult(
            user_id=user_id,
            subscription_id=int(sub["id"]),
            expires_at=sub["expires_at"],
            vless_url=str(sub["vless_url"]),
            xui_sub_id=(str(sub["xui_sub_id"]) if sub.get("xui_sub_id") else None),
            created=False,
            idempotent=True,
        )

    try:
        now = datetime.now(timezone.utc)
        user_identity = await db.get_user_identity(user_id)
        cluster_mode = bool(getattr(settings, "vpn_cluster_enabled", False))
        canonical_inbound_id = settings.xui_inbound_id
        if cluster_mode:
            _, inbound, reality, canonical_inbound_id = await _pick_canonical_node_with_inbound(
                db=db,
                settings=settings,
            )
        else:
            inbound = await xui.get_inbound(settings.xui_inbound_id)
            reality = xui.parse_reality(inbound)
        inbound_port = int(inbound["port"])

        current_sub = None
        if not force_new_config and selected_subscription_id is not None:
            current_sub = await db.get_subscription(user_id, selected_subscription_id)
        if current_sub is None and not force_new_config:
            current_sub = await db.get_active_subscription(user_id)
        created = False

        if current_sub is None:
            created = True
            client_uuid = str(uuid.uuid4())
            client_email = build_xui_client_name(
                user_id=user_id,
                client_uuid=client_uuid,
                username=(user_identity or {}).get("username"),
                first_name=(user_identity or {}).get("first_name"),
                client_code=(user_identity or {}).get("client_code"),
            )
            new_exp = now + timedelta(days=settings.plan_days)
            xui_sub_id = _deterministic_sub_id(client_uuid) if cluster_mode else None

            if not cluster_mode:
                await xui.add_client(
                    settings.xui_inbound_id,
                    client_uuid,
                    client_email,
                    new_exp,
                    limit_ip=settings.max_devices_per_sub,
                    flow=settings.vpn_flow,
                )
            vless_url = build_vless_url(
                uuid=client_uuid,
                host=settings.vpn_public_host,
                port=settings.vpn_public_port or inbound_port,
                tag=settings.vpn_tag,
                public_key=reality.public_key,
                short_id=reality.short_id,
                sni=reality.sni,
                fingerprint=reality.fingerprint,
                flow=settings.vpn_flow,
            )
            sub_id = await db.create_subscription(
                user_id=user_id,
                inbound_id=canonical_inbound_id,
                client_uuid=client_uuid,
                client_email=client_email,
                xui_sub_id=xui_sub_id,
                vless_url=vless_url,
                expires_at=new_exp,
            )
            if cluster_mode:
                ensure_result = await ensure_client_on_all_active_nodes(
                    db,
                    {
                        "id": sub_id,
                        "client_uuid": client_uuid,
                        "client_email": client_email,
                        "xui_sub_id": xui_sub_id,
                        "expires_at": new_exp,
                        "is_active": True,
                        "revoked_at": None,
                    },
                    settings,
                )
                if ensure_result.get("failed", 0) > 0:
                    await db.revoke_subscription(user_id, sub_id)
                    raise _cluster_failure_error(ensure_result)
            else:
                xui_sub_id = await xui.get_client_sub_id(settings.xui_inbound_id, client_uuid)
            await db.update_subscription_xui_sub_id(sub_id, xui_sub_id)
            await db.mark_order_activated(order_id)
            paid_to_ready_ms: int | None = None
            paid_at = order.get("paid_at")
            if isinstance(paid_at, datetime):
                paid_to_ready_ms = max(0, int((datetime.now(timezone.utc) - paid_at).total_seconds() * 1000))
            _log_provision_event(
                order_id=order_id,
                client_code=client_code,
                provider=provider,
                event_id=event_id,
                provision_state="ready_created",
                paid_to_ready_ms=paid_to_ready_ms,
            )
            return ActivationResult(
                user_id=user_id,
                subscription_id=sub_id,
                expires_at=new_exp,
                vless_url=vless_url,
                xui_sub_id=xui_sub_id,
                created=created,
                idempotent=False,
            )

        base = current_sub["expires_at"] if current_sub["expires_at"] > now else now
        new_exp = base + timedelta(days=settings.plan_days)
        client_uuid = str(current_sub["client_uuid"])
        client_email = str(current_sub["client_email"])
        xui_sub_id = str(current_sub["xui_sub_id"]) if current_sub.get("xui_sub_id") else None
        if cluster_mode and not xui_sub_id:
            xui_sub_id = _deterministic_sub_id(client_uuid)
            await db.update_subscription_xui_sub_id(int(current_sub["id"]), xui_sub_id)

        if cluster_mode:
            ensure_result = await ensure_client_on_all_active_nodes(
                db,
                {
                    "id": int(current_sub["id"]),
                    "client_uuid": client_uuid,
                    "client_email": client_email,
                    "xui_sub_id": xui_sub_id,
                    "expires_at": new_exp,
                    "is_active": True,
                    "revoked_at": None,
                },
                settings,
            )
            if ensure_result.get("failed", 0) > 0:
                raise _cluster_failure_error(ensure_result)
        else:
            await xui.update_client(
                settings.xui_inbound_id,
                client_uuid,
                client_email,
                new_exp,
                limit_ip=settings.max_devices_per_sub,
                flow=settings.vpn_flow,
            )
        vless_url = build_vless_url(
            uuid=client_uuid,
            host=settings.vpn_public_host,
            port=settings.vpn_public_port or inbound_port,
            tag=settings.vpn_tag,
            public_key=reality.public_key,
            short_id=reality.short_id,
            sni=reality.sni,
            fingerprint=reality.fingerprint,
            flow=settings.vpn_flow,
        )
        await db.extend_subscription(int(current_sub["id"]), new_exp, vless_url)
        if not cluster_mode:
            xui_sub_id = await xui.get_client_sub_id(settings.xui_inbound_id, client_uuid)
        await db.update_subscription_xui_sub_id(int(current_sub["id"]), xui_sub_id)
        await db.mark_order_activated(order_id)
        paid_to_ready_ms: int | None = None
        paid_at = order.get("paid_at")
        if isinstance(paid_at, datetime):
            paid_to_ready_ms = max(0, int((datetime.now(timezone.utc) - paid_at).total_seconds() * 1000))
        _log_provision_event(
            order_id=order_id,
            client_code=client_code,
            provider=provider,
            event_id=event_id,
            provision_state="ready_extended",
            paid_to_ready_ms=paid_to_ready_ms,
        )
        return ActivationResult(
            user_id=user_id,
            subscription_id=int(current_sub["id"]),
            expires_at=new_exp,
            vless_url=vless_url,
            xui_sub_id=xui_sub_id,
            created=created,
            idempotent=False,
        )
    except Exception:
        await db.release_order_activation_claim(order_id)
        _log_provision_event(
            order_id=order_id,
            client_code=client_code,
            provider=provider,
            event_id=event_id,
            provision_state="failed",
        )
        raise
