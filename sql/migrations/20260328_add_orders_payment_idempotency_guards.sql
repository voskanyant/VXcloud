-- Cleanup legacy duplicates before adding guards.
-- Keep the newest order for each non-null idempotency key; null old duplicates.
WITH ranked_idem AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY idempotency_key
            ORDER BY created_at DESC NULLS LAST, id DESC
        ) AS rn
    FROM orders
    WHERE idempotency_key IS NOT NULL
)
UPDATE orders o
SET idempotency_key = NULL
FROM ranked_idem r
WHERE o.id = r.id
  AND r.rn > 1;

-- Keep only one pending web order per user/payment method; cancel stale duplicates.
WITH ranked_pending AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, channel, payment_method
            ORDER BY created_at DESC NULLS LAST, id DESC
        ) AS rn
    FROM orders
    WHERE status = 'pending'
      AND channel = 'web'
      AND payment_method IS NOT NULL
)
UPDATE orders o
SET status = 'cancelled'
FROM ranked_pending r
WHERE o.id = r.id
  AND r.rn > 1;

-- Prevent duplicate web checkouts with the same idempotency key.
CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_idempotency_key
ON orders(idempotency_key)
WHERE idempotency_key IS NOT NULL;

-- Ensure one pending web order per user/payment method at a time.
CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_pending_web_user_method
ON orders(user_id, channel, payment_method)
WHERE status = 'pending'
  AND channel = 'web'
  AND payment_method IS NOT NULL;
