from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class LinkedAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="linked_account")
    telegram_id = models.BigIntegerField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.telegram_id}"


class TelegramLinkToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="telegram_link_tokens")
    code = models.CharField(max_length=32, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_telegram_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "consumed_at", "expires_at"]),
        ]

    @property
    def is_active(self) -> bool:
        return self.consumed_at is None and self.expires_at > timezone.now()

    def __str__(self) -> str:
        return f"link:{self.code} user={self.user_id}"


class WebLoginToken(models.Model):
    id = models.BigAutoField(primary_key=True)
    token = models.TextField(unique=True)
    telegram_id = models.BigIntegerField()
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "web_login_tokens"


class PaymentEvent(models.Model):
    id = models.BigAutoField(primary_key=True)
    provider = models.TextField()
    event_id = models.TextField()
    body = models.JSONField()
    created_at = models.DateTimeField()
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "payment_events"


class BotUser(models.Model):
    id = models.BigAutoField(primary_key=True)
    telegram_id = models.BigIntegerField(unique=True)
    client_code = models.TextField()
    username = models.TextField(null=True, blank=True)
    first_name = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "users"


class BotSubscription(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(BotUser, db_column="user_id", on_delete=models.DO_NOTHING)
    inbound_id = models.IntegerField()
    client_uuid = models.UUIDField()
    client_email = models.TextField()
    xui_sub_id = models.TextField(null=True, blank=True)
    display_name = models.TextField()
    vless_url = models.TextField()
    alias_fqdn = models.TextField(null=True, blank=True)
    assigned_node = models.ForeignKey(
        "VPNNode",
        db_column="assigned_node_id",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
    )
    current_node = models.ForeignKey(
        "VPNNode",
        db_column="current_node_id",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="subscriptions_current",
    )
    desired_node = models.ForeignKey(
        "VPNNode",
        db_column="desired_node_id",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="subscriptions_desired",
    )
    assignment_source = models.TextField()
    assigned_at = models.DateTimeField(null=True, blank=True)
    last_rebalanced_at = models.DateTimeField(null=True, blank=True)
    migration_state = models.TextField()
    assignment_state = models.TextField()
    ttl_seconds = models.IntegerField()
    overlap_until = models.DateTimeField(null=True, blank=True)
    dns_provider = models.TextField(null=True, blank=True)
    dns_record_id = models.TextField(null=True, blank=True)
    last_dns_change_id = models.TextField(null=True, blank=True)
    compatibility_pool = models.TextField(null=True, blank=True)
    planned_at = models.DateTimeField(null=True, blank=True)
    presynced_at = models.DateTimeField(null=True, blank=True)
    cutover_at = models.DateTimeField(null=True, blank=True)
    feed_token = models.TextField(null=True, blank=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "subscriptions"


class BotOrder(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(BotUser, db_column="user_id", on_delete=models.DO_NOTHING)
    amount_stars = models.IntegerField()
    currency = models.TextField()
    payload = models.TextField(unique=True)
    status = models.TextField()
    telegram_payment_charge_id = models.TextField(null=True, blank=True)
    provider_payment_charge_id = models.TextField(null=True, blank=True)
    channel = models.TextField(null=True, blank=True)
    payment_method = models.TextField(null=True, blank=True)
    amount_minor = models.BigIntegerField(null=True, blank=True)
    currency_iso = models.TextField(null=True, blank=True)
    card_provider = models.TextField(null=True, blank=True)
    card_payment_id = models.TextField(null=True, blank=True)
    idempotency_key = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "orders"


class SupportTicket(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        BotUser,
        db_column="user_id",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
    )
    status = models.TextField()
    subject = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "support_tickets"


class SupportMessage(models.Model):
    id = models.BigAutoField(primary_key=True)
    ticket = models.ForeignKey(SupportTicket, db_column="ticket_id", on_delete=models.DO_NOTHING)
    sender_role = models.TextField()
    sender_user = models.ForeignKey(
        BotUser,
        db_column="sender_user_id",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
    )
    message_text = models.TextField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "support_messages"


class VPNNode(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.TextField(unique=True)
    region = models.TextField(null=True, blank=True)
    xui_base_url = models.TextField()
    xui_username = models.TextField()
    xui_password = models.TextField()
    xui_inbound_id = models.IntegerField()
    backend_host = models.TextField()
    backend_port = models.IntegerField()
    public_ip = models.TextField(null=True, blank=True)
    node_fqdn = models.TextField(null=True, blank=True)
    compatibility_pool = models.TextField()
    xray_api_host = models.TextField(null=True, blank=True)
    xray_api_port = models.IntegerField(null=True, blank=True)
    xray_metrics_host = models.TextField(null=True, blank=True)
    xray_metrics_port = models.IntegerField(null=True, blank=True)
    bandwidth_capacity_mbps = models.IntegerField()
    connection_capacity = models.IntegerField()
    backend_weight = models.IntegerField()
    is_active = models.BooleanField()
    lb_enabled = models.BooleanField()
    needs_backfill = models.BooleanField()
    backfill_requested_at = models.DateTimeField(null=True, blank=True)
    last_backfill_at = models.DateTimeField(null=True, blank=True)
    last_backfill_error = models.TextField(null=True, blank=True)
    last_health_at = models.DateTimeField(null=True, blank=True)
    last_health_ok = models.BooleanField(null=True, blank=True)
    last_health_error = models.TextField(null=True, blank=True)
    last_reality_public_key = models.TextField(null=True, blank=True)
    last_reality_short_id = models.TextField(null=True, blank=True)
    last_reality_sni = models.TextField(null=True, blank=True)
    last_reality_fingerprint = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "vpn_nodes"
        verbose_name = "VPN Node"
        verbose_name_plural = "VPN Nodes"

    def __str__(self) -> str:
        return f"{self.name} ({self.backend_host}:{self.backend_port})"


class EdgeServer(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.TextField(unique=True)
    public_host = models.TextField()
    public_ip = models.TextField()
    frontend_port = models.IntegerField()
    healthcheck_host = models.TextField(null=True, blank=True)
    healthcheck_port = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField()
    is_primary = models.BooleanField()
    accept_new_clients = models.BooleanField()
    priority = models.IntegerField()
    last_health_at = models.DateTimeField(null=True, blank=True)
    last_health_ok = models.BooleanField(null=True, blank=True)
    last_health_error = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "edge_servers"
        verbose_name = "HAProxy Edge"
        verbose_name_plural = "HAProxy Edges"

    def __str__(self) -> str:
        return f"{self.name} ({self.public_host}:{self.frontend_port})"


class VPNNodeClient(models.Model):
    id = models.BigAutoField(primary_key=True)
    node = models.ForeignKey(VPNNode, db_column="node_id", on_delete=models.DO_NOTHING)
    subscription = models.ForeignKey(BotSubscription, db_column="subscription_id", on_delete=models.DO_NOTHING)
    client_uuid = models.UUIDField()
    client_email = models.TextField()
    xui_sub_id = models.TextField(null=True, blank=True)
    desired_enabled = models.BooleanField()
    desired_expires_at = models.DateTimeField()
    observed_enabled = models.BooleanField(null=True, blank=True)
    observed_expires_at = models.DateTimeField(null=True, blank=True)
    sync_state = models.TextField()
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "vpn_node_clients"
        verbose_name = "VPN Node Client"
        verbose_name_plural = "VPN Node Clients"

    def __str__(self) -> str:
        return f"node={self.node_id} sub={self.subscription_id} state={self.sync_state}"


class VPNNodeLoadSnapshot(models.Model):
    id = models.BigAutoField(primary_key=True)
    node = models.ForeignKey(VPNNode, db_column="node_id", on_delete=models.DO_NOTHING)
    assigned_active_subscriptions = models.IntegerField()
    observed_enabled_clients = models.IntegerField()
    total_traffic_bytes = models.BigIntegerField()
    peak_concurrency = models.IntegerField()
    probe_latency_ms = models.IntegerField(null=True, blank=True)
    health_ok = models.BooleanField()
    health_error = models.TextField(null=True, blank=True)
    score_hint = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "vpn_node_load_snapshots"
        verbose_name = "VPN Node Load Snapshot"
        verbose_name_plural = "VPN Node Load Snapshots"


class VPNRebalanceDecision(models.Model):
    id = models.BigAutoField(primary_key=True)
    subscription = models.ForeignKey(BotSubscription, db_column="subscription_id", on_delete=models.DO_NOTHING)
    from_node = models.ForeignKey(
        VPNNode,
        db_column="from_node_id",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="rebalance_decisions_from",
    )
    to_node = models.ForeignKey(
        VPNNode,
        db_column="to_node_id",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="rebalance_decisions_to",
    )
    decision_kind = models.TextField()
    assignment_source = models.TextField()
    from_score = models.FloatField(null=True, blank=True)
    to_score = models.FloatField(null=True, blank=True)
    score_delta = models.FloatField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    dns_change_id = models.TextField(null=True, blank=True)
    rollback_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "vpn_rebalance_decisions"
        verbose_name = "VPN Rebalance Decision"
        verbose_name_plural = "VPN Rebalance Decisions"
