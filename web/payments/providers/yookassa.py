from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from decimal import Decimal
from typing import Any, Mapping
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest

from .base import PaymentCreateResult, PaymentProvider, PaymentWebhookResult


class YooKassaPaymentProvider(PaymentProvider):
    """
    Contract-only scaffold for YooKassa integration.
    No real API calls are performed in this provider yet.
    """

    def __init__(self) -> None:
        try:
            checkout_base_url = str(
                getattr(settings, "PAYMENT_YOOKASSA_CHECKOUT_BASE_URL", "https://pay.vxcloud.ru/yookassa")
            )
            webhook_secret = str(getattr(settings, "PAYMENT_YOOKASSA_WEBHOOK_SECRET", ""))
            shop_id = str(getattr(settings, "PAYMENT_YOOKASSA_SHOP_ID", ""))
            api_key = str(getattr(settings, "PAYMENT_YOOKASSA_API_KEY", ""))
        except ImproperlyConfigured:
            checkout_base_url = os.getenv("PAYMENT_YOOKASSA_CHECKOUT_BASE_URL", "https://pay.vxcloud.ru/yookassa")
            webhook_secret = os.getenv("PAYMENT_YOOKASSA_WEBHOOK_SECRET", "")
            shop_id = os.getenv("PAYMENT_YOOKASSA_SHOP_ID", "")
            api_key = os.getenv("PAYMENT_YOOKASSA_API_KEY", "")

        self.checkout_base_url = checkout_base_url.rstrip("/")
        self.webhook_secret = webhook_secret.strip()
        self.shop_id = shop_id.strip()
        self.api_key = api_key.strip()

    def create_payment(self, order: Mapping[str, Any]) -> PaymentCreateResult:
        order_id = int(order["id"])
        payment_id = f"yookassa_stub_{order_id}_{secrets.token_hex(6)}"
        query = urlencode(
            {
                "payment_id": payment_id,
                "order_id": order_id,
                "amount_minor": order.get("amount_minor") or 0,
                "currency": order.get("currency_iso") or "RUB",
            }
        )
        pay_url = f"{self.checkout_base_url}/checkout?{query}"
        return PaymentCreateResult(
            payment_id=payment_id,
            pay_url=pay_url,
            meta={"provider": "yookassa", "mode": "stub"},
        )

    def verify_webhook(self, request: HttpRequest) -> PaymentWebhookResult:
        raw = request.body or b""
        self._validate_signature(raw, request.headers.get("X-Yookassa-Signature"))

        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise ValueError("Invalid webhook JSON payload") from exc

        event_id = str(payload.get("event_id") or payload.get("id") or "")
        payment_id = str(payload.get("payment_id") or payload.get("object", {}).get("id") or "")
        status = str(payload.get("status") or payload.get("event") or "")
        if not event_id or not payment_id or not status:
            raise ValueError("Webhook payload must include event_id, payment_id, status")

        amount_minor: int | None = None
        currency_iso: str | None = None
        amount = None
        amount_obj = payload.get("amount") or payload.get("object", {}).get("amount") or {}
        if isinstance(amount_obj, dict):
            value = amount_obj.get("value")
            currency = amount_obj.get("currency")
            if value is not None:
                dec = Decimal(str(value))
                amount = dec
                amount_minor = int(dec * 100)
            if currency:
                currency_iso = str(currency).upper()

        if amount_minor is None:
            raw_minor = payload.get("amount_minor")
            if raw_minor is not None:
                amount_minor = int(raw_minor)
                amount = Decimal(amount_minor) / Decimal(100)

        if currency_iso is None:
            raw_currency = payload.get("currency") or payload.get("currency_iso")
            if raw_currency:
                currency_iso = str(raw_currency).upper()

        return PaymentWebhookResult(
            event_id=event_id,
            payment_id=payment_id,
            status=status,
            amount=amount,
            amount_minor=amount_minor,
            currency=currency_iso,
            provider_payload=payload,
        )

    def _validate_signature(self, raw_body: bytes, signature: str | None) -> None:
        if not self.webhook_secret:
            return
        provided = (signature or "").strip().lower()
        if not provided:
            raise ValueError("Missing webhook signature")
        expected = hmac.new(self.webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, provided):
            raise ValueError("Invalid webhook signature")
