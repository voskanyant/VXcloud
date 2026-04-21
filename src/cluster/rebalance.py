from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.cluster.provisioner import create_client_on_node, delete_or_disable_client_on_node, update_client_on_node
from src.config import Settings
from src.db import DB
from src.dns_alias import (
    ASSIGNMENT_CUTOVER,
    ASSIGNMENT_PLANNED,
    ASSIGNMENT_PRESYNC,
    ASSIGNMENT_STEADY,
    ASSIGNMENT_CLEANUP,
    ensure_subscription_alias_record,
    generate_subscription_alias,
)
from src.subscription_links import build_subscription_vless_url
from src.xui_client import InboundRealityInfo


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class NodeScore:
    node: dict[str, Any]
    score: float
    reasons: dict[str, float]


def _node_reality_from_health(node: dict[str, Any]) -> InboundRealityInfo | None:
    public_key = str(node.get("last_reality_public_key") or "").strip()
    short_id = str(node.get("last_reality_short_id") or "").strip()
    sni = str(node.get("last_reality_sni") or "").strip()
    fingerprint = str(node.get("last_reality_fingerprint") or "chrome").strip() or "chrome"
    if not (public_key and short_id and sni):
        return None
    return InboundRealityInfo(
        public_key=public_key,
        short_id=short_id,
        sni=sni,
        fingerprint=fingerprint,
    )


def score_node(node: dict[str, Any], compatibility_pool: str | None = None) -> NodeScore | None:
    if not bool(node.get("is_active")):
        return None
    if not bool(node.get("lb_enabled")):
        return None
    if bool(node.get("needs_backfill")):
        return None
    if node.get("last_health_ok") is not True:
        return None
    if _node_reality_from_health(node) is None:
        return None
    if compatibility_pool and str(node.get("compatibility_pool") or "default").strip() != str(compatibility_pool).strip():
        return None

    active_assigned = float(node.get("active_assigned_subscriptions") or 0)
    observed_enabled = float(node.get("observed_enabled_clients") or 0)
    total_traffic = float(node.get("total_traffic_bytes") or 0)
    peak_concurrency = float(node.get("peak_concurrency") or 0)
    probe_latency_ms = float(node.get("probe_latency_ms") or 0)
    moves_in_week = float(node.get("moves_in_week") or 0)
    weight = float(node.get("backend_weight") or 100)
    bandwidth_capacity = float(node.get("bandwidth_capacity_mbps") or 1000)
    connection_capacity = float(node.get("connection_capacity") or 10000)
    if weight <= 0:
        weight = 100.0

    reasons = {
        "active_assigned": active_assigned * 4.0,
        "observed_enabled": observed_enabled * 3.0,
        "traffic": total_traffic / float(10 * 1024 * 1024 * 1024),
        "peak_concurrency": peak_concurrency * 2.0,
        "probe_latency": probe_latency_ms / 50.0,
        "recent_moves": moves_in_week * 1.5,
    }
    raw_score = sum(reasons.values())
    capacity_factor = max((weight / 100.0) * max(bandwidth_capacity / 1000.0, 0.25) * max(connection_capacity / 10000.0, 0.25), 0.25)
    normalized = raw_score / capacity_factor
    return NodeScore(node=node, score=normalized, reasons=reasons)


async def pick_best_node(db: DB, *, compatibility_pool: str | None = None) -> NodeScore | None:
    metrics = await db.list_node_assignment_metrics()
    scored = [item for item in (score_node(node, compatibility_pool=compatibility_pool) for node in metrics) if item is not None]
    if not scored:
        return None
    scored.sort(key=lambda item: (item.score, int(item.node.get("id", 0) or 0)))
    return scored[0]


def _workflow_now(settings: Settings) -> datetime:
    return datetime.now(ZoneInfo(str(settings.timezone or "Europe/Moscow")))


