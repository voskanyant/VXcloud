from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models


class LinkedAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="linked_account")
    telegram_id = models.BigIntegerField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.telegram_id}"


class BotUser(models.Model):
    id = models.BigAutoField(primary_key=True)
    telegram_id = models.BigIntegerField(unique=True)
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
    vless_url = models.TextField()
    expires_at = models.DateTimeField()
    is_active = models.BooleanField()
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
    created_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "orders"
