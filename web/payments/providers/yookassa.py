from __future__ import annotations

import base64
import json
import os
from decimal import Decimal
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest

from .base import PaymentCreateResult, PaymentProvider, PaymentWebhookResult


class YooKassaPaymentProvider(PaymentProvider):
    api_base_url = "https://api.yookassa.ru/v3"

    def __init__(self) -> None:
        try:
            shop_id = str(getattr(settings, "PAYMENT_YOOKASSA_SHOP_ID", ""))
            api_key = str(getattr(settings, "PAYMENT_YOOKASSA_API_KEY", ""))
        except ImproperlyConfigured:
            shop_id = os.getenv("PAYMENT_YOOKASSA_SHOP_ID", "")
            api_key = os.getenv("PAYMENT_YOOKASSA_API_KEY", "")

        self.shop_id = shop_id.strip()
        self.api_key = api_key.strip()

    def create_payment(self, order: Mapping[str, Any]) -> PaymentCreateResult:
        self._ensure_configured()
        order_id = int(order["id"])
        amount_minor = int(order.get("amount_minor") or 0)
        currency_iso = str(order.get("currency_iso") or "RUB").upper()
        return_url = str(order.get("return_url") or "").strip()
        if not return_url:
            raise ValueError("YooKassa return_url is required")

        payload = {
            "amount": {
                "value": self._format_amount_minor(amount_minor),
                "currency": currency_iso,
            },
            "capture": True,
            "confirmation": {
                "type": "redirect",
                "return_url": return_url,
            },
            "description": str(order.get("description") or f"VXcloud order #{order_id}")[:128],
            "metadata": {
                "order_id": str(order_id),
                "user_id": str(order.get("user_id") or ""),
            },
        }
        response = self._request_json(
            method="POST",
            path="/payments",
            payload=payload,
            idempotence_key=str(order.get("idempotency_key") or f"vxcloud-order-{order_id}"),
        )
        payment_id = str(response.get("id") or "").strip()
        confirmation = response.get("confirmation") if isinstance(response.get("confirmation"), dict) else {}
        pay_url = str(confirmation.get("confirmation_url") or "").strip()
        if not payment_id or not pay_url:
            raise ValueError("YooKassa create payment response is missing id or confirmation_url")
        return PaymentCreateResult(
            payment_id=payment_id,
            pay_url=pay_url,
            meta={"provider": "yookassa"},
        )

    def verify_webhook(self, request: HttpRequest) -> PaymentWebhookResult:
        try:
            payload = json.loads((request.body or b"").decode("utf-8"))
        except Exception as exc:
            raise ValueError("Invalid webhook JSON payload") from exc

        event = str(payload.get("event") or "").strip().lower()
        obj = payload.get("object")
        if not isinstance(obj, dict):
            raise ValueError("YooKassa webhook payload must include object")
        payment_id = str(obj.get("id") or "").strip()
        status = str(obj.get("status") or "").strip().lower()
        if not payment_id or not status:
            raise ValueError("YooKassa webhook payload must include object.id and object.status")

        # Do not trust the incoming body alone for payment finalization.
        remote_payment = self._fetch_payment(payment_id)
        remote_status = str(remote_payment.get("status") or "").strip().lower()
        if remote_status and remote_status != status:
            raise ValueError("YooKassa webhook status does not match fetched payment status")

        amount, amount_minor, currency_iso = self._extract_amount(remote_payment if remote_payment else obj)
        event_id = f"{event or 'payment'}:{payment_id}:{remote_status or status}"

        return PaymentWebhookResult(
            event_id=event_id,
            payment_id=payment_id,
            status=remote_status or status,
            amount=amount,
            amount_minor=amount_minor,
            currency=currency_iso,
            provider_payload=payload,
        )

    def _ensure_configured(self) -> None:
        if not self.shop_id or not self.api_key:
            raise ImproperlyConfigured("YooKassa credentials are not configured")

    @staticmethod
    def _format_amount_minor(amount_minor: int) -> str:
        dec = (Decimal(int(amount_minor)) / Decimal(100)).quantize(Decimal("0.01"))
        return format(dec, "f")

    @staticmethod
    def _extract_amount(payload: Mapping[str, Any]) -> tuple[Decimal | None, int | None, str | None]:
        amount_obj = payload.get("amount")
        if not isinstance(amount_obj, dict):
            return None, None, None
        value = amount_obj.get("value")
        currency = amount_obj.get("currency")
        if value is None:
            return None, None, str(currency).upper() if currency else None
        amount = Decimal(str(value))
        amount_minor = int((amount * Decimal(100)).quantize(Decimal("1")))
        currency_iso = str(currency).upper() if currency else None
        return amount, amount_minor, currency_iso

    def _fetch_payment(self, payment_id: str) -> dict[str, Any]:
        self._ensure_configured()
        response = self._request_json(method="GET", path=f"/payments/{payment_id}")
        if str(response.get("id") or "").strip() != payment_id:
            raise ValueError("Fetched YooKassa payment id does not match webhook payment id")
        return response

    def _request_json(
        self,
        *,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
        idempotence_key: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_configured()
        body: bytes | None = None
        headers = {
            "Authorization": f"Basic {self._basic_auth_token()}",
            "Accept": "application/json",
        }
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if idempotence_key:
            headers["Idempotence-Key"] = str(idempotence_key)[:64]

        request = Request(f"{self.api_base_url}{path}", data=body, method=method.upper(), headers=headers)
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise ValueError(f"YooKassa API HTTP {exc.code}: {error_body}") from exc
        except URLError as exc:
            raise ValueError(f"YooKassa API connection failed: {exc}") from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("YooKassa API returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("YooKassa API returned unexpected payload")
        return parsed

    def _basic_auth_token(self) -> str:
        token = f"{self.shop_id}:{self.api_key}".encode("utf-8")
        return base64.b64encode(token).decode("ascii")