async def _ensure_subscription_alias(
    db: DB,
    settings: Settings,
    sub: dict[str, Any],
    node: dict[str, Any],
    reality: InboundRealityInfo,
    *,
    assignment_source: str,
    migration_state: str,
    current_node_id: int,
    desired_node_id: int | None = None,
    assignment_state: str = ASSIGNMENT_STEADY,
    mark_rebalanced: bool = False,
) -> None:
    alias_fqdn = str(sub.get("alias_fqdn") or "").strip() or generate_subscription_alias(settings)
    alias_result = await ensure_subscription_alias_record(
        settings=settings,
        alias_fqdn=alias_fqdn,
        node=node,
        ttl=(
            int(getattr(settings, "vpn_alias_cutover_ttl", 60))
            if assignment_state in {ASSIGNMENT_PLANNED, ASSIGNMENT_PRESYNC, ASSIGNMENT_CUTOVER}
            else int(getattr(settings, "vpn_alias_default_ttl", 300))
        ),
        record_id=str(sub.get("dns_record_id") or "").strip() or None,
    )
    vless_url = build_subscription_vless_url(
        settings=settings,
        node=node,
        client_uuid=str(sub["client_uuid"]),
        reality=reality,
        subscription={"alias_fqdn": alias_fqdn},
    )
    await db.update_subscription_assignment(
        int(sub["id"]),
        assigned_node_id=current_node_id,
        vless_url=vless_url,
        assignment_source=assignment_source,
        migration_state=migration_state,
        alias_fqdn=alias_fqdn,
        current_node_id=current_node_id,
        desired_node_id=desired_node_id,
        assignment_state=assignment_state,
        ttl_seconds=alias_result.ttl,
        overlap_until=sub.get("overlap_until"),
        dns_provider=alias_result.provider,
        dns_record_id=alias_result.record_id,
        last_dns_change_id=alias_result.change_id,
        compatibility_pool=str(sub.get("compatibility_pool") or node.get("compatibility_pool") or "default"),
        mark_rebalanced=mark_rebalanced,
    )


async def bootstrap_aliasless_subscriptions(db: DB, settings: Settings, *, limit: int = 200) -> int:
    pending = await db.list_subscriptions_missing_alias(limit=limit)
    if not pending:
        return 0
    count = 0
    for sub in pending:
        node_id = int(sub.get("current_node_id") or sub.get("assigned_node_id") or 0)
        if node_id <= 0:
            continue
        node = await db.get_vpn_node(node_id)
        if not node:
            continue
        reality = _node_reality_from_health(node)
        if reality is None:
            continue
        await _ensure_subscription_alias(
            db,
            settings,
            sub,
            node,
            reality,
            assignment_source=str(sub.get("assignment_source") or "alias_bootstrap"),
            migration_state=str(sub.get("migration_state") or "ready"),
            current_node_id=node_id,
            desired_node_id=int(sub.get("desired_node_id") or 0) or None,
            assignment_state=str(sub.get("assignment_state") or ASSIGNMENT_STEADY),
        )
        count += 1
    return count


