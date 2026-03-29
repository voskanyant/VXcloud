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
    display_name = models.TextField()
    vless_url = models.TextField()
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
