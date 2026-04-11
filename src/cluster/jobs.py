from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.cluster.provisioner import create_client_on_node, delete_or_disable_client_on_node, update_client_on_node
from src.db import DB
from src.xui_client import InboundClientState, XUIClient


LOGGER = logging.getLogger(__name__)


def _is_duplicate_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "exists" in text or "exist" in text or "duplicate" in text or "already" in text


def _to_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    raise ValueError(f"Unsupported datetime value for sync: {value!r}")


def _node_client(node: dict[str, Any]) -> XUIClient:
    return XUIClient(
        str(node["xui_base_url"]).rstrip("/"),
        str(node["xui_username"]),
        str(node["xui_password"]),
    )


def _node_inbound_id(node: dict[str, Any], fallback: int = 1) -> int:
    raw = node.get("xui_inbound_id")
    if raw is None:
        return int(fallback)
    return int(raw)


def _canonical_sync_node(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not nodes:
        return None
    return sorted(
        nodes,
        key=lambda node: (
            0 if bool(node.get("lb_enabled")) else 1,
            0 if bool(node.get("last_health_ok")) else 1,
            int(node.get("id", 0)),
        ),
    )[0]


def _client_identity_keys(client_uuid: str, email: str) -> tuple[str, str]:
    return (str(client_uuid).lower(), str(email).strip().lower())


async def _sync_manual_clients_from_canonical(
    db: DB,
    nodes: list[dict[str, Any]],
) -> dict[str, int]:
    canonical = _canonical_sync_node(nodes)
    if canonical is None:
        return {"canonical_node_id": 0, "followers": 0, "manual_clients": 0, "processed": 0, "failed": 0}

    follower_nodes = [node for node in nodes if int(node["id"]) != int(canonical["id"])]
    if not follower_nodes:
        return {
            "canonical_node_id": int(canonical["id"]),
            "followers": 0,
            "manual_clients": 0,
            "processed": 0,
            "failed": 0,
        }

    managed_rows = await db.list_subscription_client_identities()
    managed_uuids = {str(row.get("client_uuid") or "").lower() for row in managed_rows if row.get("client_uuid")}
    managed_emails = {str(row.get("client_email") or "").strip().lower() for row in managed_rows if row.get("client_email")}

    canonical_xui = _node_client(canonical)
    canonical_inbound_id = _node_inbound_id(canonical)
    try:
        await canonical_xui.start()
        canonical_clients = await canonical_xui.list_clients(canonical_inbound_id)
    finally:
        await canonical_xui.close()

    manual_clients = [
        client
        for client in canonical_clients
        if client.client_uuid.lower() not in managed_uuids and client.email.strip().lower() not in managed_emails
    ]
    canonical_manual_keys = {
        _client_identity_keys(client.client_uuid, client.email)
        for client in manual_clients
    }
    processed = 0
    failed = 0

    for node in follower_nodes:
        xui = _node_client(node)
        inbound_id = _node_inbound_id(node)
        try:
            await xui.start()
            follower_clients = await xui.list_clients(inbound_id)
            follower_manual = [
                client
                for client in follower_clients
                if client.client_uuid.lower() not in managed_uuids and client.email.strip().lower() not in managed_emails
            ]
            follower_manual_keys = {
                _client_identity_keys(client.client_uuid, client.email): client
                for client in follower_manual
            }

            for client in manual_clients:
                processed += 1
                try:
                    exists = await xui.has_client(inbound_id, client.client_uuid, email=client.email)
                    if exists:
                        await xui.update_client(
                            inbound_id,
                            client.client_uuid,
                            client.email,
                            client.expiry,
                            limit_ip=client.limit_ip,
                            flow=client.flow,
                            comment=client.comment,
                            sub_id=client.sub_id,
                            enable=client.enabled,
                        )
                    else:
                        await xui.add_client(
                            inbound_id,
                            client.client_uuid,
                            client.email,
                            client.expiry,
                            limit_ip=client.limit_ip,
                            flow=client.flow,
                            comment=client.comment,
                            sub_id=client.sub_id,
                            enable=client.enabled,
                        )
                except Exception:
                    failed += 1
                    LOGGER.exception(
                        "Manual 3x-ui client sync failed for canonical node_id=%s target node_id=%s client_uuid=%s",
                        int(canonical["id"]),
                        int(node["id"]),
                        client.client_uuid,
                    )

            stale_manual_clients = [
                client
                for key, client in follower_manual_keys.items()
                if key not in canonical_manual_keys
            ]
            for client in stale_manual_clients:
                processed += 1
                try:
                    await xui.del_client(
                        inbound_id,
                        client.client_uuid,
                        email=client.email,
                        expiry=client.expiry,
                        limit_ip=client.limit_ip,
                        flow=client.flow,
                        comment=client.comment,
                        sub_id=client.sub_id,
                    )
                except Exception:
                    failed += 1
                    LOGGER.exception(
                        "Manual 3x-ui stale client cleanup failed for canonical node_id=%s target node_id=%s client_uuid=%s",
                        int(canonical["id"]),
                        int(node["id"]),
                        client.client_uuid,
                    )
        finally:
            await xui.close()

    return {
        "canonical_node_id": int(canonical["id"]),
        "followers": len(follower_nodes),
        "manual_clients": len(manual_clients),
        "processed": processed,
        "failed": failed,
    }


async def healthcheck_tick(db: DB) -> dict[str, int]:
    nodes = await db.get_active_vpn_nodes(lb_only=False)
    if not nodes:
        return {"checked": 0, "ok": 0, "failed": 0}

    checked = 0
    ok_count = 0
    failed_count = 0

    for node in nodes:
        checked += 1
        node_id = int(node["id"])
        inbound_id = _node_inbound_id(node)
        xui = _node_client(node)
        try:
            await xui.start()
            inbound = await xui.get_inbound(inbound_id)
            reality = xui.parse_reality(inbound)
            await db.mark_node_health(
                node_id=node_id,
                ok=True,
                error=None,
                reality_public_key=reality.public_key,
                reality_short_id=reality.short_id,
                reality_sni=reality.sni,
                reality_fingerprint=reality.fingerprint,
            )
            ok_count += 1
        except Exception as exc:
            failed_count += 1
            await db.mark_node_health(node_id=node_id, ok=False, error=str(exc))
            LOGGER.exception("Cluster healthcheck failed for node_id=%s", node_id)
        finally:
            await xui.close()

    return {"checked": checked, "ok": ok_count, "failed": failed_count}


async def sync_tick(db: DB, settings: Any) -> dict[str, int]:
    nodes = await db.get_cluster_sync_nodes()
    if not nodes:
        return {
            "nodes": 0,
            "processed": 0,
            "ok": 0,
            "failed": 0,
            "manual_processed": 0,
            "manual_failed": 0,
        }

    batch_size = max(1, int(getattr(settings, "vpn_cluster_sync_batch_size", 200)))
    limit_ip = int(getattr(settings, "max_devices_per_sub", 1))
    flow = str(getattr(settings, "vpn_flow", "xtls-rprx-vision") or "")

    processed = 0
    ok_count = 0
    failed_count = 0

    for node in nodes:
        node_id = int(node["id"])
        rows = await db.list_subscriptions_needing_sync(node_id, limit=batch_size)
        node_had_failures = False
        for row in rows:
            processed += 1
            subscription_id = int(row["subscription_id"])
            client_uuid = str(row["client_uuid"])
            client_email = str(row["client_email"])
            desired_enabled = bool(row.get("desired_enabled"))
            desired_expires_at = _to_utc(row.get("desired_expires_at") or row.get("expires_at"))
            sub_id_raw = row.get("xui_sub_id")
            sub_id = str(sub_id_raw).strip() if sub_id_raw else None

            try:
                if desired_enabled:
                    try:
                        node_result = await create_client_on_node(
                            node,
                            client_uuid,
                            client_email,
                            sub_id,
                            desired_expires_at,
                            limit_ip=limit_ip,
                            flow=flow,
                        )
                    except Exception as exc:
                        if not _is_duplicate_error(exc):
                            raise
                        node_result = await update_client_on_node(
                            node,
                            client_uuid,
                            client_email,
                            sub_id,
                            desired_expires_at,
                            limit_ip=limit_ip,
                            flow=flow,
                        )
                    observed_enabled = True
                    observed_expires_at = desired_expires_at
                else:
                    node_result = await delete_or_disable_client_on_node(
                        node,
                        client_uuid,
                        client_email,
                        sub_id,
                        desired_expires_at,
                        limit_ip=limit_ip,
                        flow=flow,
                    )
                    observed_enabled = False
                    observed_expires_at = desired_expires_at

                await db.upsert_vpn_node_client_state(
                    node_id=node_id,
                    subscription_id=subscription_id,
                    client_uuid=client_uuid,
                    client_email=client_email,
                    desired_enabled=desired_enabled,
                    desired_expires_at=desired_expires_at,
                    observed_enabled=observed_enabled,
                    observed_expires_at=observed_expires_at,
                    sync_state="ok",
                    last_error=None,
                    xui_sub_id=node_result.get("xui_sub_id") or sub_id,
                )
                ok_count += 1
            except Exception as exc:
                failed_count += 1
                node_had_failures = True
                await db.upsert_vpn_node_client_state(
                    node_id=node_id,
                    subscription_id=subscription_id,
                    client_uuid=client_uuid,
                    client_email=client_email,
                    desired_enabled=desired_enabled,
                    desired_expires_at=desired_expires_at,
                    observed_enabled=None,
                    observed_expires_at=None,
                    sync_state="error",
                    last_error=str(exc),
                    xui_sub_id=sub_id,
                )
                LOGGER.exception(
                    "Cluster sync failed for node_id=%s subscription_id=%s",
                    node_id,
                    subscription_id,
                )

        if bool(node.get("needs_backfill")):
            if node_had_failures:
                await db.mark_node_backfill_error(node_id, "sync errors occurred during backfill")
            else:
                remaining = await db.list_subscriptions_needing_sync(node_id, limit=1)
                if not remaining:
                    await db.mark_node_backfill_completed(node_id)

    manual_result = await _sync_manual_clients_from_canonical(db, nodes)
    return {
        "nodes": len(nodes),
        "processed": processed,
        "ok": ok_count,
        "failed": failed_count,
        "manual_processed": int(manual_result.get("processed", 0)),
        "manual_failed": int(manual_result.get("failed", 0)),
    }
