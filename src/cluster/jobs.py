from __future__ import annotations

import logging
from datetime import datetime, timezone
import time
from typing import Any

import aiohttp

from src.cluster.provisioner import create_client_on_node, delete_or_disable_client_on_node, update_client_on_node
from src.cluster.rebalance import backfill_unassigned_subscriptions, score_node
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


def _as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


async def _fetch_node_agent_metrics(node: dict[str, Any], timeout_seconds: int) -> dict[str, Any] | None:
    if not bool(node.get("metrics_agent_enabled")):
        return None
    url = str(node.get("metrics_agent_url") or "").strip()
    if not url:
        return None
    token = str(node.get("metrics_agent_token") or "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    timeout = aiohttp.ClientTimeout(total=max(1, int(timeout_seconds)))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                raise RuntimeError(f"metrics agent HTTP {response.status}: {data}")
            if not isinstance(data, dict):
                raise RuntimeError("metrics agent returned non-object payload")
            return data


def _server_status_value(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_agent_sample(payload: dict[str, Any]) -> dict[str, Any]:
    memory = payload.get("memory") if isinstance(payload.get("memory"), dict) else {}
    swap = payload.get("swap") if isinstance(payload.get("swap"), dict) else {}
    disk = payload.get("disk") if isinstance(payload.get("disk"), dict) else {}
    net = payload.get("network") if isinstance(payload.get("network"), dict) else {}
    load = payload.get("load") if isinstance(payload.get("load"), dict) else {}
    sockets = payload.get("sockets") if isinstance(payload.get("sockets"), dict) else {}
    return {
        "source": str(payload.get("source") or "agent"),
        "cpu_percent": _as_float(payload.get("cpu_percent")),
        "load1": _as_float(load.get("load1")),
        "load5": _as_float(load.get("load5")),
        "load15": _as_float(load.get("load15")),
        "memory_used_bytes": _as_int(memory.get("used_bytes")),
        "memory_total_bytes": _as_int(memory.get("total_bytes")),
        "swap_used_bytes": _as_int(swap.get("used_bytes")),
        "swap_total_bytes": _as_int(swap.get("total_bytes")),
        "disk_used_bytes": _as_int(disk.get("used_bytes")),
        "disk_total_bytes": _as_int(disk.get("total_bytes")),
        "net_rx_bytes": _as_int(net.get("rx_bytes")),
        "net_tx_bytes": _as_int(net.get("tx_bytes")),
        "tcp_connections": _as_int(sockets.get("tcp_connections")),
        "udp_sockets": _as_int(sockets.get("udp_sockets")),
        "uptime_seconds": _as_int(payload.get("uptime_seconds")),
    }


def _extract_xui_server_sample(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {}
    cpu_value = payload.get("cpu") or payload.get("cpuPercent") or payload.get("cpu_percent")
    if isinstance(cpu_value, dict):
        cpu_value = cpu_value.get("percent") or cpu_value.get("usedPercent")
    mem_total = (
        _server_status_value(payload, "mem", "total")
        or _server_status_value(payload, "memory", "total")
        or _server_status_value(payload, "memory", "total_bytes")
    )
    mem_used = (
        _server_status_value(payload, "mem", "current")
        or _server_status_value(payload, "mem", "used")
        or _server_status_value(payload, "memory", "used")
        or _server_status_value(payload, "memory", "used_bytes")
    )
    disk_total = _server_status_value(payload, "disk", "total") or _server_status_value(payload, "disk", "total_bytes")
    disk_used = (
        _server_status_value(payload, "disk", "current")
        or _server_status_value(payload, "disk", "used")
        or _server_status_value(payload, "disk", "used_bytes")
    )
    return {
        "source": "xui",
        "cpu_percent": _as_float(cpu_value),
        "memory_used_bytes": _as_int(mem_used),
        "memory_total_bytes": _as_int(mem_total),
        "disk_used_bytes": _as_int(disk_used),
        "disk_total_bytes": _as_int(disk_total),
        "xray_state": str(payload.get("xray") or payload.get("xrayState") or "") or None,
        "xray_version": str(payload.get("xrayVersion") or payload.get("version") or "") or None,
        "uptime_seconds": _as_int(payload.get("uptime") or payload.get("uptime_seconds")),
    }


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
    node_metrics = await db.list_node_assignment_metrics()
    nodes = node_metrics if isinstance(node_metrics, (list, tuple)) and node_metrics else None
    if nodes is None:
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
            started = time.perf_counter()
            await xui.start()
            inbound = await xui.get_inbound(inbound_id)
            reality = xui.parse_reality(inbound)
            list_clients = getattr(xui, "list_clients", None)
            clients = await list_clients(inbound_id) if callable(list_clients) else []
            probe_latency_ms = int((time.perf_counter() - started) * 1000)
            observed_enabled_clients = sum(1 for client in clients if bool(client.enabled))
            await db.mark_node_health(
                node_id=node_id,
                ok=True,
                error=None,
                reality_public_key=reality.public_key,
                reality_short_id=reality.short_id,
                reality_sni=reality.sni,
                reality_fingerprint=reality.fingerprint,
            )
            refreshed_node = dict(node)
            refreshed_node["last_health_ok"] = True
            refreshed_node["observed_enabled_clients"] = observed_enabled_clients
            snapshot_score = score_node(refreshed_node)
            await db.record_node_load_snapshot(
                node_id=node_id,
                assigned_active_subscriptions=int(node.get("active_assigned_subscriptions") or 0),
                observed_enabled_clients=observed_enabled_clients,
                total_traffic_bytes=int(node.get("total_traffic_bytes") or 0),
                peak_concurrency=int(node.get("peak_concurrency") or 0) if node.get("peak_concurrency") is not None else None,
                probe_latency_ms=probe_latency_ms,
                health_ok=True,
                health_error=None,
                score=(snapshot_score.score if snapshot_score is not None else None),
                meta={"source": "healthcheck_tick"},
            )
            ok_count += 1
        except Exception as exc:
            failed_count += 1
            await db.mark_node_health(node_id=node_id, ok=False, error=str(exc))
            await db.record_node_load_snapshot(
                node_id=node_id,
                assigned_active_subscriptions=int(node.get("active_assigned_subscriptions") or 0),
                observed_enabled_clients=int(node.get("observed_enabled_clients") or 0),
                total_traffic_bytes=int(node.get("total_traffic_bytes") or 0),
                peak_concurrency=int(node.get("peak_concurrency") or 0) if node.get("peak_concurrency") is not None else None,
                probe_latency_ms=None,
                health_ok=False,
                health_error=str(exc),
                score=None,
                meta={"source": "healthcheck_tick"},
            )
            LOGGER.exception("Cluster healthcheck failed for node_id=%s", node_id)
        finally:
            await xui.close()

    return {"checked": checked, "ok": ok_count, "failed": failed_count}


async def metrics_tick(db: DB, settings: Any) -> dict[str, int]:
    nodes = await db.get_active_vpn_nodes(lb_only=False)
    if not nodes:
        return {"nodes": 0, "node_samples": 0, "client_samples": 0, "failed": 0}

    node_samples = 0
    client_samples = 0
    failed = 0
    agent_timeout = int(getattr(settings, "vpn_metrics_agent_timeout_seconds", 5))

    for node in nodes:
        node_id = int(node["id"])
        inbound_id = _node_inbound_id(node)
        agent_payload: dict[str, Any] | None = None
        xui_payload: dict[str, Any] | None = None
        agent_ok = False
        xui_ok = False
        agent_error: str | None = None
        xui_error: str | None = None
        panel_latency_ms: int | None = None
        sample: dict[str, Any] = {"source": "none"}

        try:
            try:
                agent_payload = await _fetch_node_agent_metrics(node, agent_timeout)
                if agent_payload is not None:
                    agent_ok = True
                    sample = _extract_agent_sample(agent_payload)
            except Exception as exc:
                agent_error = str(exc)

            xui = _node_client(node)
            try:
                started = time.perf_counter()
                await xui.start()
                panel_latency_ms = int((time.perf_counter() - started) * 1000)
                xui_ok = True
                try:
                    xui_payload = await xui.get_server_status()
                    xui_sample = _extract_xui_server_sample(xui_payload)
                    if not agent_ok:
                        sample = xui_sample or {"source": "xui"}
                    else:
                        for key, value in xui_sample.items():
                            if key not in sample or sample.get(key) is None:
                                sample[key] = value
                except Exception as exc:
                    xui_error = str(exc)

                try:
                    traffic_stats = await xui.list_client_traffic_stats(inbound_id)
                except Exception as exc:
                    xui_error = "; ".join(part for part in [xui_error, str(exc)] if part)
                    traffic_stats = []
                subscriptions = await db.list_active_subscriptions_for_node(node_id, limit=10000)
                by_email = {str(sub.get("client_email") or "").strip().lower(): sub for sub in subscriptions}
                by_sub_id = {
                    str(sub.get("xui_sub_id") or "").strip().lower(): sub
                    for sub in subscriptions
                    if str(sub.get("xui_sub_id") or "").strip()
                }
                by_uuid = {str(sub.get("client_uuid") or "").strip().lower(): sub for sub in subscriptions}
                for stat in traffic_stats:
                    sub = None
                    if stat.sub_id:
                        sub = by_sub_id.get(stat.sub_id.strip().lower())
                    if sub is None:
                        sub = by_email.get(stat.email.strip().lower())
                    if sub is None and stat.client_uuid:
                        sub = by_uuid.get(stat.client_uuid.strip().lower())
                    if sub is None:
                        continue
                    ok = await db.record_subscription_metric_sample(
                        subscription_id=int(sub["id"]),
                        node_id=node_id,
                        client_email=stat.email,
                        xui_sub_id=stat.sub_id,
                        up_bytes=stat.up_bytes,
                        down_bytes=stat.down_bytes,
                        all_time_bytes=stat.all_time_bytes,
                        last_online_at=stat.last_online,
                        enabled=stat.enabled,
                        raw=stat.raw,
                    )
                    if ok:
                        client_samples += 1
            except Exception as exc:
                xui_error = str(exc)
            finally:
                try:
                    await xui.close()
                except Exception:
                    pass

            ok = await db.record_node_metric_sample(
                node_id=node_id,
                source=str(sample.get("source") or ("agent" if agent_ok else "xui" if xui_ok else "none")),
                agent_ok=agent_ok,
                agent_error=agent_error,
                xui_ok=xui_ok,
                xui_error=xui_error,
                cpu_percent=sample.get("cpu_percent"),
                load1=sample.get("load1"),
                load5=sample.get("load5"),
                load15=sample.get("load15"),
                memory_used_bytes=sample.get("memory_used_bytes"),
                memory_total_bytes=sample.get("memory_total_bytes"),
                swap_used_bytes=sample.get("swap_used_bytes"),
                swap_total_bytes=sample.get("swap_total_bytes"),
                disk_used_bytes=sample.get("disk_used_bytes"),
                disk_total_bytes=sample.get("disk_total_bytes"),
                net_rx_bytes=sample.get("net_rx_bytes"),
                net_tx_bytes=sample.get("net_tx_bytes"),
                tcp_connections=sample.get("tcp_connections"),
                udp_sockets=sample.get("udp_sockets"),
                uptime_seconds=sample.get("uptime_seconds"),
                xray_state=sample.get("xray_state"),
                xray_version=sample.get("xray_version"),
                panel_latency_ms=panel_latency_ms,
                raw={"agent": agent_payload, "xui": xui_payload},
            )
            if ok:
                node_samples += 1
            if agent_error or xui_error:
                failed += 1
        except Exception:
            failed += 1
            LOGGER.exception("Metrics collection failed for node_id=%s", node_id)

    cleanup = await db.cleanup_metric_samples(
        node_days=int(getattr(settings, "vpn_metrics_retention_days", 180)),
        client_days=int(getattr(settings, "vpn_client_metrics_retention_days", 90)),
    )
    return {
        "nodes": len(nodes),
        "node_samples": node_samples,
        "client_samples": client_samples,
        "failed": failed,
        **cleanup,
    }


async def sync_tick(db: DB, settings: Any) -> dict[str, int]:
    batch_size = max(1, int(getattr(settings, "vpn_cluster_sync_batch_size", 200)))
    assignment_result = await backfill_unassigned_subscriptions(db, settings, limit=batch_size)
    nodes = await db.get_cluster_sync_nodes()
    if not nodes:
        return {
            "nodes": 0,
            "processed": 0,
            "ok": 0,
            "failed": 0,
            "manual_processed": 0,
            "manual_failed": 0,
            "assignment_backfilled": int(assignment_result.get("assigned", 0)),
        }
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
        "assignment_backfilled": int(assignment_result.get("assigned", 0)),
    }