async def _plan_weekly_moves(db: DB, settings: Settings) -> int:
    metrics = await db.list_node_assignment_metrics()
    scored = [item for item in (score_node(node) for node in metrics) if item is not None]
    if len(scored) < 2:
        return 0
    existing = await db.list_subscriptions_by_assignment_state(
        [ASSIGNMENT_PLANNED, ASSIGNMENT_PRESYNC, ASSIGNMENT_CUTOVER, ASSIGNMENT_CLEANUP],
        limit=1,
    )
    if existing:
        return 0
    scored.sort(key=lambda item: item.score)
    underloaded = scored[0]
    overloaded = scored[-1]
    if (overloaded.score - underloaded.score) < float(settings.vpn_rebalance_min_score_gap):
        return 0
    max_moves = max(1, int(settings.vpn_rebalance_max_moves_per_node))
    overload_count = int(overloaded.node.get("active_assigned_subscriptions") or 0)
    move_cap = max(1, min(max_moves, int(overload_count * float(settings.vpn_rebalance_move_fraction or 0.2))))
    candidates = await db.list_rebalance_candidates(
        int(overloaded.node["id"]),
        cooldown_hours=int(settings.vpn_rebalance_cooldown_hours),
        limit=move_cap,
    )
    planned = 0
    now = _workflow_now(settings).astimezone()
    for sub in candidates:
        compatibility_pool = str(sub.get("compatibility_pool") or overloaded.node.get("compatibility_pool") or "default")
        to_node = await pick_best_node(db, compatibility_pool=compatibility_pool)
        if to_node is None or int(to_node.node["id"]) == int(overloaded.node["id"]):
            continue
        await db.update_subscription_assignment(
            int(sub["id"]),
            assigned_node_id=int(overloaded.node["id"]),
            vless_url=str(sub.get("vless_url") or ""),
            assignment_source="weekly_plan",
            migration_state="ready",
            alias_fqdn=str(sub.get("alias_fqdn") or "") or None,
            current_node_id=int(overloaded.node["id"]),
            desired_node_id=int(to_node.node["id"]),
            assignment_state=ASSIGNMENT_PLANNED,
            ttl_seconds=int(getattr(settings, "vpn_alias_default_ttl", 300)),
            compatibility_pool=compatibility_pool,
            planned_at=now,
            mark_rebalanced=False,
        )
        await db.record_rebalance_decision(
            subscription_id=int(sub["id"]),
            from_node_id=int(overloaded.node["id"]),
            to_node_id=int(to_node.node["id"]),
            decision_kind="weekly_rebalance_plan",
            score_before=overloaded.score,
            score_after=to_node.score,
            reason="planned DNS alias rebalance",
            details={"from_reasons": overloaded.reasons, "to_reasons": to_node.reasons},
        )
        planned += 1
    return planned


async def _presync_planned_moves(db: DB, settings: Settings) -> int:
    rows = await db.list_subscriptions_by_assignment_state([ASSIGNMENT_PLANNED], limit=500)
    moved = 0
    for sub in rows:
        desired_node_id = int(sub.get("desired_node_id") or 0)
        if desired_node_id <= 0:
            continue
        desired_node = await db.get_vpn_node(desired_node_id)
        if not desired_node:
            continue
        reality = _node_reality_from_health(desired_node)
        if reality is None:
            continue
        try:
            try:
                await create_client_on_node(
                    desired_node,
                    str(sub["client_uuid"]),
                    str(sub["client_email"]),
                    str(sub.get("xui_sub_id") or "").strip() or None,
                    sub["expires_at"],
                    int(getattr(settings, "max_devices_per_sub", 1)),
                    flow=str(getattr(settings, "vpn_flow", "xtls-rprx-vision") or ""),
                )
            except Exception:
                await update_client_on_node(
                    desired_node,
                    str(sub["client_uuid"]),
                    str(sub["client_email"]),
                    str(sub.get("xui_sub_id") or "").strip() or None,
                    sub["expires_at"],
                    int(getattr(settings, "max_devices_per_sub", 1)),
                    flow=str(getattr(settings, "vpn_flow", "xtls-rprx-vision") or ""),
                )
            current_node = await db.get_vpn_node(int(sub.get("current_node_id") or sub.get("assigned_node_id") or 0))
            if current_node and _node_reality_from_health(current_node):
                await _ensure_subscription_alias(
                    db,
                    settings,
                    sub,
                    current_node,
                    _node_reality_from_health(current_node),
                    assignment_source="weekly_presync",
                    migration_state="ready",
                    current_node_id=int(sub.get("current_node_id") or sub.get("assigned_node_id") or 0),
                    desired_node_id=desired_node_id,
                    assignment_state=ASSIGNMENT_PRESYNC,
                )
                await db.extend_subscription(
                    int(sub["id"]),
                    sub["expires_at"],
                    str(sub.get("vless_url") or ""),
                    assignment_state=ASSIGNMENT_PRESYNC,
                    presynced_at=_workflow_now(settings).astimezone(),
                    ttl_seconds=int(getattr(settings, "vpn_alias_cutover_ttl", 60)),
                    desired_node_id=desired_node_id,
                )
                moved += 1
        except Exception:
            LOGGER.exception("Failed to presync rebalance destination for subscription_id=%s", int(sub["id"]))
    return moved


