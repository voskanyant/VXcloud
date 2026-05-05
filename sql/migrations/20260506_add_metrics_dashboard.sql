ALTER TABLE vpn_nodes
    ADD COLUMN IF NOT EXISTS metrics_agent_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS metrics_agent_url TEXT,
    ADD COLUMN IF NOT EXISTS metrics_agent_token TEXT;

CREATE TABLE IF NOT EXISTS vpn_node_metric_samples (
    id BIGSERIAL PRIMARY KEY,
    node_id BIGINT NOT NULL REFERENCES vpn_nodes(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source TEXT NOT NULL DEFAULT 'unknown',
    agent_ok BOOLEAN NOT NULL DEFAULT FALSE,
    agent_error TEXT,
    xui_ok BOOLEAN NOT NULL DEFAULT FALSE,
    xui_error TEXT,
    cpu_percent NUMERIC(8,3),
    load1 NUMERIC(12,4),
    load5 NUMERIC(12,4),
    load15 NUMERIC(12,4),
    memory_used_bytes BIGINT,
    memory_total_bytes BIGINT,
    swap_used_bytes BIGINT,
    swap_total_bytes BIGINT,
    disk_used_bytes BIGINT,
    disk_total_bytes BIGINT,
    net_rx_bytes BIGINT,
    net_tx_bytes BIGINT,
    tcp_connections INTEGER,
    udp_sockets INTEGER,
    uptime_seconds BIGINT,
    xray_state TEXT,
    xray_version TEXT,
    panel_latency_ms INTEGER,
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vpn_node_metric_samples_node_time
    ON vpn_node_metric_samples (node_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_vpn_node_metric_samples_time
    ON vpn_node_metric_samples (observed_at DESC);

CREATE TABLE IF NOT EXISTS vpn_subscription_metric_samples (
    id BIGSERIAL PRIMARY KEY,
    subscription_id BIGINT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    node_id BIGINT REFERENCES vpn_nodes(id) ON DELETE SET NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    client_email TEXT,
    xui_sub_id TEXT,
    up_bytes BIGINT NOT NULL DEFAULT 0,
    down_bytes BIGINT NOT NULL DEFAULT 0,
    all_time_bytes BIGINT NOT NULL DEFAULT 0,
    last_online_at TIMESTAMPTZ,
    enabled BOOLEAN,
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vpn_subscription_metric_samples_sub_time
    ON vpn_subscription_metric_samples (subscription_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_vpn_subscription_metric_samples_node_time
    ON vpn_subscription_metric_samples (node_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS vpn_subscription_events (
    id BIGSERIAL PRIMARY KEY,
    subscription_id BIGINT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    event_kind TEXT NOT NULL,
    from_node_id BIGINT REFERENCES vpn_nodes(id) ON DELETE SET NULL,
    to_node_id BIGINT REFERENCES vpn_nodes(id) ON DELETE SET NULL,
    reason TEXT,
    dns_change_id TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vpn_subscription_events_sub_time
    ON vpn_subscription_events (subscription_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_vpn_subscription_events_time
    ON vpn_subscription_events (created_at DESC);
