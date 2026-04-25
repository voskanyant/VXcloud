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


@dataclass(frozen=True)
class PlannedMove:
    subscription: dict[str, Any]
    from_node_id: int
    to_node_id: int
    from_score: float
    to_score: float
    score_gap: float
    from_reasons: dict[str, float]
    to_reasons: dict[str, float]
    compatibility_pool: str


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


def node_ineligibility_reason(node: dict[str, Any], compatibility_pool: str | None = None) -> str | None:
    if not bool(node.get("is_active")):
        return "inactive"
    if not bool(node.get("lb_enabled")):
        return "lb_disabled"
    if bool(node.get("needs_backfill")):
        return "backfill_pending"
    if node.get("last_health_ok") is not True:
        return "health_not_ok"
    if _node_reality_from_health(node) is None:
        return "reality_missing"
    if compatibility_pool and str(node.get("compatibility_pool") or "default").strip() != str(compatibility_pool).strip():
        return "pool_mismatch"
    return None


def score_node(node: dict[str, Any], compatibility_pool: str | None = None) -> NodeScore | None:
    if node_ineligibility_reason(node, compatibility_pool=compatibility_pool) is not None:
        return None

    active_assigned = float(node.get("active_assigned_subscriptions") or 0)
    observed_enabled = float(node.get("observed_enabled_clients") or 0)
    weekly_traffic = float(node.get("weekly_traffic_bytes") or node.get("total_traffic_bytes") or 0)
    peak_concurrency = float(node.get("peak_concurrency") or 0)
    p95_concurrency = float(node.get("p95_concurrency") or peak_concurrency or 0)
    probe_latency_ms = float(node.get("p95_probe_latency_ms") or node.get("probe_latency_ms") or 0)
    health_failures = float(node.get("health_failures") or 0)
    moves_in_week = float(node.get("moves_in_week") or 0)
    weight = float(node.get("backend_weight") or 100)
    bandwidth_capacity = float(node.get("bandwidth_capacity_mbps") or 1000)
    connection_capacity = float(node.get("connection_capacity") or 10000)
    if weight <= 0:
        weight = 100.0

    reasons = {
        "active_assigned": active_assigned * 4.0,
        "observed_enabled": observed_enabled * 3.0,
        "weekly_traffic": weekly_traffic / float(10 * 1024 * 1024 * 1024),
        "peak_concurrency": peak_concurrency * 2.0,
        "p95_concurrency": p95_concurrency * 1.5,
        "probe_latency": probe_latency_ms / 50.0,
        "health_failures": health_failures * 2.5,
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


def _simulated_score(node: dict[str, Any], *, compatibility_pool: str | None = None) -> NodeScore | None:
    payload = dict(node)
    payload["active_assigned_subscriptions"] = max(0, int(payload.get("active_assigned_subscriptions") or 0))
    payload["moves_in_week"] = max(0, int(payload.get("moves_in_week") or 0))
    return score_node(payload, compatibility_pool=compatibility_pool)


async def preview_rebalance_plan(db: DB, settings: Settings) -> dict[str, Any]:
    metrics = await db.list_node_assignment_metrics()
    generated_at = _workflow_now(settings).astimezone()
    if not metrics:
        return {"generated_at": generated_at, "nodes": [], "moves": [], "summary": {"eligible_nodes": 0, "planned_moves": 0}}

    nodes = [dict(item) for item in metrics]
    by_pool: dict[str, list[dict[str, Any]]] = {}
    preview_nodes: list[dict[str, Any]] = []
    for node in nodes:
        pool = str(node.get("compatibility_pool") or "default").strip() or "default"
        issue = node_ineligibility_reason(node, compatibility_pool=pool)
        scored = score_node(node, compatibility_pool=pool) if issue is None else None
        preview_nodes.append(
            {
                "id": int(node.get("id") or 0),
                "name": str(node.get("name") or f"node-{int(node.get('id') or 0)}"),
                "pool": pool,
                "eligible": issue is None,
                "issue": issue or "",
                "score": round(float(scored.score), 2) if scored is not None else None,
                "reasons": dict(scored.reasons) if scored is not None else {},
                "active_assigned_subscriptions": int(node.get("active_assigned_subscriptions") or 0),
                "observed_enabled_clients": int(node.get("observed_enabled_clients") or 0),
                "weekly_traffic_bytes": int(node.get("weekly_traffic_bytes") or node.get("total_traffic_bytes") or 0),
                "peak_concurrency": int(node.get("peak_concurrency") or 0),
                "p95_probe_latency_ms": int(node.get("p95_probe_latency_ms") or node.get("probe_latency_ms") or 0),
                "bandwidth_capacity_mbps": int(node.get("bandwidth_capacity_mbps") or 0),
                "connection_capacity": int(node.get("connection_capacity") or 0),
                "backend_weight": int(node.get("backend_weight") or 0),
            }
        )
        by_pool.setdefault(pool, []).append(dict(node))

    planned_moves: list[PlannedMove] = []
    moved_subscription_ids: set[int] = set()

    for pool, pool_nodes in by_pool.items():
        eligible = [dict(item) for item in pool_nodes if score_node(item, compatibility_pool=pool) is not None]
        if len(eligible) < 2:
            continue
        for node in eligible:
            node["_candidate_cache"] = await db.list_rebalance_candidates(
                int(node["id"]),
                cooldown_hours=int(settings.vpn_rebalance_cooldown_hours),
                limit=max(1, int(settings.vpn_rebalance_max_moves_per_node)),
            )
            node["_candidate_index"] = 0
            node["_move_cap"] = max(
                1,
                min(
                    int(settings.vpn_rebalance_max_moves_per_node),
                    max(1, int(int(node.get("active_assigned_subscriptions") or 0) * float(settings.vpn_rebalance_move_fraction or 0.2))),
                ),
            )
            node["_moves_planned_out"] = 0
            node["_moves_planned_in"] = 0

        max_iterations = max(1, sum(int(node.get("_move_cap") or 0) + 1 for node in eligible) * 2)
        iterations = 0
        while True:
            iterations += 1
            if iterations > max_iterations:
                LOGGER.debug("Stopping rebalance preview loop for pool=%s after %s iterations", pool, iterations)
                break
            if not any(
                int(node.get("_moves_planned_out", 0) or 0) < int(node.get("_move_cap", 0) or 0)
                and int(node.get("_moves_planned_in", 0) or 0) == 0
                and int(node.get("active_assigned_subscriptions") or 0) > 0
                and int(node.get("_candidate_index", 0) or 0) < len(list(node.get("_candidate_cache") or []))
                for node in eligible
            ):
                break
            scored = [item for item in (_simulated_score(node, compatibility_pool=pool) for node in eligible) if item is not None]
            if len(scored) < 2:
                break
            scored.sort(key=lambda item: (item.score, int(item.node.get("id", 0) or 0)))
            underloaded = scored[0]
            overloaded = next(
                (
                    item
                    for item in reversed(scored)
                    if int(item.node.get("_moves_planned_out", 0) or 0) < int(item.node.get("_move_cap", 0) or 0)
                    and int(item.node.get("_moves_planned_in", 0) or 0) == 0
                    and int(item.node.get("active_assigned_subscriptions") or 0) > 0
                ),
                None,
            )
            if overloaded is None:
                break
            score_gap = float(overloaded.score) - float(underloaded.score)
            if score_gap < float(settings.vpn_rebalance_min_score_gap):
                break
            if int(overloaded.node["id"]) == int(underloaded.node["id"]):
                break

            candidate_cache = list(overloaded.node.get("_candidate_cache") or [])
            candidate_index = int(overloaded.node.get("_candidate_index") or 0)
            next_candidate: dict[str, Any] | None = None
            while candidate_index < len(candidate_cache):
                candidate = dict(candidate_cache[candidate_index])
                candidate_index += 1
                if int(candidate.get("id") or 0) in moved_subscription_ids:
                    continue
                next_candidate = candidate
                break
            overloaded.node["_candidate_index"] = candidate_index
            if next_candidate is None:
                overloaded.node["_moves_planned_out"] = int(overloaded.node.get("_move_cap") or 0)
                continue

            moved_subscription_ids.add(int(next_candidate["id"]))
            overloaded.node["active_assigned_subscriptions"] = max(0, int(overloaded.node.get("active_assigned_subscriptions") or 0) - 1)
            overloaded.node["_moves_planned_out"] = int(overloaded.node.get("_moves_planned_out") or 0) + 1
            underloaded.node["active_assigned_subscriptions"] = int(underloaded.node.get("active_assigned_subscriptions") or 0) + 1
            underloaded.node["moves_in_week"] = int(underloaded.node.get("moves_in_week") or 0) + 1
            underloaded.node["_moves_planned_in"] = int(underloaded.node.get("_moves_planned_in") or 0) + 1

            planned_moves.append(
                PlannedMove(
                    subscription=next_candidate,
                    from_node_id=int(overloaded.node["id"]),
                    to_node_id=int(underloaded.node["id"]),
                    from_score=float(overloaded.score),
                    to_score=float(underloaded.score),
                    score_gap=score_gap,
                    from_reasons=dict(overloaded.reasons),
                    to_reasons=dict(underloaded.reasons),
                    compatibility_pool=pool,
                )
            )

    return {
        "generated_at": generated_at,
        "nodes": preview_nodes,
        "moves": [
            {
                "id": int(item.subscription["id"]),
                "subscription_id": int(item.subscription["id"]),
                "display_name": str(item.subscription.get("display_name") or item.subscription.get("client_email") or item.subscription["id"]),
                "alias_fqdn": str(item.subscription.get("alias_fqdn") or ""),
                "vless_url": str(item.subscription.get("vless_url") or ""),
                "from_node_id": item.from_node_id,
                "to_node_id": item.to_node_id,
                "score_gap": round(item.score_gap, 2),
                "from_score": round(item.from_score, 2),
                "to_score": round(item.to_score, 2),
                "compatibility_pool": item.compatibility_pool,
            }
            for item in planned_moves
        ],
        "summary": {
            "eligible_nodes": sum(1 for item in preview_nodes if item["eligible"]),
            "planned_moves": len(planned_moves),
            "compatible_pools": len({str(item["pool"]) for item in preview_nodes if item["eligible"]}),
        },
    }


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
    existing = await db.list_subscriptions_by_assignment_state(
        [ASSIGNMENT_PLANNED, ASSIGNMENT_PRESYNC, ASSIGNMENT_CUTOVER, ASSIGNMENT_CLEANUP],
        limit=1,
    )
    if existing:
        return 0
    preview = await preview_rebalance_plan(db, settings)
    candidates = list(preview.get("moves") or [])
    if not candidates:
        return 0
    planned = 0
    now = _workflow_now(settings).astimezone()
    for sub in candidates:
        from_node_id = int(sub.get("from_node_id") or 0)
        to_node_id = int(sub.get("to_node_id") or 0)
        if from_node_id <= 0 or to_node_id <= 0:
            continue
        compatibility_pool = str(sub.get("compatibility_pool") or "default")
        await db.update_subscription_assignment(
            int(sub["id"]),
            assigned_node_id=from_node_id,
            vless_url=str(sub.get("vless_url") or ""),
            assignment_source="weekly_plan",
            migration_state="ready",
            alias_fqdn=str(sub.get("alias_fqdn") or "") or None,
            current_node_id=from_node_id,
            desired_node_id=to_node_id,
            assignment_state=ASSIGNMENT_PLANNED,
            ttl_seconds=int(getattr(settings, "vpn_alias_default_ttl", 300)),
            compatibility_pool=compatibility_pool,
            planned_at=now,
            mark_rebalanced=False,
        )
        await db.record_rebalance_decision(
            subscription_id=int(sub["id"]),
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            decision_kind="weekly_rebalance_plan",
            score_before=float(sub.get("from_score") or 0.0),
            score_after=float(sub.get("to_score") or 0.0),
            reason="planned DNS alias rebalance",
            details={"score_gap": float(sub.get("score_gap") or 0.0), "compatibility_pool": compatibility_pool},
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


async def manual_rebalance_tick(db: DB, settings: Settings) -> dict[str, int]:
    """Run the rebalance workflow immediately for an operator-triggered cutover."""
    bootstrapped_aliases = await bootstrap_aliasless_subscriptions(
        db,
        settings,
        limit=max(1, int(getattr(settings, "vpn_cluster_sync_batch_size", 200))),
    )
    assignment_result = await backfill_unassigned_subscriptions(
        db,
        settings,
        limit=max(1, int(getattr(settings, "vpn_cluster_sync_batch_size", 200))),
    )
    presynced_existing = await _presync_planned_moves(db, settings)
    cutover_existing = await _cutover_presynced_moves(db, settings)
    cleaned = await _cleanup_cutover_moves(db, settings)
    planned = await _plan_weekly_moves(db, settings)
    presynced_new = await _presync_planned_moves(db, settings)
    cutover_new = await _cutover_presynced_moves(db, settings)
    return {
        "bootstrapped_aliases": bootstrapped_aliases,
        "assigned": int(assignment_result.get("assigned", 0)),
        "planned": planned,
        "presynced": presynced_existing + presynced_new,
        "cutover": cutover_existing + cutover_new,
        "cleaned": cleaned,
    }