async def _cutover_presynced_moves(db: DB, settings: Settings) -> int:
    rows = await db.list_subscriptions_by_assignment_state([ASSIGNMENT_PRESYNC], limit=500)
    moved = 0
    overlap_until = _workflow_now(settings).astimezone() + timedelta(minutes=int(getattr(settings, "vpn_alias_overlap_minutes", 310)))
    for sub in rows:
        desired_node_id = int(sub.get("desired_node_id") or 0)
        if desired_node_id <= 0:
            continue
        desired_node = await db.get_vpn_node(desired_node_id)
        if not desired_node:
            continue
        reality = _node_reality_from_health(desired_node)
        if reality is None:
            continue
        await _ensure_subscription_alias(
            db,
            settings,
            {**sub, "overlap_until": overlap_until},
            desired_node,
            reality,
            assignment_source="weekly_cutover",
            migration_state="ready",
            current_node_id=int(sub.get("current_node_id") or sub.get("assigned_node_id") or 0),
            desired_node_id=desired_node_id,
            assignment_state=ASSIGNMENT_CUTOVER,
            mark_rebalanced=True,
        )
        await db.extend_subscription(
            int(sub["id"]),
            sub["expires_at"],
            build_subscription_vless_url(
                settings=settings,
                node=desired_node,
                client_uuid=str(sub["client_uuid"]),
                reality=reality,
                subscription={"alias_fqdn": str(sub.get("alias_fqdn") or "")},
            ),
            assigned_node_id=int(sub.get("current_node_id") or sub.get("assigned_node_id") or 0),
            current_node_id=int(sub.get("current_node_id") or sub.get("assigned_node_id") or 0),
            desired_node_id=desired_node_id,
            assignment_state=ASSIGNMENT_CUTOVER,
            overlap_until=overlap_until,
            cutover_at=_workflow_now(settings).astimezone(),
            ttl_seconds=int(getattr(settings, "vpn_alias_cutover_ttl", 60)),
            compatibility_pool=str(sub.get("compatibility_pool") or desired_node.get("compatibility_pool") or "default"),
        )
        moved += 1
    return moved


