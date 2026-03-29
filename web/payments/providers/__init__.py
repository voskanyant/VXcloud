from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured
from django.conf import settings

from .base import PaymentProvider
from .reference import ReferencePaymentProvider
from .yookassa import YooKassaPaymentProvider


_PROVIDERS: dict[str, type[PaymentProvider]] = {
    "reference": ReferencePaymentProvider,
    "yookassa": YooKassaPaymentProvider,
}


def get_payment_provider(provider_name: str | None = None) -> PaymentProvider:
    selected_name = provider_name
    if not selected_name:
        try:
            selected_name = str(getattr(settings, "PAYMENT_PROVIDER", "reference")).strip().lower()
        except ImproperlyConfigured:
            selected_name = "reference"

    provider_name = (selected_name or "reference").strip().lower()
    provider_cls = _PROVIDERS.get(provider_name)
    if provider_cls is None:
        available = ", ".join(sorted(_PROVIDERS.keys()))
        raise ValueError(f"Unknown PAYMENT_PROVIDER='{provider_name}'. Available: {available}")
    return provider_cls()


__all__ = [
    "PaymentProvider",
    "get_payment_provider",
]
