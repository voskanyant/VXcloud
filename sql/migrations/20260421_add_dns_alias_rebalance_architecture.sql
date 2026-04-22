ALTER TABLE vpn_nodes
    ADD COLUMN IF NOT EXISTS public_ip TEXT,
    ADD COLUMN IF NOT EXISTS node_fqdn TEXT,
    ADD COLUMN IF NOT EXISTS compatibility_pool TEXT NOT NULL DEFAULT 'default',
    ADD COLUMN IF NOT EXISTS xray_api_host TEXT,
    ADD COLUMN IF NOT EXISTS xray_api_port INTEGER,
    ADD COLUMN IF NOT EXISTS xray_metrics_host TEXT,
    ADD COLUMN IF NOT EXISTS xray_metrics_port INTEGER,
    ADD COLUMN IF NOT EXISTS bandwidth_capacity_mbps INTEGER NOT NULL DEFAULT 1000,
    ADD COLUMN IF NOT EXISTS connection_capacity INTEGER NOT NULL DEFAULT 10000;

UPDATE vpn_nodes
SET public_ip = backend_host
WHERE (public_ip IS NULL OR public_ip = '')
  AND backend_host ~ '^[0-9]+(\\.[0-9]+){3}$';

UPDATE vpn_nodes
SET node_fqdn = CASE
    WHEN backend_host ~ '^[0-9]+(\\.[0-9]+){3}$' THEN NULL
    ELSE backend_host
END
WHERE node_fqdn IS NULL OR node_fqdn = '';

ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS alias_fqdn TEXT,
    ADD COLUMN IF NOT EXISTS current_node_id BIGINT REFERENCES vpn_nodes(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS desired_node_id BIGINT REFERENCES vpn_nodes(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS assignment_state TEXT NOT NULL DEFAULT 'steady',
    ADD COLUMN IF NOT EXISTS ttl_seconds INTEGER NOT NULL DEFAULT 300,
    ADD COLUMN IF NOT EXISTS overlap_until TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS dns_provider TEXT,
    ADD COLUMN IF NOT EXISTS dns_record_id TEXT,
    ADD COLUMN IF NOT EXISTS last_dns_change_id TEXT,
    ADD COLUMN IF NOT EXISTS compatibility_pool TEXT,
    ADD COLUMN IF NOT EXISTS planned_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS presynced_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS cutover_at TIMESTAMPTZ;

UPDATE subscriptions
SET current_node_id = assigned_node_id
WHERE current_node_id IS NULL
  AND assigned_node_id IS NOT NULL;

UPDATE subscriptions s
SET compatibility_pool = n.compatibility_pool
FROM vpn_nodes n
WHERE s.compatibility_pool IS NULL
  AND s.current_node_id = n.id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_subscriptions_alias_fqdn
    ON subscriptions (alias_fqdn)
    WHERE alias_fqdn IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_subscriptions_current_node_id
    ON subscriptions (current_node_id);

CREATE INDEX IF NOT EXISTS idx_subscriptions_desired_node_id
    ON subscriptions (desired_node_id);

CREATE INDEX IF NOT EXISTS idx_subscriptions_assignment_state_v2
    ON subscriptions (assignment_state, current_node_id, desired_node_id);

CREATE INDEX IF NOT EXISTS idx_subscriptions_overlap_until
    ON subscriptions (overlap_until);

ALTER TABLE vpn_node_load_snapshots
    ADD COLUMN IF NOT EXISTS probe_latency_ms INTEGER;

ALTER TABLE vpn_rebalance_decisions
    ADD COLUMN IF NOT EXISTS dns_change_id TEXT,
    ADD COLUMN IF NOT EXISTS rollback_reason TEXT;
