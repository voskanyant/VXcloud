CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    client_code TEXT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION set_users_client_code()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.client_code IS NULL OR NEW.client_code = '' THEN
        NEW.client_code := 'VX-' || LPAD(NEW.id::text, 6, '0');
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_set_users_client_code ON users;
CREATE TRIGGER trg_set_users_client_code
BEFORE INSERT ON users
FOR EACH ROW
EXECUTE FUNCTION set_users_client_code();

CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    inbound_id INTEGER NOT NULL,
    client_uuid UUID NOT NULL,
    client_email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL DEFAULT '',
    xui_sub_id TEXT,
    assigned_node_id BIGINT REFERENCES vpn_nodes(id) ON DELETE SET NULL,
    alias_fqdn TEXT UNIQUE,
    current_node_id BIGINT REFERENCES vpn_nodes(id) ON DELETE SET NULL,
    desired_node_id BIGINT REFERENCES vpn_nodes(id) ON DELETE SET NULL,
    assignment_source TEXT NOT NULL DEFAULT 'legacy',
    assigned_at TIMESTAMPTZ,
    last_rebalanced_at TIMESTAMPTZ,
    migration_state TEXT NOT NULL DEFAULT 'pending',
    assignment_state TEXT NOT NULL DEFAULT 'steady',
    ttl_seconds INTEGER NOT NULL DEFAULT 300,
    overlap_until TIMESTAMPTZ,
    dns_provider TEXT,
    dns_record_id TEXT,
    last_dns_change_id TEXT,
    compatibility_pool TEXT,
    planned_at TIMESTAMPTZ,
    presynced_at TIMESTAMPTZ,
    cutover_at TIMESTAMPTZ,
    feed_token TEXT UNIQUE,
    vless_url TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_expires_at ON subscriptions(expires_at);
CREATE INDEX IF NOT EXISTS idx_subscriptions_assigned_node_id ON subscriptions(assigned_node_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_assignment_state ON subscriptions(migration_state, assigned_node_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_current_node_id ON subscriptions(current_node_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_desired_node_id ON subscriptions(desired_node_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_dns_state ON subscriptions(assignment_state, current_node_id, desired_node_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_overlap_until ON subscriptions(overlap_until);

CREATE TABLE IF NOT EXISTS reminder_logs (
    id BIGSERIAL PRIMARY KEY,
    subscription_id BIGINT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    reminder_type TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (subscription_id, reminder_type)
);

CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount_stars INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'XTR',
    target_subscription_id BIGINT,
    order_kind TEXT NOT NULL DEFAULT 'renew',
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    channel TEXT,
    payment_method TEXT,
    amount_minor BIGINT,
    currency_iso TEXT,
    card_provider TEXT,
    card_payment_id TEXT,
    idempotency_key TEXT,
    payload TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    telegram_payment_charge_id TEXT UNIQUE,
    provider_payment_charge_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    paid_at TIMESTAMPTZ,
    notified_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_card_payment_id ON orders(card_payment_id);
CREATE INDEX IF NOT EXISTS idx_orders_idempotency_key ON orders(idempotency_key);

CREATE TABLE IF NOT EXISTS payment_events (
    id BIGSERIAL PRIMARY KEY,
    provider TEXT NOT NULL,
    event_id TEXT NOT NULL,
    body JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    UNIQUE (provider, event_id)
);

CREATE TABLE IF NOT EXISTS support_tickets (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'open',
    subject TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS support_messages (
    id BIGSERIAL PRIMARY KEY,
    ticket_id BIGINT NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
    sender_role TEXT NOT NULL,
    sender_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    message_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);
CREATE INDEX IF NOT EXISTS idx_support_tickets_user_id ON support_tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_support_tickets_updated_at ON support_tickets(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_support_messages_ticket_id ON support_messages(ticket_id);
CREATE INDEX IF NOT EXISTS idx_support_messages_created_at ON support_messages(created_at DESC);

CREATE TABLE IF NOT EXISTS vpn_nodes (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    region TEXT,
    xui_base_url TEXT NOT NULL,
    xui_username TEXT NOT NULL,
    xui_password TEXT NOT NULL,
    xui_inbound_id INTEGER NOT NULL,
    backend_host TEXT NOT NULL,
    backend_port INTEGER NOT NULL,
    public_ip TEXT,
    node_fqdn TEXT,
    compatibility_pool TEXT NOT NULL DEFAULT 'default',
    xray_api_host TEXT,
    xray_api_port INTEGER,
    xray_metrics_host TEXT,
    xray_metrics_port INTEGER,
    bandwidth_capacity_mbps INTEGER NOT NULL DEFAULT 1000,
    connection_capacity INTEGER NOT NULL DEFAULT 10000,
    backend_weight INTEGER NOT NULL DEFAULT 100,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    lb_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    needs_backfill BOOLEAN NOT NULL DEFAULT FALSE,
    backfill_requested_at TIMESTAMPTZ,
    last_backfill_at TIMESTAMPTZ,
    last_backfill_error TEXT,
    last_health_at TIMESTAMPTZ,
    last_health_ok BOOLEAN,
    last_health_error TEXT,
    last_reality_public_key TEXT,
    last_reality_short_id TEXT,
    last_reality_sni TEXT,
    last_reality_fingerprint TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vpn_nodes_lb_enabled_is_active
    ON vpn_nodes (lb_enabled, is_active);

CREATE TABLE IF NOT EXISTS vpn_node_clients (
    id BIGSERIAL PRIMARY KEY,
    node_id BIGINT NOT NULL REFERENCES vpn_nodes(id) ON DELETE CASCADE,
    subscription_id BIGINT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    client_uuid UUID NOT NULL,
    client_email TEXT NOT NULL,
    xui_sub_id TEXT,
    desired_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    desired_expires_at TIMESTAMPTZ NOT NULL,
    observed_enabled BOOLEAN,
    observed_expires_at TIMESTAMPTZ,
    sync_state TEXT NOT NULL DEFAULT 'pending',
    last_synced_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (node_id, subscription_id)
);

CREATE INDEX IF NOT EXISTS idx_vpn_node_clients_node_id_sync_state
    ON vpn_node_clients (node_id, sync_state);

CREATE INDEX IF NOT EXISTS idx_vpn_node_clients_subscription_id
    ON vpn_node_clients (subscription_id);

CREATE TABLE IF NOT EXISTS vpn_node_load_snapshots (
    id BIGSERIAL PRIMARY KEY,
    node_id BIGINT NOT NULL REFERENCES vpn_nodes(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_active_subscriptions INTEGER NOT NULL DEFAULT 0,
    observed_enabled_clients INTEGER NOT NULL DEFAULT 0,
    total_traffic_bytes BIGINT NOT NULL DEFAULT 0,
    peak_concurrency INTEGER,
    probe_latency_ms INTEGER,
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
    dns_change_id TEXT,
    rollback_reason TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vpn_rebalance_decisions_subscription_id
    ON vpn_rebalance_decisions (subscription_id, decided_at DESC);

CREATE INDEX IF NOT EXISTS idx_vpn_rebalance_decisions_to_node_id
    ON vpn_rebalance_decisions (to_node_id, decided_at DESC);
