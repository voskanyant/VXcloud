from __future__ import annotations

import json
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
              AND is_active = TRUE
              AND expires_at > NOW()
            ORDER BY expires_at DESC, id DESC
            LIMIT 1
            """,
            user_id,
        )
        return dict(row) if row else None

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
    ) -> int:
        assert self.pool is not None
        try:
            row = await self.pool.fetchrow(
                """
                INSERT INTO subscriptions (
                    user_id, inbound_id, client_uuid, client_email, xui_sub_id, vless_url, expires_at, is_active
                )
                VALUES ($1, $2, $3::uuid, $4, $5, $6, $7, TRUE)
                RETURNING id
                """,
                user_id,
                inbound_id,
                client_uuid,
                client_email,
                xui_sub_id,
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
