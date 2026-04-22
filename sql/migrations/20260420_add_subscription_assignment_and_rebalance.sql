ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS assigned_node_id BIGINT REFERENCES vpn_nodes(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS assignment_source TEXT NOT NULL DEFAULT 'legacy',
    ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_rebalanced_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS migration_state TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS feed_token TEXT;

UPDATE subscriptions
SET feed_token = md5(id::text || ':' || client_uuid::text || ':' || COALESCE(xui_sub_id, '') || ':' || EXTRACT(EPOCH FROM NOW())::text)
WHERE feed_token IS NULL OR feed_token = '';

CREATE UNIQUE INDEX IF NOT EXISTS idx_subscriptions_feed_token
    ON subscriptions (feed_token);

CREATE INDEX IF NOT EXISTS idx_subscriptions_assigned_node_id
    ON subscriptions (assigned_node_id);

CREATE INDEX IF NOT EXISTS idx_subscriptions_assignment_state
    ON subscriptions (migration_state, assigned_node_id);

CREATE TABLE IF NOT EXISTS vpn_node_load_snapshots (
    id BIGSERIAL PRIMARY KEY,
    node_id BIGINT NOT NULL REFERENCES vpn_nodes(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_active_subscriptions INTEGER NOT NULL DEFAULT 0,
    observed_enabled_clients INTEGER NOT NULL DEFAULT 0,
    total_traffic_bytes BIGINT NOT NULL DEFAULT 0,
    peak_concurrency INTEGER,
    health_ok BOOLEAN NOT NULL DEFAULT FALSE,
    health_error TEXT,
    score NUMERIC(18,6),
    meta JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_vpn_node_load_snapshots_node_id_observed_at
    ON vpn_node_load_snapshots (node_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS vpn_rebalance_decisions (
    id BIGSERIAL PRIMARY KEY,
    subscription_id BIGINT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    from_node_id BIGINT REFERENCES vpn_nodes(id) ON DELETE SET NULL,
    to_node_id BIGINT REFERENCES vpn_nodes(id) ON DELETE SET NULL,
    decision_kind TEXT NOT NULL,
    score_before NUMERIC(18,6),
    score_after NUMERIC(18,6),
    reason TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vpn_rebalance_decisions_subscription_id
    ON vpn_rebalance_decisions (subscription_id, decided_at DESC);

CREATE INDEX IF NOT EXISTS idx_vpn_rebalance_decisions_to_node_id
    ON vpn_rebalance_decisions (to_node_id, decided_at DESC);
