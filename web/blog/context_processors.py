from django.conf import settings

from .models import Page


def _format_card_price_label() -> str:
    value = int(getattr(settings, "CARD_PAYMENT_AMOUNT_MINOR", 24900) or 0)
    currency = str(getattr(settings, "CARD_PAYMENT_CURRENCY", "RUB") or "RUB").upper()
    major = value // 100
    minor = value % 100
    amount = f"{major}" if minor == 0 else f"{major}.{minor:02d}"
    if currency in {"RUB", "RUR"}:
        return f"{amount} RUB"
    return f"{amount} {currency}"


def site_navigation(request):
    nav_pages = Page.objects.filter(is_published=True, show_in_nav=True).order_by("nav_order", "id")
    return {
        "nav_pages": nav_pages,
        "card_price_label": _format_card_price_label(),
    }