async def _cleanup_cutover_moves(db: DB, settings: Settings) -> int:
    rows = await db.list_subscriptions_by_assignment_state([ASSIGNMENT_CUTOVER, ASSIGNMENT_CLEANUP], limit=500)
    cleaned = 0
    now = _workflow_now(settings).astimezone()
    for sub in rows:
        overlap_until = sub.get("overlap_until")
        if overlap_until and overlap_until > now:
            continue
        current_node_id = int(sub.get("current_node_id") or sub.get("assigned_node_id") or 0)
        desired_node_id = int(sub.get("desired_node_id") or 0)
        if desired_node_id <= 0:
            continue
        old_node = await db.get_vpn_node(current_node_id) if current_node_id > 0 else None
        new_node = await db.get_vpn_node(desired_node_id)
        if not new_node:
            continue
        reality = _node_reality_from_health(new_node)
        if reality is None:
            continue
        if old_node:
            try:
                await delete_or_disable_client_on_node(
                    old_node,
                    str(sub["client_uuid"]),
                    str(sub["client_email"]),
                    str(sub.get("xui_sub_id") or "").strip() or None,
                    sub["expires_at"],
                    int(getattr(settings, "max_devices_per_sub", 1)),
                    flow=str(getattr(settings, "vpn_flow", "xtls-rprx-vision") or ""),
                )
            except Exception:
                LOGGER.exception("Cleanup failed for old node client subscription_id=%s", int(sub["id"]))
                continue
        alias_result = await ensure_subscription_alias_record(
            settings=settings,
            alias_fqdn=str(sub.get("alias_fqdn") or ""),
            node=new_node,
            ttl=int(getattr(settings, "vpn_alias_default_ttl", 300)),
            record_id=str(sub.get("dns_record_id") or "").strip() or None,
        )
        vless_url = build_subscription_vless_url(
            settings=settings,
            node=new_node,
            client_uuid=str(sub["client_uuid"]),
            reality=reality,
            subscription={"alias_fqdn": str(sub.get("alias_fqdn") or "")},
        )
        await db.update_subscription_assignment(
            int(sub["id"]),
            assigned_node_id=desired_node_id,
            vless_url=vless_url,
            assignment_source="weekly_cleanup",
            migration_state="ready",
            alias_fqdn=str(sub.get("alias_fqdn") or "") or None,
            current_node_id=desired_node_id,
            desired_node_id=None,
            assignment_state=ASSIGNMENT_STEADY,
            ttl_seconds=alias_result.ttl,
            overlap_until=None,
            dns_provider=alias_result.provider,
            dns_record_id=alias_result.record_id,
            last_dns_change_id=alias_result.change_id,
            compatibility_pool=str(sub.get("compatibility_pool") or new_node.get("compatibility_pool") or "default"),
            mark_rebalanced=True,
        )
        cleaned += 1
    return cleaned


async def backfill_unassigned_subscriptions(db: DB, settings: Settings, *, limit: int = 200) -> dict[str, int]:
    pending = await db.list_unassigned_active_subscriptions(limit=limit)
    if not pending:
        return {"processed": 0, "assigned": 0, "skipped": 0}

    assigned = 0
    skipped = 0
    for sub in pending:
        best = await pick_best_node(db, compatibility_pool=str(sub.get("compatibility_pool") or "default"))
        if best is None:
            skipped += 1
            continue
        reality = _node_reality_from_health(best.node)
        if reality is None:
            skipped += 1
            continue
        await _ensure_subscription_alias(
            db,
            settings,
            sub,
            best.node,
            reality,
            assignment_source="migration_backfill",
            migration_state="ready",
            current_node_id=int(best.node["id"]),
            desired_node_id=None,
            assignment_state=ASSIGNMENT_STEADY,
            mark_rebalanced=False,
        )
        await db.record_rebalance_decision(
            subscription_id=int(sub["id"]),
            from_node_id=None,
            to_node_id=int(best.node["id"]),
            decision_kind="migration_backfill",
            score_before=None,
            score_after=best.score,
            reason="subscription had no assigned node",
            details={"reasons": best.reasons},
        )
        assigned += 1

    return {"processed": len(pending), "assigned": assigned, "skipped": skipped}


async def rebalance_tick(db: DB, settings: Settings) -> dict[str, int]:
    bootstrapped_aliases = await bootstrap_aliasless_subscriptions(db, settings, limit=max(1, int(getattr(settings, "vpn_cluster_sync_batch_size", 200))))
    assignment_result = await backfill_unassigned_subscriptions(
        db,
        settings,
        limit=max(1, int(getattr(settings, "vpn_cluster_sync_batch_size", 200))),
    )
    planned = 0
    presynced = await _presync_planned_moves(db, settings)
    cutover = await _cutover_presynced_moves(db, settings)
    cleaned = await _cleanup_cutover_moves(db, settings)
    now = _workflow_now(settings)
    if now.weekday() == 6 and now.hour == 1 and now.minute < 10:
        planned = await _plan_weekly_moves(db, settings)
    return {
        "bootstrapped_aliases": bootstrapped_aliases,
        "assigned": int(assignment_result.get("assigned", 0)),
        "planned": planned,
        "presynced": presynced,
        "cutover": cutover,
        "cleaned": cleaned,
    }
