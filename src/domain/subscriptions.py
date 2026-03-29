from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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
            client_email = f"tg_{user_id}_{int(now.timestamp())}"
            new_exp = now + timedelta(days=settings.plan_days)

            await xui.add_client(
                settings.xui_inbound_id,
                client_uuid,
                client_email,
                new_exp,
                limit_ip=settings.max_devices_per_sub,
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
            )
            xui_sub_id = await xui.get_client_sub_id(settings.xui_inbound_id, client_uuid)
            sub_id = await db.create_subscription(
                user_id=user_id,
                inbound_id=settings.xui_inbound_id,
                client_uuid=client_uuid,
                client_email=client_email,
                xui_sub_id=xui_sub_id,
                vless_url=vless_url,
                expires_at=new_exp,
            )
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

        await xui.update_client(
            settings.xui_inbound_id,
            client_uuid,
            client_email,
            new_exp,
            limit_ip=settings.max_devices_per_sub,
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
        )
        await db.extend_subscription(int(current_sub["id"]), new_exp, vless_url)
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
