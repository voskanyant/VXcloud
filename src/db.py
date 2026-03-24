from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg


class DB:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=10)

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()

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
            ORDER BY id DESC
            LIMIT 1
            """,
            user_id,
        )
        return dict(row) if row else None

    async def create_subscription(
        self,
        user_id: int,
        inbound_id: int,
        client_uuid: str,
        client_email: str,
        vless_url: str,
        expires_at: datetime,
    ) -> int:
        assert self.pool is not None
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

    async def extend_subscription(self, subscription_id: int, new_expiry: datetime, vless_url: str) -> None:
        assert self.pool is not None
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

    async def due_reminders(self) -> list[dict[str, Any]]:
        assert self.pool is not None
        now = datetime.now(timezone.utc)
        in_3_days = now + timedelta(days=3)
        in_1_day = now + timedelta(days=1)
        rows = await self.pool.fetch(
            """
            SELECT s.id, s.user_id, s.expires_at, u.telegram_id
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
