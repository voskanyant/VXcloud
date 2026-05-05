from django.db import migrations, models
import django.db.models.deletion


SQL = """
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
"""


class Migration(migrations.Migration):
    dependencies = [
        ("cabinet", "0007_vpnnodeloadsnapshot_vpnrebalancedecision"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="vpnnode",
                    name="metrics_agent_enabled",
                    field=models.BooleanField(default=False),
                ),
                migrations.AddField(
                    model_name="vpnnode",
                    name="metrics_agent_url",
                    field=models.TextField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="vpnnode",
                    name="metrics_agent_token",
                    field=models.TextField(blank=True, null=True),
                ),
                migrations.AlterField(
                    model_name="vpnnodeloadsnapshot",
                    name="created_at",
                    field=models.DateTimeField(db_column="observed_at"),
                ),
                migrations.AlterField(
                    model_name="vpnnodeloadsnapshot",
                    name="score_hint",
                    field=models.FloatField(blank=True, db_column="score", null=True),
                ),
                migrations.RemoveField(
                    model_name="vpnrebalancedecision",
                    name="assignment_source",
                ),
                migrations.AlterField(
                    model_name="vpnrebalancedecision",
                    name="created_at",
                    field=models.DateTimeField(db_column="decided_at"),
                ),
                migrations.AlterField(
                    model_name="vpnrebalancedecision",
                    name="from_score",
                    field=models.FloatField(blank=True, db_column="score_before", null=True),
                ),
                migrations.AlterField(
                    model_name="vpnrebalancedecision",
                    name="to_score",
                    field=models.FloatField(blank=True, db_column="score_after", null=True),
                ),
                migrations.RemoveField(
                    model_name="vpnrebalancedecision",
                    name="score_delta",
                ),
                migrations.AddField(
                    model_name="vpnrebalancedecision",
                    name="details",
                    field=models.JSONField(default=dict),
                ),
                migrations.CreateModel(
                    name="VPNNodeMetricSample",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        ("observed_at", models.DateTimeField()),
                        ("source", models.TextField()),
                        ("agent_ok", models.BooleanField()),
                        ("agent_error", models.TextField(blank=True, null=True)),
                        ("xui_ok", models.BooleanField()),
                        ("xui_error", models.TextField(blank=True, null=True)),
                        ("cpu_percent", models.FloatField(blank=True, null=True)),
                        ("load1", models.FloatField(blank=True, null=True)),
                        ("load5", models.FloatField(blank=True, null=True)),
                        ("load15", models.FloatField(blank=True, null=True)),
                        ("memory_used_bytes", models.BigIntegerField(blank=True, null=True)),
                        ("memory_total_bytes", models.BigIntegerField(blank=True, null=True)),
                        ("swap_used_bytes", models.BigIntegerField(blank=True, null=True)),
                        ("swap_total_bytes", models.BigIntegerField(blank=True, null=True)),
                        ("disk_used_bytes", models.BigIntegerField(blank=True, null=True)),
                        ("disk_total_bytes", models.BigIntegerField(blank=True, null=True)),
                        ("net_rx_bytes", models.BigIntegerField(blank=True, null=True)),
                        ("net_tx_bytes", models.BigIntegerField(blank=True, null=True)),
                        ("tcp_connections", models.IntegerField(blank=True, null=True)),
                        ("udp_sockets", models.IntegerField(blank=True, null=True)),
                        ("uptime_seconds", models.BigIntegerField(blank=True, null=True)),
                        ("xray_state", models.TextField(blank=True, null=True)),
                        ("xray_version", models.TextField(blank=True, null=True)),
                        ("panel_latency_ms", models.IntegerField(blank=True, null=True)),
                        ("raw", models.JSONField(default=dict)),
                        ("created_at", models.DateTimeField()),
                        (
                            "node",
                            models.ForeignKey(
                                db_column="node_id",
                                on_delete=django.db.models.deletion.DO_NOTHING,
                                to="cabinet.vpnnode",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "VPN Node Metric Sample",
                        "verbose_name_plural": "VPN Node Metric Samples",
                        "db_table": "vpn_node_metric_samples",
                        "managed": False,
                    },
                ),
                migrations.CreateModel(
                    name="VPNSubscriptionMetricSample",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        ("observed_at", models.DateTimeField()),
                        ("client_email", models.TextField(blank=True, null=True)),
                        ("xui_sub_id", models.TextField(blank=True, null=True)),
                        ("up_bytes", models.BigIntegerField()),
                        ("down_bytes", models.BigIntegerField()),
                        ("all_time_bytes", models.BigIntegerField()),
                        ("last_online_at", models.DateTimeField(blank=True, null=True)),
                        ("enabled", models.BooleanField(blank=True, null=True)),
                        ("raw", models.JSONField(default=dict)),
                        ("created_at", models.DateTimeField()),
                        (
                            "node",
                            models.ForeignKey(
                                blank=True,
                                db_column="node_id",
                                null=True,
                                on_delete=django.db.models.deletion.DO_NOTHING,
                                to="cabinet.vpnnode",
                            ),
                        ),
                        (
                            "subscription",
                            models.ForeignKey(
                                db_column="subscription_id",
                                on_delete=django.db.models.deletion.DO_NOTHING,
                                to="cabinet.botsubscription",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "VPN Subscription Metric Sample",
                        "verbose_name_plural": "VPN Subscription Metric Samples",
                        "db_table": "vpn_subscription_metric_samples",
                        "managed": False,
                    },
                ),
                migrations.CreateModel(
                    name="VPNSubscriptionEvent",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        ("event_kind", models.TextField()),
                        ("reason", models.TextField(blank=True, null=True)),
                        ("dns_change_id", models.TextField(blank=True, null=True)),
                        ("details", models.JSONField(default=dict)),
                        ("created_at", models.DateTimeField()),
                        (
                            "from_node",
                            models.ForeignKey(
                                blank=True,
                                db_column="from_node_id",
                                null=True,
                                on_delete=django.db.models.deletion.DO_NOTHING,
                                related_name="subscription_events_from",
                                to="cabinet.vpnnode",
                            ),
                        ),
                        (
                            "subscription",
                            models.ForeignKey(
                                db_column="subscription_id",
                                on_delete=django.db.models.deletion.DO_NOTHING,
                                to="cabinet.botsubscription",
                            ),
                        ),
                        (
                            "to_node",
                            models.ForeignKey(
                                blank=True,
                                db_column="to_node_id",
                                null=True,
                                on_delete=django.db.models.deletion.DO_NOTHING,
                                related_name="subscription_events_to",
                                to="cabinet.vpnnode",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "VPN Subscription Event",
                        "verbose_name_plural": "VPN Subscription Events",
                        "db_table": "vpn_subscription_events",
                        "managed": False,
                    },
                ),
            ],
        )
    ]
