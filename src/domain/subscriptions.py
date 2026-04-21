from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from src.cluster.provisioner import create_client_on_node, update_client_on_node
from src.cluster.rebalance import pick_best_node
from src.client_naming import build_xui_client_name
from src.config import Settings
from src.db import DB
from src.dns_alias import ensure_subscription_alias_record, generate_subscription_alias
from src.subscription_links import build_subscription_vless_url
from src.xui_client import InboundRealityInfo, XUIClient

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActivationResult:
    user_id: int
    subscription_id: int
    expires_at: datetime
    vless_url: str
    xui_sub_id: str | None
    feed_token: str | None
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


async def _load_cluster_node_runtime(
    *,
    node: dict[str, Any],
    settings: Settings,
    db: DB,
) -> tuple[dict[str, Any], InboundRealityInfo, int]:
    node_id = int(node.get("id", 0) or 0)
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
        return inbound, reality, inbound_id
    except Exception as exc:
        await db.mark_node_health(node_id=node_id, ok=False, error=str(exc))
        raise
    finally:
        await node_xui.close()


async def _pick_subscription_node(
    *,
    db: DB,
    settings: Settings,
    current_sub: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], InboundRealityInfo, int, str]:
    preferred_node_id = int(current_sub["assigned_node_id"]) if current_sub and current_sub.get("assigned_node_id") else 0
    if preferred_node_id > 0:
        preferred_node = await db.get_vpn_node(preferred_node_id)
        if preferred_node and bool(preferred_node.get("is_active")):
            try:
                inbound, reality, inbound_id = await _load_cluster_node_runtime(
                    node=preferred_node,
                    settings=settings,
                    db=db,
                )
                return preferred_node, inbound, reality, inbound_id, "preserved_assignment"
            except Exception:
                LOGGER.exception("Assigned node is unavailable during activation, selecting replacement node")

    best = await pick_best_node(db)
    if best is None:
        raise RuntimeError("No healthy VPN node is eligible for subscription assignment")
    inbound, reality, inbound_id = await _load_cluster_node_runtime(node=best.node, settings=settings, db=db)
    return best.node, inbound, reality, inbound_id, "selected_best_node"


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
            feed_token=(str(sub["feed_token"]) if sub.get("feed_token") else None),
            created=False,
            idempotent=True,
        )

    try:
        now = datetime.now(timezone.utc)
        user_identity = await db.get_user_identity(user_id)
        cluster_mode = bool(getattr(settings, "vpn_cluster_enabled", False))
        canonical_inbound_id = settings.xui_inbound_id

        current_sub = None
        if not force_new_config and selected_subscription_id is not None:
            current_sub = await db.get_subscription(user_id, selected_subscription_id)
        if current_sub is None and not force_new_config:
            current_sub = await db.get_active_subscription(user_id)
        created = False

        if cluster_mode:
            assigned_node, inbound, reality, canonical_inbound_id, assignment_reason = await _pick_subscription_node(
                db=db,
                settings=settings,
                current_sub=current_sub,
            )
            inbound_port = int(inbound["port"])
        else:
            assigned_node = None
            assignment_reason = "single_node"
            inbound = await xui.get_inbound(settings.xui_inbound_id)
            reality = xui.parse_reality(inbound)
            inbound_port = int(inbound["port"])

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
            alias_fqdn = generate_subscription_alias(settings) if cluster_mode else None
            compatibility_pool = (
                str(assigned_node.get("compatibility_pool") or "").strip() or "default"
                if cluster_mode and assigned_node is not None
                else None
            )

            if cluster_mode:
                node_result = await create_client_on_node(
                    assigned_node,
                    client_uuid,
                    client_email,
                    xui_sub_id,
                    new_exp,
                    limit_ip=settings.max_devices_per_sub,
                    flow=settings.vpn_flow,
                )
                xui_sub_id = node_result.get("xui_sub_id") or xui_sub_id
            else:
                await xui.add_client(
                    settings.xui_inbound_id,
                    client_uuid,
                    client_email,
                    new_exp,
                    limit_ip=settings.max_devices_per_sub,
                    flow=settings.vpn_flow,
                )
                xui_sub_id = await xui.get_client_sub_id(settings.xui_inbound_id, client_uuid)

            vless_url = build_subscription_vless_url(
                settings=settings,
                node=assigned_node,
                client_uuid=client_uuid,
                reality=reality,
                subscription={"alias_fqdn": alias_fqdn},
            ) if cluster_mode else build_subscription_vless_url(
                settings=settings,
                node={"backend_host": settings.vpn_public_host, "backend_port": settings.vpn_public_port or inbound_port},
                client_uuid=client_uuid,
                reality=reality,
            )
            sub_id = await db.create_subscription(
                user_id=user_id,
                inbound_id=canonical_inbound_id,
                client_uuid=client_uuid,
                client_email=client_email,
                xui_sub_id=xui_sub_id,
                assigned_node_id=(int(assigned_node["id"]) if assigned_node is not None else None),
                assignment_source=("new" if cluster_mode else "single_node"),
                migration_state="ready",
                alias_fqdn=alias_fqdn,
                current_node_id=(int(assigned_node["id"]) if assigned_node is not None else None),
                desired_node_id=None,
                assignment_state=("steady" if cluster_mode else "single_node"),
                ttl_seconds=int(getattr(settings, "vpn_alias_default_ttl", 300)),
                dns_provider=(settings.vpn_alias_provider if cluster_mode else None),
                compatibility_pool=compatibility_pool,
                vless_url=vless_url,
                expires_at=new_exp,
            )
            feed_token = await db.ensure_subscription_feed_token(sub_id)
            await db.update_subscription_xui_sub_id(sub_id, xui_sub_id)
            if cluster_mode and alias_fqdn and assigned_node is not None:
                alias_result = await ensure_subscription_alias_record(
                    settings=settings,
                    alias_fqdn=alias_fqdn,
                    node=assigned_node,
                    ttl=int(getattr(settings, "vpn_alias_default_ttl", 300)),
                )
                await db.update_subscription_assignment(
                    sub_id,
                    assigned_node_id=int(assigned_node["id"]),
                    vless_url=vless_url,
                    assignment_source="new",
                    migration_state="ready",
                    alias_fqdn=alias_fqdn,
                    current_node_id=int(assigned_node["id"]),
                    desired_node_id=None,
                    assignment_state="steady",
                    ttl_seconds=alias_result.ttl,
                    dns_provider=alias_result.provider,
                    dns_record_id=alias_result.record_id,
                    last_dns_change_id=alias_result.change_id,
                    compatibility_pool=compatibility_pool,
                    mark_rebalanced=False,
                )
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
                provision_state=f"ready_created:{assignment_reason}",
                paid_to_ready_ms=paid_to_ready_ms,
            )
            return ActivationResult(
                user_id=user_id,
                subscription_id=sub_id,
                expires_at=new_exp,
                vless_url=vless_url,
                xui_sub_id=xui_sub_id,
                feed_token=feed_token,
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

        if cluster_mode:
            alias_fqdn = str(current_sub.get("alias_fqdn") or "").strip() or generate_subscription_alias(settings)
            compatibility_pool = (
                str(current_sub.get("compatibility_pool") or "").strip()
                or str(assigned_node.get("compatibility_pool") or "").strip()
                or "default"
            )
            node_result = await update_client_on_node(
                assigned_node,
                client_uuid,
                client_email,
                xui_sub_id,
                new_exp,
                limit_ip=settings.max_devices_per_sub,
                flow=settings.vpn_flow,
            )
            xui_sub_id = node_result.get("xui_sub_id") or xui_sub_id
            vless_url = build_subscription_vless_url(
                settings=settings,
                node=assigned_node,
                client_uuid=client_uuid,
                reality=reality,
                subscription={"alias_fqdn": alias_fqdn},
            )
        else:
            await xui.update_client(
                settings.xui_inbound_id,
                client_uuid,
                client_email,
                new_exp,
                limit_ip=settings.max_devices_per_sub,
                flow=settings.vpn_flow,
            )
            vless_url = build_subscription_vless_url(
                settings=settings,
                node={"backend_host": settings.vpn_public_host, "backend_port": settings.vpn_public_port or inbound_port},
                client_uuid=client_uuid,
                reality=reality,
            )
            xui_sub_id = await xui.get_client_sub_id(settings.xui_inbound_id, client_uuid)

        await db.extend_subscription(
            int(current_sub["id"]),
            new_exp,
            vless_url,
            assigned_node_id=(int(assigned_node["id"]) if assigned_node is not None else None),
            assignment_source=("renew_preserve" if assignment_reason == "preserved_assignment" else "renew_reassign"),
            migration_state="ready",
            alias_fqdn=(alias_fqdn if cluster_mode else None),
            current_node_id=(int(assigned_node["id"]) if assigned_node is not None else None),
            desired_node_id=None,
            assignment_state=("steady" if cluster_mode else None),
            ttl_seconds=(int(getattr(settings, "vpn_alias_default_ttl", 300)) if cluster_mode else None),
            dns_provider=(settings.vpn_alias_provider if cluster_mode else None),
            compatibility_pool=(compatibility_pool if cluster_mode else None),
        )
        if cluster_mode and alias_fqdn and assigned_node is not None:
            alias_result = await ensure_subscription_alias_record(
                settings=settings,
                alias_fqdn=alias_fqdn,
                node=assigned_node,
                ttl=int(getattr(settings, "vpn_alias_default_ttl", 300)),
                record_id=str(current_sub.get("dns_record_id") or "").strip() or None,
            )
            await db.update_subscription_assignment(
                int(current_sub["id"]),
                assigned_node_id=int(assigned_node["id"]),
                vless_url=vless_url,
                assignment_source=("renew_preserve" if assignment_reason == "preserved_assignment" else "renew_reassign"),
                migration_state="ready",
                alias_fqdn=alias_fqdn,
                current_node_id=int(assigned_node["id"]),
                desired_node_id=None,
                assignment_state="steady",
                ttl_seconds=alias_result.ttl,
                dns_provider=alias_result.provider,
                dns_record_id=alias_result.record_id,
                last_dns_change_id=alias_result.change_id,
                compatibility_pool=compatibility_pool,
                mark_rebalanced=False,
            )
        await db.update_subscription_xui_sub_id(int(current_sub["id"]), xui_sub_id)
        feed_token = await db.ensure_subscription_feed_token(int(current_sub["id"]))
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
            provision_state=f"ready_extended:{assignment_reason}",
            paid_to_ready_ms=paid_to_ready_ms,
        )
        return ActivationResult(
            user_id=user_id,
            subscription_id=int(current_sub["id"]),
            expires_at=new_exp,
            vless_url=vless_url,
            xui_sub_id=xui_sub_id,
            feed_token=feed_token,
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
