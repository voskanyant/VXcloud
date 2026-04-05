from __future__ import annotations

import json
import time
from urllib.error import URLError
from urllib.request import urlopen

from django.conf import settings

from .models import Page

_WORDPRESS_SHELL_CACHE: dict[str, object] = {
    "expires_at": 0.0,
    "value": None,
}


def _format_card_price_label() -> str:
    value = int(getattr(settings, "CARD_PAYMENT_AMOUNT_MINOR", 24900) or 0)
    currency = str(getattr(settings, "CARD_PAYMENT_CURRENCY", "RUB") or "RUB").upper()
    major = value // 100
    minor = value % 100
    amount = f"{major}" if minor == 0 else f"{major}.{minor:02d}"
    if currency in {"RUB", "RUR"}:
        return f"{amount} RUB"
    return f"{amount} {currency}"


def _normalize_menu_path(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    if "://" not in value:
        return value
    without_scheme = value.split("://", 1)[1]
    path_start = without_scheme.find("/")
    if path_start == -1:
        return "/"
    return without_scheme[path_start:]


def _mark_active(menu_items: list[dict[str, str]], request_path: str) -> list[dict[str, object]]:
    normalized_request = request_path or "/"
    enriched: list[dict[str, object]] = []
    for item in menu_items:
        path = _normalize_menu_path(item.get("path") or item.get("url") or "")
        is_active = False
        if path:
            if path == "/":
                is_active = normalized_request == "/"
            else:
                is_active = normalized_request == path or normalized_request.startswith(path.rstrip("/") + "/")
        enriched.append(
            {
                "label": item.get("label") or "",
                "url": item.get("url") or path or "#",
                "path": path,
                "active": is_active,
            }
        )
    return enriched


def _fetch_wordpress_shell() -> dict[str, object] | None:
    now = time.time()
    expires_at = float(_WORDPRESS_SHELL_CACHE.get("expires_at", 0.0) or 0.0)
    cached = _WORDPRESS_SHELL_CACHE.get("value")
    if cached is not None and now < expires_at:
        return cached if isinstance(cached, dict) else None

    wordpress_url = str(getattr(settings, "WORDPRESS_PUBLIC_SITE_URL", "") or "").rstrip("/")
    if not wordpress_url:
        _WORDPRESS_SHELL_CACHE["value"] = None
        _WORDPRESS_SHELL_CACHE["expires_at"] = now + 300
        return None

    endpoint = f"{wordpress_url}/wp-json/vx-site/v1/shell"
    try:
        with urlopen(endpoint, timeout=2.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError):
        _WORDPRESS_SHELL_CACHE["value"] = None
        _WORDPRESS_SHELL_CACHE["expires_at"] = now + 30
        return None

    if not isinstance(payload, dict):
        _WORDPRESS_SHELL_CACHE["value"] = None
        _WORDPRESS_SHELL_CACHE["expires_at"] = now + 30
        return None

    _WORDPRESS_SHELL_CACHE["value"] = payload
    _WORDPRESS_SHELL_CACHE["expires_at"] = now + 60
    return payload


def _build_wordpress_shell(request) -> dict[str, object] | None:
    if not getattr(settings, "WORDPRESS_PUBLIC_SITE_ENABLED", False):
        return None

    payload = _fetch_wordpress_shell()
    if not payload:
        return None

    brand = payload.get("brand") if isinstance(payload.get("brand"), dict) else {}
    cta = payload.get("cta") if isinstance(payload.get("cta"), dict) else {}
    footer = payload.get("footer") if isinstance(payload.get("footer"), dict) else {}
    header_menu = payload.get("header_menu") if isinstance(payload.get("header_menu"), list) else []
    footer_menu = payload.get("footer_menu") if isinstance(payload.get("footer_menu"), list) else []

    return {
        "brand": {
            "label": brand.get("label") or "VXcloud",
            "url": brand.get("url") or "/",
        },
        "header_menu": _mark_active(header_menu, request.path),
        "footer_menu": _mark_active(footer_menu, request.path),
        "cta": {
            "label": cta.get("label") or "Open account",
            "price_label": cta.get("price_label") or _format_card_price_label(),
            "account_url": cta.get("account_url") or "/account/",
            "buy_url": cta.get("buy_url") or "/account/buy/",
            "open_app_url": cta.get("open_app_url") or "/open-app/",
        },
        "footer": {
            "copy": footer.get("copy") or "© VXcloud",
            "tagline": footer.get("tagline") or "Стабильный VPN/прокси для повседневного доступа к интернету.",
        },
    }


def site_navigation(request):
    nav_pages = Page.objects.filter(is_published=True, show_in_nav=True).order_by("nav_order", "id")
    return {
        "nav_pages": nav_pages,
        "card_price_label": _format_card_price_label(),
        "wordpress_shell": _build_wordpress_shell(request),
    }
