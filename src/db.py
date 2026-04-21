from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg


WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET = 10**12


def _new_feed_token() -> str:
    return secrets.token_urlsafe(24)


def _site_placeholder_telegram_id_for_auth_user(user_id: int) -> int:
    return -(WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET + int(user_id))


class DB:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=10)

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()

    async def fetch_bot_site_text_overrides(self) -> dict[str, str]:
        assert self.pool is not None
        try:
            rows = await self.pool.fetch(
                """
                SELECT key, value
                FROM blog_sitetext
                WHERE key LIKE 'bot.%'
                ORDER BY key
                """
            )
        except asyncpg.UndefinedTableError:
            return {}
        out: dict[str, str] = {}
        for row in rows:
            key = str(row["key"] or "").strip()
            value = str(row["value"] or "")
            if key.startswith("bot."):
                out[key[4:]] = value
        return out

    async def upsert_user(self, telegram_id: int, username: str | None, first_name: str | None) -> int:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            INSERT INTO users (telegram_id, username, first_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id)
            DO UPDATE SET username = EXCLUDED.username, first_name = EXCLUDED.first_name
            RETURNING id
            """,
            telegram_id,
            username,
            first_name,
        )
        return int(row["id"])

    async def get_active_subscription(self, user_id: int) -> dict[str, Any] | None:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            SELECT *
            FROM subscriptions
            WHERE user_id = $1
              AND is_active = TRUE
              AND expires_at > NOW()
            ORDER BY expires_at DESC, id DESC
            LIMIT 1
            """,
            user_id,
        )
        return dict(row) if row else None

    async def list_subscriptions(self, user_id: int) -> list[dict[str, Any]]:
        assert self.pool is not None
        rows = await self.pool.fetch(
            """
            SELECT *
            FROM subscriptions
            WHERE user_id = $1
            ORDER BY expires_at DESC, id DESC
            """,
            user_id,
        )
        return [dict(r) for r in rows]

    async def get_subscription(self, user_id: int, subscription_id: int) -> dict[str, Any] | None:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            SELECT *
            FROM subscriptions
            WHERE id = $1
              AND user_id = $2
            LIMIT 1
            """,
            subscription_id,
            user_id,
        )
        return dict(row) if row else None

    async def rename_subscription(self, user_id: int, subscription_id: int, display_name: str) -> bool:
        assert self.pool is not None
        normalized = display_name.strip()
        try:
            row = await self.pool.fetchrow(
                """
                UPDATE subscriptions
                SET display_name = $3,
                    updated_at = NOW()
                WHERE id = $1
                  AND user_id = $2
                RETURNING id
                """,
                subscription_id,
                user_id,
                normalized,
            )
        except asyncpg.UndefinedColumnError:
            return False
        return row is not None

    async def revoke_subscription(self, user_id: int, subscription_id: int) -> bool:
        assert self.pool is not None
        try:
            row = await self.pool.fetchrow(
                """
                UPDATE subscriptions
                SET revoked_at = NOW(),
                    is_active = FALSE,
                    updated_at = NOW()
                WHERE id = $1
                  AND user_id = $2
                RETURNING id
                """,
                subscription_id,
                user_id,
            )
        except asyncpg.UndefinedColumnError:
            row = await self.pool.fetchrow(
                """
                UPDATE subscriptions
                SET is_active = FALSE,
                    updated_at = NOW()
                WHERE id = $1
                  AND user_id = $2
                RETURNING id
                """,
                subscription_id,
                user_id,
            )
        return row is not None

    async def delete_subscription(self, user_id: int, subscription_id: int) -> bool:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            DELETE FROM subscriptions
            WHERE id = $1
              AND user_id = $2
              AND NOT (
                    is_active = TRUE
                AND expires_at > NOW()
                AND revoked_at IS NULL
              )
            RETURNING id
            """,
            subscription_id,
            user_id,
        )
        return row is not None

    async def get_user_client_code(self, user_id: int) -> str | None:
        assert self.pool is not None
        try:
            row = await self.pool.fetchrow(
                """
                SELECT client_code
                FROM users
                WHERE id = $1
                LIMIT 1
                """,
                user_id,
            )
        except asyncpg.UndefinedColumnError:
            # Early rollout compatibility: column may not exist yet.
            return None
        if not row:
            return None
        value = row["client_code"]
        return str(value) if value else None

    async def get_user_identity(self, user_id: int) -> dict[str, str | None] | None:
        assert self.pool is not None
        try:
            row = await self.pool.fetchrow(
                """
                SELECT client_code, username, first_name
                FROM users
                WHERE id = $1
                LIMIT 1
                """,
                user_id,
            )
        except asyncpg.UndefinedColumnError:
            row = await self.pool.fetchrow(
                """
                SELECT NULL::TEXT AS client_code, username, first_name
                FROM users
                WHERE id = $1
                LIMIT 1
                """,
                user_id,
            )
        if not row:
            return None
        return {
            "client_code": (str(row["client_code"]) if row["client_code"] else None),
            "username": (str(row["username"]) if row["username"] else None),
            "first_name": (str(row["first_name"]) if row["first_name"] else None),
        }

    async def get_user_telegram_id(self, user_id: int) -> int | None:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            SELECT telegram_id
            FROM users
            WHERE id = $1
            LIMIT 1
            """,
            user_id,
        )
        if not row:
            return None
        value = row["telegram_id"]
        return int(value) if value is not None else None

    async def get_user_by_client_code(self, client_code: str) -> dict[str, Any] | None:
        assert self.pool is not None
        normalized = client_code.strip().upper()
        if not normalized:
            return None
        try:
            row = await self.pool.fetchrow(
                """
                SELECT *
                FROM users
                WHERE UPPER(client_code) = $1
                LIMIT 1
                """,
                normalized,
            )
        except asyncpg.UndefinedColumnError:
            return None
        return dict(row) if row else None

    async def has_any_subscription(self, user_id: int) -> bool:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            SELECT 1
            FROM subscriptions
            WHERE user_id = $1
            LIMIT 1
            """,
            user_id,
        )
        return row is not None

    async def get_latest_subscription(self, user_id: int) -> dict[str, Any] | None:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            SELECT *
            FROM subscriptions
            WHERE user_id = $1
            ORDER BY expires_at DESC, id DESC
            LIMIT 1
            """,
            user_id,
        )
        return dict(row) if row else None

    async def list_active_subscriptions(self) -> list[dict[str, Any]]:
        assert self.pool is not None
        rows = await self.pool.fetch(
            """
            SELECT
                id,
                user_id,
                inbound_id,
                client_uuid,
                client_email,
                expires_at,
                assigned_node_id,
                current_node_id,
                desired_node_id,
                alias_fqdn,
                assignment_state,
                compatibility_pool,
                feed_token,
                vless_url
            FROM subscriptions
            WHERE is_active = TRUE
              AND expires_at > NOW()
            ORDER BY id
            """
        )
        return [dict(r) for r in rows]

    async def list_subscription_client_identities(self) -> list[dict[str, Any]]:
        assert self.pool is not None
        rows = await self.pool.fetch(
            """
            SELECT id, client_uuid, client_email
            FROM subscriptions
            ORDER BY id
            """
        )
        return [dict(r) for r in rows]

    async def get_subscription_by_feed_token(self, feed_token: str) -> dict[str, Any] | None:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            SELECT
                s.*,
                n.name AS assigned_node_name,
                n.backend_host AS assigned_backend_host,
                n.backend_port AS assigned_backend_port
            FROM subscriptions s
            LEFT JOIN vpn_nodes n ON n.id = COALESCE(s.current_node_id, s.assigned_node_id)
            WHERE s.feed_token = $1
            LIMIT 1
            """,
            str(feed_token).strip(),
        )
        return dict(row) if row else None

    async def get_subscription_by_id(self, subscription_id: int) -> dict[str, Any] | None:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            SELECT *
            FROM subscriptions
            WHERE id = $1
            LIMIT 1
            """,
            int(subscription_id),
        )
        return dict(row) if row else None

    async def list_unassigned_active_subscriptions(self, limit: int = 500) -> list[dict[str, Any]]:
        assert self.pool is not None
        rows = await self.pool.fetch(
            """
            SELECT *
            FROM subscriptions
            WHERE is_active = TRUE
              AND expires_at > NOW()
              AND COALESCE(current_node_id, assigned_node_id) IS NULL
            ORDER BY created_at ASC, id ASC
            LIMIT $1
            """,
            max(1, int(limit)),
        )
        return [dict(r) for r in rows]

    async def list_subscriptions_missing_alias(self, limit: int = 500) -> list[dict[str, Any]]:
        assert self.pool is not None
        rows = await self.pool.fetch(
            """
            SELECT *
            FROM subscriptions
            WHERE is_active = TRUE
              AND expires_at > NOW()
              AND COALESCE(alias_fqdn, '') = ''
            ORDER BY created_at ASC, id ASC
            LIMIT $1
            """,
            max(1, int(limit)),
        )
        return [dict(r) for r in rows]

    async def list_subscriptions_by_assignment_state(self, states: list[str], limit: int = 500) -> list[dict[str, Any]]:
        assert self.pool is not None
        normalized = [str(state).strip() for state in states if str(state).strip()]
        if not normalized:
            return []
        rows = await self.pool.fetch(
            """
            SELECT *
            FROM subscriptions
            WHERE assignment_state = ANY($1::text[])
            ORDER BY COALESCE(planned_at, created_at) ASC, id ASC
            LIMIT $2
            """,
            normalized,
            max(1, int(limit)),
        )
        return [dict(r) for r in rows]

    async def get_active_vpn_nodes(self, lb_only: bool = False) -> list[dict[str, Any]]:
        assert self.pool is not None
        where = "WHERE is_active = TRUE"
        if lb_only:
            where += " AND lb_enabled = TRUE"
        try:
            rows = await self.pool.fetch(
                f"""
                SELECT *
                FROM vpn_nodes
                {where}
                ORDER BY id
                """
            )
        except (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError):
            return []
        return [dict(r) for r in rows]

    async def get_ready_lb_vpn_nodes(self) -> list[dict[str, Any]]:
        assert self.pool is not None
        try:
            rows = await self.pool.fetch(
                """
                SELECT *
                FROM vpn_nodes
                WHERE is_active = TRUE
                  AND lb_enabled = TRUE
                  AND COALESCE(needs_backfill, FALSE) = FALSE
                ORDER BY id
                """
            )
        except (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError):
            return []
        return [dict(r) for r in rows]

    async def list_node_assignment_metrics(self) -> list[dict[str, Any]]:
        assert self.pool is not None
        try:
            rows = await self.pool.fetch(
                """
                WITH active_subs AS (
                    SELECT
                        COALESCE(current_node_id, assigned_node_id) AS node_id,
                        COUNT(*) FILTER (
                            WHERE is_active = TRUE
                              AND expires_at > NOW()
                              AND revoked_at IS NULL
                        ) AS active_assigned_subscriptions
                    FROM subscriptions
                    WHERE COALESCE(current_node_id, assigned_node_id) IS NOT NULL
                    GROUP BY COALESCE(current_node_id, assigned_node_id)
                ),
                latest_snapshots AS (
                    SELECT DISTINCT ON (node_id)
                        node_id,
                        observed_at,
                        assigned_active_subscriptions,
                        observed_enabled_clients,
                        total_traffic_bytes,
                        peak_concurrency,
                        probe_latency_ms,
                        health_ok,
                        health_error,
                        score
                    FROM vpn_node_load_snapshots
                    ORDER BY node_id, observed_at DESC
                ),
                weekly_moves AS (
                    SELECT
                        to_node_id AS node_id,
                        COUNT(*) AS moves_in_week
                    FROM vpn_rebalance_decisions
                    WHERE decided_at >= (NOW() - INTERVAL '7 days')
                      AND to_node_id IS NOT NULL
                    GROUP BY to_node_id
                )
                SELECT
                    n.*,
                    COALESCE(a.active_assigned_subscriptions, 0) AS active_assigned_subscriptions,
                    COALESCE(s.observed_enabled_clients, 0) AS observed_enabled_clients,
                    COALESCE(s.total_traffic_bytes, 0) AS total_traffic_bytes,
                    s.peak_concurrency,
                    s.probe_latency_ms,
                    s.observed_at AS last_snapshot_at,
                    COALESCE(w.moves_in_week, 0) AS moves_in_week,
                    s.score AS last_snapshot_score
                FROM vpn_nodes n
                LEFT JOIN active_subs a ON a.node_id = n.id
                LEFT JOIN latest_snapshots s ON s.node_id = n.id
                LEFT JOIN weekly_moves w ON w.node_id = n.id
                ORDER BY n.id
                """
            )
        except (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError):
            return []
        return [dict(r) for r in rows]

    async def get_cluster_sync_nodes(self) -> list[dict[str, Any]]:
        assert self.pool is not None
        try:
            rows = await self.pool.fetch(
                """
                SELECT *
                FROM vpn_nodes
                WHERE is_active = TRUE
                  AND (lb_enabled = TRUE OR COALESCE(needs_backfill, FALSE) = TRUE)
                ORDER BY id
                """
            )
        except (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError):
            return []
        return [dict(r) for r in rows]

    async def get_vpn_node(self, node_id: int) -> dict[str, Any] | None:
        assert self.pool is not None
        try:
            row = await self.pool.fetchrow(
                """
                SELECT *
                FROM vpn_nodes
                WHERE id = $1
                LIMIT 1
                """,
                node_id,
            )
        except (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError):
            return None
        return dict(row) if row else None

    async def get_subscription_assigned_node(self, subscription_id: int) -> dict[str, Any] | None:
        assert self.pool is not None
        try:
            row = await self.pool.fetchrow(
                """
                SELECT n.*
                FROM subscriptions s
                JOIN vpn_nodes n ON n.id = COALESCE(s.current_node_id, s.assigned_node_id)
                WHERE s.id = $1
                LIMIT 1
                """,
                subscription_id,
            )
        except (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError):
            return None
        return dict(row) if row else None

    async def mark_node_health(
        self,
        node_id: int,
        ok: bool,
        error: str | None = None,
        reality_public_key: str | None = None,
        reality_short_id: str | None = None,
        reality_sni: str | None = None,
        reality_fingerprint: str | None = None,
    ) -> bool:
        assert self.pool is not None
        try:
            row = await self.pool.fetchrow(
                """
                UPDATE vpn_nodes
                SET last_health_at = NOW(),
                    last_health_ok = $2,
                    last_health_error = $3,
                    last_reality_public_key = $4,
                    last_reality_short_id = $5,
                    last_reality_sni = $6,
                    last_reality_fingerprint = $7,
                    updated_at = NOW()
                WHERE id = $1
                RETURNING id
                """,
                node_id,
                bool(ok),
                error,
                reality_public_key,
                reality_short_id,
                reality_sni,
                reality_fingerprint,
            )
        except asyncpg.UndefinedColumnError:
            row = await self.pool.fetchrow(
                """
                UPDATE vpn_nodes
                SET last_health_at = NOW(),
                    last_health_ok = $2,
                    last_health_error = $3
                WHERE id = $1
                RETURNING id
                """,
                node_id,
                bool(ok),
                error,
            )
        except asyncpg.UndefinedTableError:
            return False
        return row is not None

    async def list_subscriptions_needing_sync(self, node_id: int, limit: int = 200) -> list[dict[str, Any]]:
        assert self.pool is not None
        safe_limit = max(1, int(limit))
        try:
            rows = await self.pool.fetch(
                """
                WITH tracked AS (
                    SELECT DISTINCT subscription_id
                    FROM vpn_node_clients
                    WHERE node_id = $1
                ),
                candidates AS (
                    SELECT s.*
                    FROM subscriptions s
                    WHERE COALESCE(s.current_node_id, s.assigned_node_id) = $1
                       OR s.desired_node_id = $1
                    UNION
                    SELECT s.*
                    FROM subscriptions s
                    JOIN tracked t ON t.subscription_id = s.id
                )
                SELECT
                    c.id AS subscription_id,
                    c.user_id,
                    c.inbound_id,
                    c.client_uuid,
                    c.client_email,
                    c.xui_sub_id,
                    c.expires_at,
                    c.is_active,
                    c.revoked_at,
                    c.assigned_node_id,
                    c.current_node_id,
                    c.desired_node_id,
                    c.assignment_state,
                    COALESCE(
                        vnc.desired_enabled,
                        (
                            c.is_active = TRUE
                            AND c.expires_at > NOW()
                            AND c.revoked_at IS NULL
                            AND (
                                COALESCE(c.current_node_id, c.assigned_node_id) = $1
                                OR (
                                    c.desired_node_id = $1
                                    AND COALESCE(c.assignment_state, 'steady') IN ('planned', 'presync', 'cutover', 'cleanup', 'rollback')
                                )
                            )
                        )
                    ) AS desired_enabled,
                    COALESCE(vnc.desired_expires_at, c.expires_at) AS desired_expires_at,
                    vnc.observed_enabled,
                    vnc.observed_expires_at,
                    COALESCE(vnc.sync_state, 'pending') AS sync_state,
                    vnc.last_synced_at,
                    vnc.last_error
                FROM candidates c
                LEFT JOIN vpn_node_clients vnc
                  ON vnc.subscription_id = c.id
                 AND vnc.node_id = $1
                WHERE
                    vnc.id IS NULL
                    OR vnc.sync_state <> 'ok'
                    OR vnc.desired_enabled IS DISTINCT FROM (
                        c.is_active = TRUE
                        AND c.expires_at > NOW()
                        AND c.revoked_at IS NULL
                        AND (
                            COALESCE(c.current_node_id, c.assigned_node_id) = $1
                            OR (
                                c.desired_node_id = $1
                                AND COALESCE(c.assignment_state, 'steady') IN ('planned', 'presync', 'cutover', 'cleanup', 'rollback')
                            )
                        )
                    )
                    OR vnc.desired_expires_at IS DISTINCT FROM c.expires_at
                ORDER BY COALESCE(vnc.last_synced_at, TO_TIMESTAMP(0)) ASC, c.id ASC
                LIMIT $2
                """,
                node_id,
                safe_limit,
            )
        except asyncpg.UndefinedColumnError:
            try:
                rows = await self.pool.fetch(
                    """
                    SELECT
                        s.id AS subscription_id,
                        s.user_id,
                        s.inbound_id,
                        s.client_uuid,
                        s.client_email,
                        s.expires_at,
                        s.is_active,
                        (s.is_active = TRUE AND s.expires_at > NOW()) AS desired_enabled,
                        s.expires_at AS desired_expires_at,
                        COALESCE(vnc.sync_state, 'pending') AS sync_state,
                        vnc.last_synced_at,
                        vnc.last_error
                    FROM subscriptions s
                    LEFT JOIN vpn_node_clients vnc
                      ON vnc.subscription_id = s.id
                     AND vnc.node_id = $1
                    WHERE
                        vnc.id IS NULL
                        OR vnc.sync_state <> 'ok'
                        OR vnc.desired_enabled IS DISTINCT FROM (s.is_active = TRUE AND s.expires_at > NOW())
                        OR vnc.desired_expires_at IS DISTINCT FROM s.expires_at
                    ORDER BY COALESCE(vnc.last_synced_at, TO_TIMESTAMP(0)) ASC, s.id ASC
                    LIMIT $2
                    """,
                    node_id,
                    safe_limit,
                )
            except (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError):
                return []
        except asyncpg.UndefinedTableError:
            return []
        return [dict(r) for r in rows]

    async def upsert_vpn_node_client_state(
        self,
        node_id: int,
        subscription_id: int,
        client_uuid: str,
        client_email: str,
        desired_enabled: bool,
        desired_expires_at: datetime,
        observed_enabled: bool | None,
        observed_expires_at: datetime | None,
        sync_state: str,
        last_error: str | None = None,
        xui_sub_id: str | None = None,
    ) -> dict[str, Any] | None:
        assert self.pool is not None
        try:
            row = await self.pool.fetchrow(
                """
                INSERT INTO vpn_node_clients (
                    node_id,
                    subscription_id,
                    client_uuid,
                    client_email,
                    xui_sub_id,
                    desired_enabled,
                    desired_expires_at,
                    observed_enabled,
                    observed_expires_at,
                    sync_state,
                    last_synced_at,
                    last_error,
                    updated_at
                )
                VALUES ($1, $2, $3::uuid, $4, $5, $6, $7, $8, $9, $10, NOW(), $11, NOW())
                ON CONFLICT (node_id, subscription_id)
                DO UPDATE SET
                    client_uuid = EXCLUDED.client_uuid,
                    client_email = EXCLUDED.client_email,
                    xui_sub_id = EXCLUDED.xui_sub_id,
                    desired_enabled = EXCLUDED.desired_enabled,
                    desired_expires_at = EXCLUDED.desired_expires_at,
                    observed_enabled = EXCLUDED.observed_enabled,
                    observed_expires_at = EXCLUDED.observed_expires_at,
                    sync_state = EXCLUDED.sync_state,
                    last_synced_at = NOW(),
                    last_error = EXCLUDED.last_error,
                    updated_at = NOW()
                RETURNING *
                """,
                node_id,
                subscription_id,
                client_uuid,
                client_email,
                xui_sub_id,
                bool(desired_enabled),
                desired_expires_at,
                observed_enabled,
                observed_expires_at,
                sync_state,
                last_error,
            )
        except asyncpg.UndefinedColumnError:
            try:
                row = await self.pool.fetchrow(
                    """
                    INSERT INTO vpn_node_clients (
                        node_id,
                        subscription_id,
                        client_uuid,
                        client_email,
                        desired_enabled,
                        desired_expires_at,
                        observed_enabled,
                        observed_expires_at,
                        sync_state,
                        last_synced_at,
                        last_error
                    )
                    VALUES ($1, $2, $3::uuid, $4, $5, $6, $7, $8, $9, NOW(), $10)
                    ON CONFLICT (node_id, subscription_id)
                    DO UPDATE SET
                        client_uuid = EXCLUDED.client_uuid,
                        client_email = EXCLUDED.client_email,
                        desired_enabled = EXCLUDED.desired_enabled,
                        desired_expires_at = EXCLUDED.desired_expires_at,
                        observed_enabled = EXCLUDED.observed_enabled,
                        observed_expires_at = EXCLUDED.observed_expires_at,
                        sync_state = EXCLUDED.sync_state,
                        last_synced_at = NOW(),
                        last_error = EXCLUDED.last_error
                    RETURNING *
                    """,
                    node_id,
                    subscription_id,
                    client_uuid,
                    client_email,
                    bool(desired_enabled),
                    desired_expires_at,
                    observed_enabled,
                    observed_expires_at,
                    sync_state,
                    last_error,
                )
            except (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError):
                return None
        except asyncpg.UndefinedTableError:
            return None
        return dict(row) if row else None

    async def mark_node_backfill_requested(self, node_id: int) -> bool:
        assert self.pool is not None
        try:
            row = await self.pool.fetchrow(
                """
                UPDATE vpn_nodes
                SET needs_backfill = TRUE,
                    backfill_requested_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                RETURNING id
                """,
                node_id,
            )
        except asyncpg.UndefinedColumnError:
            row = await self.pool.fetchrow(
                """
                UPDATE vpn_nodes
                SET needs_backfill = TRUE
                WHERE id = $1
                RETURNING id
                """,
                node_id,
            )
        except asyncpg.UndefinedTableError:
            return False
        return row is not None

    async def mark_node_backfill_completed(self, node_id: int) -> bool:
        assert self.pool is not None
        try:
            row = await self.pool.fetchrow(
                """
                UPDATE vpn_nodes
                SET needs_backfill = FALSE,
                    last_backfill_at = NOW(),
                    last_backfill_error = NULL,
                    updated_at = NOW()
                WHERE id = $1
                RETURNING id
                """,
                node_id,
            )
        except asyncpg.UndefinedColumnError:
            row = await self.pool.fetchrow(
                """
                UPDATE vpn_nodes
                SET needs_backfill = FALSE
                WHERE id = $1
                RETURNING id
                """,
                node_id,
            )
        except asyncpg.UndefinedTableError:
            return False
        return row is not None

    async def mark_node_backfill_error(self, node_id: int, error: str) -> bool:
        assert self.pool is not None
        try:
            row = await self.pool.fetchrow(
                """
                UPDATE vpn_nodes
                SET last_backfill_error = $2,
                    updated_at = NOW()
                WHERE id = $1
                RETURNING id
                """,
                node_id,
                error,
            )
        except asyncpg.UndefinedColumnError:
            return False
        except asyncpg.UndefinedTableError:
            return False
        return row is not None

    async def get_latest_payment_method(self, user_id: int) -> str | None:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            SELECT payment_method, currency
            FROM orders
            WHERE user_id = $1
              AND status IN ('paid', 'activating', 'activated')
            ORDER BY paid_at DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            user_id,
        )
        if not row:
            return None
        payment_method = row["payment_method"]
        currency = row["currency"]
        if payment_method:
            return str(payment_method)
        if currency and str(currency).upper() == "XTR":
            return "stars"
        return None

    async def create_subscription(
        self,
        user_id: int,
        inbound_id: int,
        client_uuid: str,
        client_email: str,
        vless_url: str,
        expires_at: datetime,
        xui_sub_id: str | None = None,
        assigned_node_id: int | None = None,
        assignment_source: str = "new",
        migration_state: str = "ready",
        feed_token: str | None = None,
        alias_fqdn: str | None = None,
        current_node_id: int | None = None,
        desired_node_id: int | None = None,
        assignment_state: str = "steady",
        ttl_seconds: int = 300,
        overlap_until: datetime | None = None,
        dns_provider: str | None = None,
        dns_record_id: str | None = None,
        last_dns_change_id: str | None = None,
        compatibility_pool: str | None = None,
        planned_at: datetime | None = None,
        presynced_at: datetime | None = None,
        cutover_at: datetime | None = None,
    ) -> int:
        assert self.pool is not None
        resolved_feed_token = str(feed_token or _new_feed_token())
        try:
            row = await self.pool.fetchrow(
                """
                INSERT INTO subscriptions (
                    user_id,
                    inbound_id,
                    client_uuid,
                    client_email,
                    xui_sub_id,
                    assigned_node_id,
                    current_node_id,
                    desired_node_id,
                    alias_fqdn,
                    assignment_source,
                    assigned_at,
                    migration_state,
                    assignment_state,
                    ttl_seconds,
                    overlap_until,
                    dns_provider,
                    dns_record_id,
                    last_dns_change_id,
                    compatibility_pool,
                    planned_at,
                    presynced_at,
                    cutover_at,
                    feed_token,
                    vless_url,
                    expires_at,
                    is_active
                )
                VALUES ($1, $2, $3::uuid, $4, $5, $6, $7, $8, $9, $10, NOW(), $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, TRUE)
                RETURNING id
                """,
                user_id,
                inbound_id,
                client_uuid,
                client_email,
                xui_sub_id,
                assigned_node_id,
                current_node_id,
                desired_node_id,
                alias_fqdn,
                assignment_source,
                migration_state,
                assignment_state,
                int(ttl_seconds),
                overlap_until,
                dns_provider,
                dns_record_id,
                last_dns_change_id,
                compatibility_pool,
                planned_at,
                presynced_at,
                cutover_at,
                resolved_feed_token,
                vless_url,
                expires_at,
            )
        except asyncpg.UndefinedColumnError:
            row = await self.pool.fetchrow(
                """
                INSERT INTO subscriptions (user_id, inbound_id, client_uuid, client_email, vless_url, expires_at, is_active)
                VALUES ($1, $2, $3::uuid, $4, $5, $6, TRUE)
                RETURNING id
                """,
                user_id,
                inbound_id,
                client_uuid,
                client_email,
                vless_url,
                expires_at,
            )
        return int(row["id"])

    async def extend_subscription(
        self,
        subscription_id: int,
        new_expiry: datetime,
        vless_url: str,
        *,
        assigned_node_id: int | None = None,
        assignment_source: str | None = None,
        migration_state: str | None = None,
        alias_fqdn: str | None = None,
        current_node_id: int | None = None,
        desired_node_id: int | None = None,
        assignment_state: str | None = None,
        ttl_seconds: int | None = None,
        overlap_until: datetime | None = None,
        dns_provider: str | None = None,
        dns_record_id: str | None = None,
        last_dns_change_id: str | None = None,
        compatibility_pool: str | None = None,
        planned_at: datetime | None = None,
        presynced_at: datetime | None = None,
        cutover_at: datetime | None = None,
    ) -> None:
        assert self.pool is not None
        try:
            await self.pool.execute(
                """
                UPDATE subscriptions
                SET expires_at = $2,
                    vless_url = $3,
                    is_active = TRUE,
                    assigned_node_id = COALESCE($4, assigned_node_id),
                    assignment_source = COALESCE($5, assignment_source),
                    assigned_at = CASE WHEN $4 IS NOT NULL THEN NOW() ELSE assigned_at END,
                    migration_state = COALESCE($6, migration_state),
                    alias_fqdn = COALESCE($7, alias_fqdn),
                    current_node_id = COALESCE($8, current_node_id),
                    desired_node_id = COALESCE($9, desired_node_id),
                    assignment_state = COALESCE($10, assignment_state),
                    ttl_seconds = COALESCE($11, ttl_seconds),
                    overlap_until = COALESCE($12, overlap_until),
                    dns_provider = COALESCE($13, dns_provider),
                    dns_record_id = COALESCE($14, dns_record_id),
                    last_dns_change_id = COALESCE($15, last_dns_change_id),
                    compatibility_pool = COALESCE($16, compatibility_pool),
                    planned_at = COALESCE($17, planned_at),
                    presynced_at = COALESCE($18, presynced_at),
                    cutover_at = COALESCE($19, cutover_at),
                    updated_at = NOW()
                WHERE id = $1
                """,
                subscription_id,
                new_expiry,
                vless_url,
                assigned_node_id,
                assignment_source,
                migration_state,
                alias_fqdn,
                current_node_id,
                desired_node_id,
                assignment_state,
                ttl_seconds,
                overlap_until,
                dns_provider,
                dns_record_id,
                last_dns_change_id,
                compatibility_pool,
                planned_at,
                presynced_at,
                cutover_at,
            )
        except asyncpg.UndefinedColumnError:
            await self.pool.execute(
                """
                UPDATE subscriptions
                SET expires_at = $2, vless_url = $3, is_active = TRUE, updated_at = NOW()
                WHERE id = $1
                """,
                subscription_id,
                new_expiry,
                vless_url,
            )

    async def update_subscription_xui_sub_id(self, subscription_id: int, xui_sub_id: str | None) -> None:
        assert self.pool is not None
        try:
            await self.pool.execute(
                """
                UPDATE subscriptions
                SET xui_sub_id = $2, updated_at = NOW()
                WHERE id = $1
                """,
                subscription_id,
                xui_sub_id,
            )
        except asyncpg.UndefinedColumnError:
            # Early rollout compatibility.
            return

    async def update_subscription_assignment(
        self,
        subscription_id: int,
        *,
        assigned_node_id: int,
        vless_url: str,
        assignment_source: str,
        migration_state: str = "ready",
        mark_rebalanced: bool = False,
        alias_fqdn: str | None = None,
        current_node_id: int | None = None,
        desired_node_id: int | None = None,
        assignment_state: str | None = None,
        ttl_seconds: int | None = None,
        overlap_until: datetime | None = None,
        dns_provider: str | None = None,
        dns_record_id: str | None = None,
        last_dns_change_id: str | None = None,
        compatibility_pool: str | None = None,
        planned_at: datetime | None = None,
        presynced_at: datetime | None = None,
        cutover_at: datetime | None = None,
    ) -> None:
        assert self.pool is not None
        try:
            await self.pool.execute(
                """
                UPDATE subscriptions
                SET assigned_node_id = $2,
                    vless_url = $3,
                    assignment_source = $4,
                    assigned_at = NOW(),
                    last_rebalanced_at = CASE WHEN $6 THEN NOW() ELSE last_rebalanced_at END,
                    migration_state = $5,
                    alias_fqdn = COALESCE($7, alias_fqdn),
                    current_node_id = COALESCE($8, current_node_id),
                    desired_node_id = COALESCE($9, desired_node_id),
                    assignment_state = COALESCE($10, assignment_state),
                    ttl_seconds = COALESCE($11, ttl_seconds),
                    overlap_until = COALESCE($12, overlap_until),
                    dns_provider = COALESCE($13, dns_provider),
                    dns_record_id = COALESCE($14, dns_record_id),
                    last_dns_change_id = COALESCE($15, last_dns_change_id),
                    compatibility_pool = COALESCE($16, compatibility_pool),
                    planned_at = COALESCE($17, planned_at),
                    presynced_at = COALESCE($18, presynced_at),
                    cutover_at = COALESCE($19, cutover_at),
                    updated_at = NOW()
                WHERE id = $1
                """,
                subscription_id,
                assigned_node_id,
                vless_url,
                assignment_source,
                migration_state,
                bool(mark_rebalanced),
                alias_fqdn,
                current_node_id,
                desired_node_id,
                assignment_state,
                ttl_seconds,
                overlap_until,
                dns_provider,
                dns_record_id,
                last_dns_change_id,
                compatibility_pool,
                planned_at,
                presynced_at,
                cutover_at,
            )
        except asyncpg.UndefinedColumnError:
            await self.pool.execute(
                """
                UPDATE subscriptions
                SET vless_url = $2,
                    updated_at = NOW()
                WHERE id = $1
                """,
                subscription_id,
                vless_url,
            )

    async def ensure_subscription_feed_token(self, subscription_id: int) -> str | None:
        assert self.pool is not None
        try:
            token = _new_feed_token()
            row = await self.pool.fetchrow(
                """
                UPDATE subscriptions
                SET feed_token = COALESCE(NULLIF(feed_token, ''), $2),
                    updated_at = NOW()
                WHERE id = $1
                RETURNING feed_token
                """,
                subscription_id,
                token,
            )
        except asyncpg.UndefinedColumnError:
            return None
        if not row:
            return None
        value = row["feed_token"]
        return str(value) if value else None

    async def record_node_load_snapshot(
        self,
        *,
        node_id: int,
        assigned_active_subscriptions: int,
        observed_enabled_clients: int,
        total_traffic_bytes: int = 0,
        peak_concurrency: int | None = None,
        probe_latency_ms: int | None = None,
        health_ok: bool,
        health_error: str | None = None,
        score: float | None = None,
        meta: dict[str, Any] | None = None,
    ) -> bool:
        assert self.pool is not None
        try:
            await self.pool.execute(
                """
                INSERT INTO vpn_node_load_snapshots (
                    node_id,
                    assigned_active_subscriptions,
                    observed_enabled_clients,
                    total_traffic_bytes,
                    peak_concurrency,
                    probe_latency_ms,
                    health_ok,
                    health_error,
                    score,
                    meta
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
                """,
                node_id,
                int(assigned_active_subscriptions),
                int(observed_enabled_clients),
                int(total_traffic_bytes),
                peak_concurrency,
                probe_latency_ms,
                bool(health_ok),
                health_error,
                score,
                json.dumps(meta or {}, ensure_ascii=False),
            )
        except (asyncpg.UndefinedColumnError, asyncpg.UndefinedTableError):
            return False
        return True

    async def record_rebalance_decision(
        self,
        *,
        subscription_id: int,
        from_node_id: int | None,
        to_node_id: int | None,
        decision_kind: str,
        score_before: float | None = None,
        score_after: float | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
        dns_change_id: str | None = None,
        rollback_reason: str | None = None,
    ) -> bool:
        assert self.pool is not None
        try:
            await self.pool.execute(
                """
                INSERT INTO vpn_rebalance_decisions (
                    subscription_id,
                    from_node_id,
                    to_node_id,
                    decision_kind,
                    score_before,
                    score_after,
                    reason,
                    details,
                    dns_change_id,
                    rollback_reason
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10)
                """,
                subscription_id,
                from_node_id,
                to_node_id,
                decision_kind,
                score_before,
                score_after,
                reason,
                json.dumps(details or {}, ensure_ascii=False),
                dns_change_id,
                rollback_reason,
            )
        except (asyncpg.UndefinedColumnError, asyncpg.UndefinedTableError):
            return False
        return True

    async def list_rebalance_candidates(self, from_node_id: int, cooldown_hours: int, limit: int) -> list[dict[str, Any]]:
        assert self.pool is not None
        try:
            rows = await self.pool.fetch(
                """
                SELECT *
                FROM subscriptions
                WHERE COALESCE(current_node_id, assigned_node_id) = $1
                  AND is_active = TRUE
                  AND expires_at > NOW()
                  AND revoked_at IS NULL
                  AND (
                        last_rebalanced_at IS NULL
                     OR last_rebalanced_at < (NOW() - make_interval(hours => $2))
                  )
                ORDER BY COALESCE(last_rebalanced_at, TO_TIMESTAMP(0)) ASC, expires_at DESC, id ASC
                LIMIT $3
                """,
                from_node_id,
                max(0, int(cooldown_hours)),
                max(1, int(limit)),
            )
        except (asyncpg.UndefinedColumnError, asyncpg.UndefinedTableError):
            return []
        return [dict(r) for r in rows]

    async def due_reminders(self) -> list[dict[str, Any]]:
        assert self.pool is not None
        now = datetime.now(timezone.utc)
        in_3_days = now + timedelta(days=3)
        in_1_day = now + timedelta(days=1)
        rows = await self.pool.fetch(
            """
            SELECT s.id, s.user_id, s.expires_at, s.display_name, u.telegram_id
            FROM subscriptions s
            JOIN users u ON u.id = s.user_id
            WHERE s.is_active = TRUE
              AND (
                   (s.expires_at BETWEEN $1 AND $2 AND NOT EXISTS (
                        SELECT 1 FROM reminder_logs r
                        WHERE r.subscription_id = s.id AND r.reminder_type = '3d'
                   ))
                OR (s.expires_at BETWEEN $3 AND $1 AND NOT EXISTS (
                        SELECT 1 FROM reminder_logs r
                        WHERE r.subscription_id = s.id AND r.reminder_type = '1d'
                   ))
                OR (s.expires_at <= $1 AND NOT EXISTS (
                        SELECT 1 FROM reminder_logs r
                        WHERE r.subscription_id = s.id AND r.reminder_type = 'expired'
                   ))
              )
            """,
            now,
            in_3_days,
            in_1_day,
        )
        return [dict(r) for r in rows]

    async def log_reminder(self, subscription_id: int, reminder_type: str) -> None:
        assert self.pool is not None
        await self.pool.execute(
            """
            INSERT INTO reminder_logs (subscription_id, reminder_type)
            VALUES ($1, $2)
            ON CONFLICT (subscription_id, reminder_type) DO NOTHING
            """,
            subscription_id,
            reminder_type,
        )

    async def create_order(self, user_id: int, amount_stars: int, payload: str) -> int:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            INSERT INTO orders (user_id, amount_stars, currency, payload, status)
            VALUES ($1, $2, 'XTR', $3, 'pending')
            RETURNING id
            """,
            user_id,
            amount_stars,
            payload,
        )
        return int(row["id"])

    async def cancel_expired_pending_orders(
        self,
        user_id: int,
        payload_prefix: str,
        max_age_seconds: int = 3600,
    ) -> int:
        assert self.pool is not None
        result = await self.pool.execute(
            """
            UPDATE orders
            SET status = 'cancelled'
            WHERE user_id = $1
              AND status = 'pending'
              AND payload LIKE ($2 || '%')
              AND created_at < (NOW() - make_interval(secs => $3))
            """,
            user_id,
            payload_prefix,
            int(max_age_seconds),
        )
        # asyncpg returns e.g. "UPDATE 3"
        updated = int(str(result).split()[-1])
        return updated

    async def get_fresh_pending_order(
        self,
        user_id: int,
        payload_prefix: str,
        max_age_seconds: int = 3600,
    ) -> dict[str, Any] | None:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            SELECT *
            FROM orders
            WHERE user_id = $1
              AND status = 'pending'
              AND payload LIKE ($2 || '%')
              AND created_at >= (NOW() - make_interval(secs => $3))
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            user_id,
            payload_prefix,
            int(max_age_seconds),
        )
        return dict(row) if row else None

    async def create_or_reuse_pending_stars_order(
        self,
        user_id: int,
        amount_stars: int,
        payload_prefix: str,
        new_payload: str,
        max_age_seconds: int = 3600,
    ) -> dict[str, Any]:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE orders
                    SET status = 'cancelled'
                    WHERE user_id = $1
                      AND status = 'pending'
                      AND payload LIKE ($2 || '%')
                      AND created_at < (NOW() - make_interval(secs => $3))
                    """,
                    user_id,
                    payload_prefix,
                    int(max_age_seconds),
                )

                existing = await conn.fetchrow(
                    """
                    SELECT *
                    FROM orders
                    WHERE user_id = $1
                      AND status = 'pending'
                      AND payload LIKE ($2 || '%')
                      AND created_at >= (NOW() - make_interval(secs => $3))
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    user_id,
                    payload_prefix,
                    int(max_age_seconds),
                )
                if existing and int(existing["amount_stars"] or 0) == int(amount_stars):
                    return dict(existing)
                if existing:
                    await conn.execute(
                        """
                        UPDATE orders
                        SET status = 'cancelled'
                        WHERE id = $1
                        """,
                        int(existing["id"]),
                    )

                created = await conn.fetchrow(
                    """
                    INSERT INTO orders (user_id, amount_stars, currency, payload, status)
                    VALUES ($1, $2, 'XTR', $3, 'pending')
                    RETURNING *
                    """,
                    user_id,
                    amount_stars,
                    new_payload,
                )
                return dict(created)

    async def get_order_by_payload(self, payload: str) -> dict[str, Any] | None:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            "SELECT * FROM orders WHERE payload = $1 LIMIT 1",
            payload,
        )
        return dict(row) if row else None

    async def is_charge_processed(self, telegram_payment_charge_id: str) -> bool:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            "SELECT 1 FROM orders WHERE telegram_payment_charge_id = $1 LIMIT 1",
            telegram_payment_charge_id,
        )
        return row is not None

    async def mark_order_paid(
        self,
        order_id: int,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str | None,
    ) -> None:
        assert self.pool is not None
        await self.pool.execute(
            """
            UPDATE orders
            SET status = 'paid',
                telegram_payment_charge_id = $2,
                provider_payment_charge_id = $3,
                paid_at = NOW()
            WHERE id = $1
            """,
            order_id,
            telegram_payment_charge_id,
            provider_payment_charge_id,
        )

    async def mark_order_paid_if_pending(
        self,
        order_id: int,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str | None,
    ) -> bool:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            UPDATE orders
            SET status = 'paid',
                telegram_payment_charge_id = $2,
                provider_payment_charge_id = $3,
                paid_at = NOW()
            WHERE id = $1
              AND status = 'pending'
            RETURNING id
            """,
            order_id,
            telegram_payment_charge_id,
            provider_payment_charge_id,
        )
        return row is not None

    async def insert_payment_event_if_new(self, provider: str, event_id: str, body: Any) -> bool:
        assert self.pool is not None
        payload = json.dumps(body, ensure_ascii=False)
        row = await self.pool.fetchrow(
            """
            INSERT INTO payment_events (provider, event_id, body)
            VALUES ($1, $2, $3::jsonb)
            ON CONFLICT (provider, event_id) DO NOTHING
            RETURNING id
            """,
            provider,
            event_id,
            payload,
        )
        return row is not None

    async def mark_payment_event_processed(self, provider: str, event_id: str) -> bool:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            UPDATE payment_events
            SET processed_at = NOW()
            WHERE provider = $1
              AND event_id = $2
            RETURNING id
            """,
            provider,
            event_id,
        )
        return row is not None

    async def get_latest_paid_order(self, user_id: int) -> dict[str, Any] | None:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            SELECT *
            FROM orders
            WHERE user_id = $1
              AND (
                    status IN ('paid', 'activating', 'activated', 'completed', 'success', 'succeeded')
                    OR paid_at IS NOT NULL
                    OR telegram_payment_charge_id IS NOT NULL
                    OR provider_payment_charge_id IS NOT NULL
                  )
            ORDER BY paid_at DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            user_id,
        )
        return dict(row) if row else None

    async def get_order_by_id(self, order_id: int) -> dict[str, Any] | None:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            SELECT *
            FROM orders
            WHERE id = $1
            LIMIT 1
            """,
            order_id,
        )
        return dict(row) if row else None

    async def claim_order_for_activation(self, order_id: int) -> dict[str, Any] | None:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            UPDATE orders
            SET status = 'activating'
            WHERE id = $1
              AND status = 'paid'
            RETURNING *
            """,
            order_id,
        )
        return dict(row) if row else None

    async def release_order_activation_claim(self, order_id: int) -> bool:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            UPDATE orders
            SET status = 'paid'
            WHERE id = $1
              AND status = 'activating'
            RETURNING id
            """,
            order_id,
        )
        return row is not None

    async def mark_order_activated(self, order_id: int) -> bool:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            UPDATE orders
            SET status = 'activated'
            WHERE id = $1
            RETURNING id
            """,
            order_id,
        )
        return row is not None

    async def mark_order_notified_if_pending(self, order_id: int) -> bool:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            UPDATE orders
            SET notified_at = NOW()
            WHERE id = $1
              AND notified_at IS NULL
            RETURNING id
            """,
            order_id,
        )
        return row is not None

    async def create_ticket(self, user_id: int | None, subject: str | None) -> int:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            INSERT INTO support_tickets (user_id, subject, status)
            VALUES ($1, $2, 'open')
            RETURNING id
            """,
            user_id,
            subject,
        )
        return int(row["id"])

    async def get_latest_open_ticket_for_user(self, user_id: int) -> dict[str, Any] | None:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            SELECT *
            FROM support_tickets
            WHERE user_id = $1
              AND status = 'open'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            user_id,
        )
        return dict(row) if row else None

    async def add_message(
        self,
        ticket_id: int,
        sender_role: str,
        message_text: str,
        sender_user_id: int | None = None,
    ) -> int:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO support_messages (ticket_id, sender_role, sender_user_id, message_text)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                    """,
                    ticket_id,
                    sender_role,
                    sender_user_id,
                    message_text,
                )
                await conn.execute(
                    """
                    UPDATE support_tickets
                    SET updated_at = NOW()
                    WHERE id = $1
                    """,
                    ticket_id,
                )
        return int(row["id"])

    async def list_open_tickets_for_admin(self, limit: int = 100) -> list[dict[str, Any]]:
        assert self.pool is not None
        try:
            rows = await self.pool.fetch(
                """
                SELECT
                    t.id,
                    t.user_id,
                    t.status,
                    t.subject,
                    t.created_at,
                    t.updated_at,
                    t.closed_at,
                    u.telegram_id,
                    u.client_code,
                    m.id AS last_message_id,
                    m.sender_role AS last_message_sender_role,
                    m.message_text AS last_message_text,
                    m.created_at AS last_message_at
                FROM support_tickets t
                LEFT JOIN users u ON u.id = t.user_id
                LEFT JOIN LATERAL (
                    SELECT sm.id, sm.sender_role, sm.message_text, sm.created_at
                    FROM support_messages sm
                    WHERE sm.ticket_id = t.id
                    ORDER BY sm.created_at DESC, sm.id DESC
                    LIMIT 1
                ) m ON TRUE
                WHERE t.status = 'open'
                ORDER BY t.updated_at DESC, t.id DESC
                LIMIT $1
                """,
                limit,
            )
        except asyncpg.UndefinedColumnError:
            rows = await self.pool.fetch(
                """
                SELECT
                    t.id,
                    t.user_id,
                    t.status,
                    t.subject,
                    t.created_at,
                    t.updated_at,
                    t.closed_at,
                    u.telegram_id,
                    NULL::TEXT AS client_code,
                    m.id AS last_message_id,
                    m.sender_role AS last_message_sender_role,
                    m.message_text AS last_message_text,
                    m.created_at AS last_message_at
                FROM support_tickets t
                LEFT JOIN users u ON u.id = t.user_id
                LEFT JOIN LATERAL (
                    SELECT sm.id, sm.sender_role, sm.message_text, sm.created_at
                    FROM support_messages sm
                    WHERE sm.ticket_id = t.id
                    ORDER BY sm.created_at DESC, sm.id DESC
                    LIMIT 1
                ) m ON TRUE
                WHERE t.status = 'open'
                ORDER BY t.updated_at DESC, t.id DESC
                LIMIT $1
                """,
                limit,
            )
        return [dict(r) for r in rows]

    async def get_ticket_for_admin(self, ticket_id: int) -> dict[str, Any] | None:
        assert self.pool is not None
        try:
            row = await self.pool.fetchrow(
                """
                SELECT
                    t.id,
                    t.user_id,
                    t.status,
                    t.subject,
                    t.created_at,
                    t.updated_at,
                    t.closed_at,
                    u.telegram_id,
                    u.client_code
                FROM support_tickets t
                LEFT JOIN users u ON u.id = t.user_id
                WHERE t.id = $1
                LIMIT 1
                """,
                ticket_id,
            )
        except asyncpg.UndefinedColumnError:
            row = await self.pool.fetchrow(
                """
                SELECT
                    t.id,
                    t.user_id,
                    t.status,
                    t.subject,
                    t.created_at,
                    t.updated_at,
                    t.closed_at,
                    u.telegram_id,
                    NULL::TEXT AS client_code
                FROM support_tickets t
                LEFT JOIN users u ON u.id = t.user_id
                WHERE t.id = $1
                LIMIT 1
                """,
                ticket_id,
            )
        return dict(row) if row else None

    async def list_ticket_messages(self, ticket_id: int, limit: int = 10) -> list[dict[str, Any]]:
        assert self.pool is not None
        rows = await self.pool.fetch(
            """
            SELECT
                m.id,
                m.ticket_id,
                m.sender_role,
                m.sender_user_id,
                m.message_text,
                m.created_at,
                u.client_code
            FROM support_messages m
            LEFT JOIN users u ON u.id = m.sender_user_id
            WHERE m.ticket_id = $1
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT $2
            """,
            ticket_id,
            max(1, limit),
        )
        return [dict(r) for r in rows]

    async def close_ticket(self, ticket_id: int) -> bool:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """
            UPDATE support_tickets
            SET status = 'closed',
                closed_at = COALESCE(closed_at, NOW()),
                updated_at = NOW()
            WHERE id = $1
              AND status <> 'closed'
            RETURNING id
            """,
            ticket_id,
        )
        return row is not None

    async def consume_telegram_link_code(self, code: str, telegram_id: int) -> str:
        assert self.pool is not None
        normalized = code.strip().upper()
        if not normalized:
            return "invalid"

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                token = await conn.fetchrow(
                    """
                    SELECT id, user_id
                    FROM cabinet_telegramlinktoken
                    WHERE code = $1
                      AND consumed_at IS NULL
                      AND expires_at > NOW()
                    ORDER BY id DESC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    normalized,
                )
                if not token:
                    exists = await conn.fetchrow(
                        "SELECT consumed_at, expires_at FROM cabinet_telegramlinktoken WHERE code = $1 ORDER BY id DESC LIMIT 1",
                        normalized,
                    )
                    if not exists:
                        return "invalid"
                    if exists["consumed_at"] is not None:
                        return "used"
                    return "expired"

                user_id = int(token["user_id"])
                placeholder_telegram_id = _site_placeholder_telegram_id_for_auth_user(user_id)
                placeholder_user = await conn.fetchrow(
                    """
                    SELECT id
                    FROM users
                    WHERE telegram_id = $1
                    LIMIT 1
                    FOR UPDATE
                    """,
                    placeholder_telegram_id,
                )
                telegram_user = await conn.fetchrow(
                    """
                    SELECT id, username, first_name
                    FROM users
                    WHERE telegram_id = $1
                    LIMIT 1
                    FOR UPDATE
                    """,
                    telegram_id,
                )

                if placeholder_user and telegram_user and int(placeholder_user["id"]) != int(telegram_user["id"]):
                    placeholder_user_id = int(placeholder_user["id"])
                    telegram_user_id = int(telegram_user["id"])
                    await conn.execute(
                        "UPDATE orders SET user_id = $1 WHERE user_id = $2",
                        placeholder_user_id,
                        telegram_user_id,
                    )
                    await conn.execute(
                        "UPDATE subscriptions SET user_id = $1 WHERE user_id = $2",
                        placeholder_user_id,
                        telegram_user_id,
                    )
                    await conn.execute(
                        "UPDATE support_tickets SET user_id = $1 WHERE user_id = $2",
                        placeholder_user_id,
                        telegram_user_id,
                    )
                    await conn.execute(
                        "UPDATE support_messages SET sender_user_id = $1 WHERE sender_user_id = $2",
                        placeholder_user_id,
                        telegram_user_id,
                    )
                    await conn.execute(
                        """
                        UPDATE users
                        SET telegram_id = $1,
                            username = COALESCE($2, username),
                            first_name = COALESCE($3, first_name)
                        WHERE id = $4
                        """,
                        telegram_id,
                        telegram_user["username"],
                        telegram_user["first_name"],
                        placeholder_user_id,
                    )
                    await conn.execute(
                        "DELETE FROM users WHERE id = $1",
                        telegram_user_id,
                    )
                elif placeholder_user:
                    await conn.execute(
                        """
                        UPDATE users
                        SET telegram_id = $1
                        WHERE id = $2
                        """,
                        telegram_id,
                        int(placeholder_user["id"]),
                    )

                await conn.execute(
                    "DELETE FROM cabinet_linkedaccount WHERE telegram_id = $1 AND user_id <> $2",
                    telegram_id,
                    user_id,
                )
                await conn.execute(
                    """
                    INSERT INTO cabinet_linkedaccount (user_id, telegram_id, created_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (user_id)
                    DO UPDATE SET telegram_id = EXCLUDED.telegram_id
                    """,
                    user_id,
                    telegram_id,
                )
                await conn.execute(
                    """
                    UPDATE cabinet_telegramlinktoken
                    SET consumed_at = NOW(),
                        consumed_telegram_id = $2
                    WHERE id = $1
                    """,
                    int(token["id"]),
                    telegram_id,
                )
        return "ok"
