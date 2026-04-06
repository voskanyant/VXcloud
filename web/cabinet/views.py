from __future__ import annotations

import base64
import asyncio
import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import string
import sys
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl
from urllib.parse import unquote
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen

import qrcode
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError
from django.db import transaction
from django.conf import settings
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.http import HttpRequest, HttpResponse
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import EmailAuthenticationForm, SignUpForm
from .models import BotOrder, BotSubscription, BotUser, LinkedAccount, PaymentEvent, TelegramLinkToken, WebLoginToken
from payments.providers import get_payment_provider


ALLOWED_DEEPLINK_SCHEMES = ("vless://", "vmess://", "trojan://", "ss://", "hysteria2://", "tuic://")
PAYMENT_SUCCESS_STATUSES = {"success", "succeeded", "paid", "approved"}
LOGGER = logging.getLogger(__name__)
WEB_ORDER_SESSION_KEY = "web_order_checkout_state_v1"
WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET = 10**12


def _account_embed_mode(request: HttpRequest) -> bool:
    return (request.GET.get("embed") or "").strip() == "1"


def _account_backend_base(request: HttpRequest) -> str:
    return "/account-app/" if _account_embed_mode(request) else "/account/"


def _account_frontend_url(path: str = "") -> str:
    base = "/account/"
    suffix = str(path or "").lstrip("/")
    return base if not suffix else f"{base}{suffix}"


def _account_backend_url(request: HttpRequest, path: str = "") -> str:
    base = _account_backend_base(request)
    suffix = str(path or "").lstrip("/")
    url = base if not suffix else f"{base}{suffix}"
    if _account_embed_mode(request):
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}embed=1"
    return url


def _account_redirect(request: HttpRequest, path: str = "") -> HttpResponse:
    target = _account_backend_url(request, path) if _account_embed_mode(request) else _account_frontend_url(path)
    return redirect(target)


def _redirect_after_account_post(request: HttpRequest, fallback_path: str = "") -> HttpResponse:
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return _account_redirect(request, fallback_path)


def _account_template_urls(request: HttpRequest) -> dict[str, object]:
    return {
        "embed_mode": _account_embed_mode(request),
        "frontend_dashboard_url": _account_frontend_url(),
        "backend_dashboard_url": _account_backend_url(request),
        "backend_link_url": _account_backend_url(request, "link/"),
        "backend_buy_url": _account_backend_url(request, "buy/"),
        "backend_renew_url": _account_backend_url(request, "renew/"),
        "backend_config_prefix": _account_backend_base(request) + "config/",
        "backend_rename_prefix": _account_backend_base(request) + "subscriptions/",
        "support_url": "/instructions/",
    }


def _json_body(request: HttpRequest) -> dict[str, object]:
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_error(message: str, *, status: int = 400, errors: dict[str, str] | None = None) -> JsonResponse:
    payload: dict[str, object] = {"ok": False, "error": message}
    if errors:
        payload["errors"] = errors
    return JsonResponse(payload, status=status)


def _serialize_form_errors(form) -> dict[str, str]:
    serialized: dict[str, str] = {}
    for field, field_errors in form.errors.items():
        key = "form" if field == "__all__" else str(field)
        serialized[key] = " ".join(str(item) for item in field_errors)
    return serialized


def _format_dt_label(value: datetime | None) -> str:
    if not value:
        return ""
    return timezone.localtime(value).strftime("%d.%m.%Y %H:%M")


def _build_subscription_rows(bot_user: BotUser | None) -> tuple[list[dict[str, object]], int, int]:
    subscriptions = _list_subscriptions_for_bot_user(bot_user)
    now = timezone.now()
    rows: list[dict[str, object]] = []
    for item in subscriptions:
        expires_at = getattr(item, "expires_at", None)
        is_active = bool(getattr(item, "is_active", False) and expires_at and expires_at > now and getattr(item, "revoked_at", None) is None)
        status_text = "Активна" if is_active else ("Отключена" if getattr(item, "revoked_at", None) else "Истекла")
        rows.append(
            {
                "obj": item,
                "id": int(item.id),
                "display_name": _subscription_display_name(item),
                "is_active": is_active,
                "status_text": status_text,
                "expires_at": expires_at,
            }
        )
    active_configs = sum(1 for row in rows if bool(row["is_active"]))
    inactive_configs = max(len(rows) - active_configs, 0)
    return rows, active_configs, inactive_configs


def _serialize_subscription_row(row: dict[str, object]) -> dict[str, object]:
    subscription = row["obj"]
    return {
        "id": int(row["id"]),
        "display_name": str(row["display_name"]),
        "is_active": bool(row["is_active"]),
        "status_text": str(row["status_text"]),
        "expires_at": _format_dt_label(row.get("expires_at")),
        "config_url": _account_frontend_url(f"config/{int(row['id'])}/"),
        "vless_url": getattr(subscription, "vless_url", "") or "",
    }


def _build_dashboard_payload(request: HttpRequest) -> dict[str, object]:
    linked, bot_user = _resolve_account_bot_user(request, ensure_site_bot_user=True)
    rows, active_configs, inactive_configs = _build_subscription_rows(bot_user)
    subscriptions_payload = [_serialize_subscription_row(row) for row in rows]
    telegram_payload: dict[str, object] = {
        "linked": bool(linked),
        "status_text": "Привязан" if linked else "Не привязан",
        "telegram_id": int(linked.telegram_id) if linked else None,
        "link_url": _account_frontend_url("link/"),
    }
    return {
        "title": "Личный кабинет",
        "subtitle": "Управляйте доступами, конфигами и подключением в одном месте.",
        "card_price_label": _format_minor_amount_rub(settings.CARD_PAYMENT_AMOUNT_MINOR),
        "access_count": len(subscriptions_payload),
        "user": {
            "username": request.user.username,
            "client_code": (getattr(bot_user, "client_code", "") or ""),
        },
        "stats": {
            "active_configs": active_configs,
            "inactive_configs": inactive_configs,
        },
        "telegram": telegram_payload,
        "subscriptions": subscriptions_payload,
        "urls": {
            "dashboard": _account_frontend_url(),
            "buy": _account_frontend_url("buy/"),
            "renew": _account_frontend_url("renew/"),
            "support": "/instructions/",
            "password_reset": "/accounts/password_reset/",
        },
    }


def _build_config_payload(request: HttpRequest, subscription_id: int) -> tuple[dict[str, object] | None, str | None]:
    linked, bot_user = _resolve_account_bot_user(request, ensure_site_bot_user=True)
    if not bot_user:
        return None, "Не удалось загрузить данные аккаунта."

    rows, _, _ = _build_subscription_rows(bot_user)
    row_map = {int(row["id"]): row for row in rows}
    current_row = row_map.get(int(subscription_id))
    if current_row is None:
        return None, "Конфиг не найден."

    sub = current_row["obj"]
    qr_data = getattr(sub, "vless_url", "") or ""
    img = qrcode.make(qr_data)
    buff = io.BytesIO()
    img.save(buff, format="PNG")
    qr_b64 = base64.b64encode(buff.getvalue()).decode("ascii")

    return (
        {
            "id": int(sub.id),
            "display_name": _subscription_display_name(sub),
            "status_text": str(current_row["status_text"]),
            "is_active": bool(current_row["is_active"]),
            "expires_at": _format_dt_label(getattr(sub, "expires_at", None)),
            "client_code": (getattr(getattr(sub, "user", None), "client_code", "") or ""),
            "copy_text": qr_data,
            "qr_image_data_url": f"data:image/png;base64,{qr_b64}",
            "dashboard_url": _account_frontend_url(),
            "subscriptions": [
                {
                    "id": int(row["id"]),
                    "label": f"#{int(row['id'])} — {_format_dt_label(row.get('expires_at'))}" + (" (active)" if bool(row["is_active"]) else ""),
                    "url": _account_frontend_url(f"config/{int(row['id'])}/"),
                    "selected": int(row["id"]) == int(sub.id),
                }
                for row in rows
            ],
            "telegram": {
                "linked": bool(linked),
                "telegram_id": int(linked.telegram_id) if linked else None,
            },
        },
        None,
    )

def _log_payment_event(
    *,
    order_id: int | None,
    client_code: str | None,
    provider: str | None,
    event_id: str | None,
    provision_state: str,
    paid_to_ready_ms: int | None = None,
) -> None:
    payload: dict[str, object] = {
        "event": "payment_flow",
        "order_id": int(order_id) if order_id is not None else 0,
        "client_code": client_code or "",
        "provider": provider or "",
        "event_id": event_id or "",
        "provision_state": provision_state,
    }
    if paid_to_ready_ms is not None:
        payload["paid_to_ready_ms"] = paid_to_ready_ms
    LOGGER.info(json.dumps(payload, ensure_ascii=False))


class EmailLoginView(LoginView):
    authentication_form = EmailAuthenticationForm
    template_name = "registration/login.html"

    def get_success_url(self) -> str:
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to
        if _account_embed_mode(self.request):
            return _account_backend_url(self.request)
        return super().get_success_url()


def _format_minor_amount_rub(amount_minor: int | None) -> str:
    value = int(amount_minor or 0)
    rub = value // 100
    kop = value % 100
    if kop == 0:
        return f"{rub} ₽"
    return f"{rub}.{kop:02d} ₽"


def _format_payment_method(method: str | None, currency: str | None = None) -> str:
    normalized = (method or "").strip().lower()
    if not normalized:
        if (currency or "").upper() == "XTR":
            return "Telegram Stars"
        return "Не указан"
    if normalized == "card":
        return "Карта"
    if normalized == "stars":
        return "Telegram Stars"
    return normalized


def _get_subscription_snapshot_for_bot_user(bot_user: BotUser | None) -> tuple[BotSubscription | None, bool, str]:
    if not bot_user:
        return None, False, "Не указан"

    now = timezone.now()
    subscription = (
        BotSubscription.objects.filter(user_id=bot_user.id)
        .order_by("-expires_at", "-id")
        .first()
    )
    has_active = bool(subscription and subscription.is_active and subscription.expires_at > now)
    latest_order = (
        BotOrder.objects.filter(user_id=bot_user.id, status__in=["paid", "activating", "activated"])
        .order_by("-paid_at", "-id")
        .first()
    )
    payment_method = _format_payment_method(
        getattr(latest_order, "payment_method", None) if latest_order else None,
        getattr(latest_order, "currency", None) if latest_order else None,
    )
    return subscription, has_active, payment_method


def _list_subscriptions_for_bot_user(bot_user: BotUser | None) -> list[BotSubscription]:
    if not bot_user:
        return []
    return list(
        BotSubscription.objects.filter(user_id=bot_user.id)
        .order_by("-is_active", "-expires_at", "-id")
    )


def _subscription_display_name(subscription: BotSubscription) -> str:
    value = (getattr(subscription, "display_name", "") or "").strip()
    if value:
        return value
    return f"Конфиг #{subscription.id}"


def _site_placeholder_telegram_id_for_user(user_id: int) -> int:
    return -(WEB_PLACEHOLDER_TELEGRAM_ID_OFFSET + int(user_id))


def _ensure_site_bot_user(request: HttpRequest) -> BotUser | None:
    if not getattr(request.user, "is_authenticated", False):
        return None

    placeholder_telegram_id = _site_placeholder_telegram_id_for_user(int(request.user.id))
    existing = BotUser.objects.filter(telegram_id=placeholder_telegram_id).first()
    desired_username = (request.user.username or "").strip() or None
    desired_first_name = (request.user.first_name or request.user.username or "").strip() or None
    if existing:
        update_fields: list[str] = []
        if existing.username != desired_username:
            existing.username = desired_username
            update_fields.append("username")
        if existing.first_name != desired_first_name:
            existing.first_name = desired_first_name
            update_fields.append("first_name")
        if update_fields:
            existing.save(update_fields=update_fields)
        return existing

    try:
        BotUser.objects.create(
            telegram_id=placeholder_telegram_id,
            client_code="",
            username=desired_username,
            first_name=desired_first_name,
            created_at=timezone.now(),
        )
    except IntegrityError:
        pass

    return BotUser.objects.filter(telegram_id=placeholder_telegram_id).first()


def _resolve_account_bot_user(
    request: HttpRequest,
    *,
    ensure_site_bot_user: bool = False,
) -> tuple[LinkedAccount | None, BotUser | None]:
    linked = LinkedAccount.objects.filter(user=request.user).first()
    if linked:
        bot_user = BotUser.objects.filter(telegram_id=linked.telegram_id).first()
        if bot_user is not None:
            return linked, bot_user

    placeholder_telegram_id = _site_placeholder_telegram_id_for_user(int(request.user.id))
    placeholder_user = BotUser.objects.filter(telegram_id=placeholder_telegram_id).first()
    if placeholder_user is not None:
        return linked, placeholder_user

    if ensure_site_bot_user:
        return linked, _ensure_site_bot_user(request)
    return linked, None


def _new_web_idempotency_key() -> str:
    return uuid.uuid4().hex


def _load_web_order_session_state(request: HttpRequest, *, user_id: int) -> dict[str, str]:
    raw_state = request.session.get(WEB_ORDER_SESSION_KEY)
    if not isinstance(raw_state, dict):
        return {"user_id": str(user_id), "idempotency_key": _new_web_idempotency_key()}
    if str(raw_state.get("user_id", "")) != str(user_id):
        return {"user_id": str(user_id), "idempotency_key": _new_web_idempotency_key()}
    idempotency_key = str(raw_state.get("idempotency_key", "")).strip()
    if not idempotency_key:
        raw_state["idempotency_key"] = _new_web_idempotency_key()
    return {
        "user_id": str(user_id),
        "idempotency_key": str(raw_state.get("idempotency_key")),
        "order_id": str(raw_state.get("order_id", "")),
        "pay_url": str(raw_state.get("pay_url", "")),
    }


def _save_web_order_session_state(
    request: HttpRequest,
    *,
    user_id: int,
    idempotency_key: str,
    order_id: int | None = None,
    pay_url: str | None = None,
) -> None:
    state: dict[str, str] = {
        "user_id": str(user_id),
        "idempotency_key": idempotency_key,
    }
    if order_id is not None:
        state["order_id"] = str(order_id)
    if pay_url:
        state["pay_url"] = pay_url
    request.session[WEB_ORDER_SESSION_KEY] = state
    request.session.modified = True


def _reference_checkout_url_from_order(order: BotOrder) -> str | None:
    if not order.card_payment_id:
        return None
    base_url = str(getattr(settings, "PAYMENT_REFERENCE_BASE_URL", "https://pay.vxcloud.ru/mock")).rstrip("/")
    query = urlencode(
        {
            "payment_id": order.card_payment_id,
            "order_id": order.id,
            "amount_minor": order.amount_minor or 0,
            "currency": order.currency_iso or order.currency or "RUB",
        }
    )
    return f"{base_url}/checkout?{query}"


def signup_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("account_dashboard")

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"].strip()
        email = form.cleaned_data["email"].strip().lower()
        password = form.cleaned_data["password"]
        if User.objects.filter(username=username).exists():
            form.add_error("username", "Пользователь с таким логином уже существует")
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            auth_user = authenticate(request, username=username, password=password)
            if auth_user:
                login(request, auth_user)
                return _account_redirect(request)
            return redirect("login")

    context = {"form": form}
    context.update(_account_template_urls(request))
    return render(request, "cabinet/signup.html", context)


@login_required
def account_dashboard(request: HttpRequest) -> HttpResponse:
    linked, bot_user = _resolve_account_bot_user(request, ensure_site_bot_user=True)
    sub, has_active, last_payment_method = _get_subscription_snapshot_for_bot_user(bot_user)
    subscriptions = _list_subscriptions_for_bot_user(bot_user)
    now = timezone.now()
    subscription_rows: list[dict[str, object]] = []
    for item in subscriptions:
        expires_at = getattr(item, "expires_at", None)
        is_active = bool(getattr(item, "is_active", False) and expires_at and expires_at > now and getattr(item, "revoked_at", None) is None)
        status_text = "Активна" if is_active else ("Отключена" if getattr(item, "revoked_at", None) else "Истекла")
        subscription_rows.append(
            {
                "obj": item,
                "id": int(item.id),
                "display_name": _subscription_display_name(item),
                "is_active": is_active,
                "status_text": status_text,
                "expires_at": expires_at,
            }
        )
    active_configs = sum(1 for row in subscription_rows if bool(row["is_active"]))
    inactive_configs = max(len(subscription_rows) - active_configs, 0)
    return render(
        request,
        "cabinet/dashboard.html",
        {
            "linked": linked,
            "bot_user": bot_user,
            "subscription": sub,
            "subscriptions": subscriptions,
            "has_active": has_active,
            "last_payment_method": last_payment_method,
            "card_price_label": _format_minor_amount_rub(settings.CARD_PAYMENT_AMOUNT_MINOR),
            "now": now,
            "subscription_rows": subscription_rows,
            "active_configs": active_configs,
            "inactive_configs": inactive_configs,
            **_account_template_urls(request),
        },
    )


@login_required
def link_telegram(request: HttpRequest) -> HttpResponse:
    linked = LinkedAccount.objects.filter(user=request.user).first()
    now = timezone.now()

    if request.method == "POST":
        TelegramLinkToken.objects.filter(user=request.user, consumed_at__isnull=True).delete()
        messages.info(request, "Создан новый код для привязки Telegram.")
        return _account_redirect(request, "link/")

    token = (
        TelegramLinkToken.objects.filter(
            user=request.user,
            consumed_at__isnull=True,
            expires_at__gt=now,
        )
        .order_by("-id")
        .first()
    )
    if token is None:
        token = TelegramLinkToken.objects.create(
            user=request.user,
            code=_generate_link_code(),
            expires_at=now + timedelta(minutes=20),
        )

    bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
    deep_link = f"https://t.me/{bot_username}?start=link_{token.code}" if bot_username else ""

    return render(
        request,
        "cabinet/link_telegram.html",
        {
            "linked": linked,
            "link_code": token.code,
            "deep_link": deep_link,
            "expires_at": token.expires_at,
            "bot_username": bot_username,
            **_account_template_urls(request),
        },
    )


def _generate_link_code(length: int = 12) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@login_required
def account_config(request: HttpRequest, subscription_id: int | None = None) -> HttpResponse:
    linked, bot_user = _resolve_account_bot_user(request, ensure_site_bot_user=True)
    if not bot_user:
        messages.error(request, "Не удалось загрузить данные аккаунта")
        return _account_redirect(request)

    sub, has_active, last_payment_method = _get_subscription_snapshot_for_bot_user(bot_user)
    subscriptions = _list_subscriptions_for_bot_user(bot_user)
    if subscription_id is not None:
        selected = next((s for s in subscriptions if int(s.id) == int(subscription_id)), None)
        if selected is None:
            messages.error(request, "Конфиг не найден")
            return _account_redirect(request)
        sub = selected
        has_active = bool(sub.is_active and sub.expires_at > timezone.now())
    if not sub:
        messages.error(request, "Подписка не найдена")
        return _account_redirect(request)

    qr_data = sub.vless_url
    img = qrcode.make(qr_data)
    buff = io.BytesIO()
    img.save(buff, format="PNG")
    qr_b64 = base64.b64encode(buff.getvalue()).decode("ascii")

    return render(
        request,
        "cabinet/config.html",
        {
            "subscription": sub,
            "subscriptions": subscriptions,
            "has_active": has_active,
            "last_payment_method": last_payment_method,
            "display_name": _subscription_display_name(sub),
            "qr_b64": qr_b64,
            "copy_text": qr_data,
            **_account_template_urls(request),
        },
    )


def _start_checkout_flow(
    request: HttpRequest,
    *,
    flow_mode: str,
    requested_subscription_id: int | None = None,
) -> tuple[str | None, str | None]:
    linked, bot_user = _resolve_account_bot_user(request, ensure_site_bot_user=True)
    if not bot_user:
        return None, "Не удалось подготовить аккаунт для оплаты. Попробуйте снова через 1-2 минуты."

    now = timezone.now()
    target_subscription_id: int | None = None
    if flow_mode == "renew":
        if requested_subscription_id is not None:
            candidate_id = int(requested_subscription_id)
            if BotSubscription.objects.filter(id=candidate_id, user_id=bot_user.id).exists():
                target_subscription_id = candidate_id
        if target_subscription_id is None:
            active_sub = (
                BotSubscription.objects.filter(user_id=bot_user.id, is_active=True, expires_at__gt=now)
                .order_by("-expires_at", "-id")
                .first()
            )
            if active_sub:
                target_subscription_id = int(active_sub.id)

    session_state = _load_web_order_session_state(request, user_id=bot_user.id)
    idempotency_key = str(session_state.get("idempotency_key") or "").strip() or _new_web_idempotency_key()
    pending_cutoff = now - timedelta(hours=1)

    pending_method = "card"
    pending_payload_prefix = (
        f"web-newcfg:{bot_user.id}:"
        if flow_mode == "buynew"
        else f"web-renew:{bot_user.id}:{int(target_subscription_id or 0)}:"
    )
    BotOrder.objects.filter(
        user_id=bot_user.id,
        status="pending",
        channel="web",
        payment_method=pending_method,
        payload__startswith=pending_payload_prefix,
        created_at__lt=pending_cutoff,
    ).update(status="cancelled")

    existing_pending = (
        BotOrder.objects.filter(
            user_id=bot_user.id,
            status="pending",
            channel="web",
            payment_method=pending_method,
            payload__startswith=pending_payload_prefix,
            created_at__gte=pending_cutoff,
        )
        .order_by("-id")
        .first()
    )
    if existing_pending:
        pay_url = str(session_state.get("pay_url") or "").strip()
        if not pay_url and str(settings.PAYMENT_PROVIDER).lower() == "reference":
            pay_url = _reference_checkout_url_from_order(existing_pending) or ""
        if not pay_url:
            provider_name = str(settings.PAYMENT_PROVIDER).lower()
            provider = get_payment_provider(provider_name=provider_name)
            try:
                create_result = provider.create_payment(
                    {
                        "id": int(existing_pending.id),
                        "user_id": int(bot_user.id),
                        "amount_minor": int(existing_pending.amount_minor or settings.CARD_PAYMENT_AMOUNT_MINOR),
                        "currency_iso": str(existing_pending.currency_iso or settings.CARD_PAYMENT_CURRENCY).upper(),
                        "idempotency_key": idempotency_key,
                    }
                )
                existing_pending.card_payment_id = create_result.payment_id
                existing_pending.save(update_fields=["card_payment_id"])
                pay_url = create_result.pay_url
            except Exception:
                return None, "Не удалось восстановить ссылку оплаты. Попробуйте снова через 1-2 минуты."
        if pay_url:
            _save_web_order_session_state(
                request,
                user_id=bot_user.id,
                idempotency_key=idempotency_key,
                order_id=int(existing_pending.id),
                pay_url=pay_url,
            )
            return pay_url, None

    used_non_pending = BotOrder.objects.filter(user_id=bot_user.id, idempotency_key=idempotency_key).exclude(status="pending").exists()
    if used_non_pending:
        idempotency_key = _new_web_idempotency_key()
        _save_web_order_session_state(request, user_id=bot_user.id, idempotency_key=idempotency_key)

    payload_prefix = "web-newcfg" if flow_mode == "buynew" else "web-renew"
    if flow_mode == "renew":
        payload = f"{payload_prefix}:{bot_user.id}:{int(target_subscription_id or 0)}:{int(datetime.now().timestamp())}:{uuid.uuid4().hex[:6]}"
    else:
        payload = f"{payload_prefix}:{bot_user.id}:{int(datetime.now().timestamp())}:{uuid.uuid4().hex[:6]}"
    amount_minor = int(settings.CARD_PAYMENT_AMOUNT_MINOR)
    currency_iso = str(settings.CARD_PAYMENT_CURRENCY).upper()
    provider_name = str(settings.PAYMENT_PROVIDER).lower()

    try:
        order = BotOrder.objects.create(
            user_id=bot_user.id,
            amount_stars=0,
            currency=currency_iso,
            payload=payload,
            status="pending",
            channel="web",
            payment_method="card",
            amount_minor=amount_minor,
            currency_iso=currency_iso,
            card_provider=provider_name,
            idempotency_key=idempotency_key,
            created_at=now,
        )
    except IntegrityError:
        # Another request likely created the same pending order or reused idempotency key.
        existing_pending = (
            BotOrder.objects.filter(
                user_id=bot_user.id,
                status="pending",
                channel="web",
                payment_method="card",
                payload__startswith=pending_payload_prefix,
                created_at__gte=pending_cutoff,
            )
            .order_by("-id")
            .first()
        )
        if existing_pending:
            pay_url = _reference_checkout_url_from_order(existing_pending) or ""
            if pay_url:
                _save_web_order_session_state(
                    request,
                    user_id=bot_user.id,
                    idempotency_key=str(existing_pending.idempotency_key or idempotency_key),
                order_id=int(existing_pending.id),
                pay_url=pay_url,
            )
                return pay_url, None
        return None, "Не удалось создать платеж. Попробуйте снова через 1-2 минуты."

    provider = get_payment_provider(provider_name=provider_name)
    try:
        create_result = provider.create_payment(
            {
                "id": order.id,
                "user_id": bot_user.id,
                "amount_minor": amount_minor,
                "currency_iso": currency_iso,
                "idempotency_key": idempotency_key,
            }
        )
    except Exception:
        return None, "Не удалось создать платеж. Попробуйте снова через 1-2 минуты."

    order.card_payment_id = create_result.payment_id
    order.save(update_fields=["card_payment_id"])
    _save_web_order_session_state(
        request,
        user_id=bot_user.id,
        idempotency_key=idempotency_key,
        order_id=int(order.id),
        pay_url=create_result.pay_url,
    )
    return create_result.pay_url, None


@login_required
def create_order_stub(request: HttpRequest) -> HttpResponse:
    is_buy_route = request.resolver_match and request.resolver_match.url_name == "account_buy"
    flow_mode = "buynew" if is_buy_route else "renew"
    requested_subscription_id_raw = (request.GET.get("subscription_id") or request.POST.get("subscription_id") or "").strip()
    requested_subscription_id = int(requested_subscription_id_raw) if requested_subscription_id_raw.isdigit() else None
    pay_url, error_message = _start_checkout_flow(
        request,
        flow_mode=flow_mode,
        requested_subscription_id=requested_subscription_id,
    )
    if error_message:
        messages.error(request, error_message)
        return _account_redirect(request)
    if not pay_url:
        messages.error(request, "Не удалось создать платеж. Попробуйте снова через 1-2 минуты.")
        return _account_redirect(request)
    return redirect(pay_url)


@ensure_csrf_cookie
def account_api_state(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return _json_error("Method not allowed", status=405)

    view_name = (request.GET.get("view") or "dashboard").strip().lower()
    subscription_id_raw = (request.GET.get("subscription_id") or "").strip()
    subscription_id = int(subscription_id_raw) if subscription_id_raw.isdigit() else None

    payload: dict[str, object] = {
        "ok": True,
        "authenticated": bool(request.user.is_authenticated),
        "csrf_token": get_token(request),
        "account_url": _account_frontend_url(),
        "password_reset_url": "/accounts/password_reset/",
    }

    if not request.user.is_authenticated:
        payload["view"] = "auth"
        payload["auth"] = {
            "title": "Вход",
            "subtitle": "Войдите в аккаунт, чтобы управлять доступами и конфигами.",
            "login_label": "Войти",
            "signup_label": "Регистрация",
            "forgot_password_label": "Забыли пароль?",
        }
        return JsonResponse(payload)

    if view_name == "config" and subscription_id is not None:
        config_payload, error_message = _build_config_payload(request, subscription_id)
        if error_message:
            return _json_error(error_message, status=404)
        payload["view"] = "config"
        payload["config"] = config_payload
        return JsonResponse(payload)

    payload["view"] = "dashboard"
    payload["dashboard"] = _build_dashboard_payload(request)
    return JsonResponse(payload)


@require_POST
def account_api_login(request: HttpRequest) -> JsonResponse:
    if request.user.is_authenticated:
        return JsonResponse({"ok": True})

    data = _json_body(request)
    form = EmailAuthenticationForm(
        request=request,
        data={
            "username": (data.get("username") or "").strip(),
            "password": data.get("password") or "",
        },
    )
    if not form.is_valid():
        return _json_error("Не удалось выполнить вход.", errors=_serialize_form_errors(form))

    user = form.get_user()
    if user is None:
        return _json_error("Не удалось выполнить вход.")

    login(request, user)
    return JsonResponse({"ok": True})


@require_POST
def account_api_signup(request: HttpRequest) -> JsonResponse:
    if request.user.is_authenticated:
        return JsonResponse({"ok": True})

    data = _json_body(request)
    form = SignUpForm(
        {
            "username": (data.get("username") or "").strip(),
            "email": (data.get("email") or "").strip(),
            "password": data.get("password") or "",
            "password_confirm": data.get("password_confirm") or "",
        }
    )
    if not form.is_valid():
        return _json_error("Не удалось создать аккаунт.", errors=_serialize_form_errors(form))

    username = form.cleaned_data["username"].strip()
    email = form.cleaned_data["email"].strip().lower()
    password = form.cleaned_data["password"]
    if User.objects.filter(username=username).exists():
        return _json_error("Не удалось создать аккаунт.", errors={"username": "Пользователь с таким логином уже существует"})

    user = User.objects.create_user(username=username, email=email, password=password)
    auth_user = authenticate(request, username=username, password=password)
    if auth_user is None:
        return _json_error("Аккаунт создан, но не удалось выполнить вход.", status=500)

    login(request, auth_user)
    return JsonResponse({"ok": True})


@require_POST
def account_api_buy(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return _json_error("Требуется вход в аккаунт.", status=401)

    pay_url, error_message = _start_checkout_flow(request, flow_mode="buynew")
    if error_message:
        return _json_error(error_message)
    return JsonResponse({"ok": True, "redirect_url": pay_url})


@require_POST
def account_api_renew(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return _json_error("Требуется вход в аккаунт.", status=401)

    data = _json_body(request)
    subscription_id_raw = str(data.get("subscription_id") or "").strip()
    subscription_id = int(subscription_id_raw) if subscription_id_raw.isdigit() else None
    pay_url, error_message = _start_checkout_flow(
        request,
        flow_mode="renew",
        requested_subscription_id=subscription_id,
    )
    if error_message:
        return _json_error(error_message)
    return JsonResponse({"ok": True, "redirect_url": pay_url})


@login_required
@require_POST
def rename_subscription(request: HttpRequest, subscription_id: int) -> HttpResponse:
    linked, bot_user = _resolve_account_bot_user(request, ensure_site_bot_user=True)
    if not bot_user:
        messages.error(request, "Не удалось загрузить данные аккаунта.")
        return _redirect_after_account_post(request)

    subscription = BotSubscription.objects.filter(id=subscription_id, user_id=bot_user.id).first()
    if not subscription:
        messages.error(request, "Конфиг не найден.")
        return _redirect_after_account_post(request)

    new_name = (request.POST.get("display_name") or "").strip()
    if not new_name:
        messages.error(request, "Введите имя конфига.")
        return _redirect_after_account_post(request)

    subscription.display_name = new_name[:80]
    subscription.updated_at = timezone.now()
    subscription.save(update_fields=["display_name", "updated_at"])
    messages.success(request, "Имя конфига обновлено.")
    return _redirect_after_account_post(request)


@login_required
@require_POST
def revoke_subscription(request: HttpRequest, subscription_id: int) -> HttpResponse:
    linked, bot_user = _resolve_account_bot_user(request, ensure_site_bot_user=True)
    if not bot_user:
        messages.error(request, "Не удалось загрузить данные аккаунта.")
        return _account_redirect(request)

    subscription = BotSubscription.objects.filter(id=subscription_id, user_id=bot_user.id).first()
    if not subscription:
        messages.error(request, "Конфиг не найден.")
        return _account_redirect(request)

    now = timezone.now()
    subscription.is_active = False
    subscription.revoked_at = now
    subscription.updated_at = now
    subscription.save(update_fields=["is_active", "revoked_at", "updated_at"])
    messages.success(request, "Конфиг отключен.")
    return _account_redirect(request)


def open_app_link(request: HttpRequest) -> HttpResponse:
    raw = (request.GET.get("u") or "").strip()
    deeplink = unquote(raw)
    if not any(deeplink.startswith(prefix) for prefix in ALLOWED_DEEPLINK_SCHEMES):
        deeplink = ""
    return render(request, "cabinet/open_app.html", {"deeplink": deeplink})


def tg_magic_login(request: HttpRequest, token: str) -> HttpResponse:
    if request.method != "GET":
        return HttpResponse(status=405)

    now = timezone.now()
    with transaction.atomic():
        login_token = (
            WebLoginToken.objects.select_for_update()
            .filter(token=token)
            .first()
        )
        if not login_token:
            return HttpResponse("Invalid token", status=404)
        if login_token.consumed_at is not None:
            return HttpResponse("Token already used", status=410)
        if login_token.expires_at <= now:
            return HttpResponse("Token expired", status=410)

        linked = LinkedAccount.objects.select_related("user").filter(telegram_id=login_token.telegram_id).first()
        if linked:
            user = linked.user
        else:
            user = _create_user_for_telegram(login_token.telegram_id)
            LinkedAccount.objects.create(user=user, telegram_id=login_token.telegram_id)

        login_token.consumed_at = now
        login_token.save(update_fields=["consumed_at"])

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("/account/")


def _create_user_for_telegram(telegram_id: int) -> User:
    base_username = f"tg_{telegram_id}"
    username = base_username
    suffix = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}_{suffix}"
        suffix += 1

    user = User(username=username)
    user.set_unusable_password()
    user.save()
    return user


@csrf_exempt
def create_magic_link(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)

    configured_secret = settings.MAGIC_LINK_SHARED_SECRET.strip()
    incoming_secret = (request.headers.get("X-Shared-Secret") or "").strip()
    if not configured_secret or incoming_secret != configured_secret:
        return JsonResponse({"error": "forbidden"}, status=403)

    if _is_magic_link_rate_limited(request):
        return JsonResponse({"error": "rate_limited"}, status=429)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)

    telegram_id_raw = payload.get("telegram_id")
    bot_user_id_raw = payload.get("bot_user_id")

    telegram_user_id: int | None = None
    bot_user_id: int | None = None

    if telegram_id_raw is not None:
        try:
            telegram_user_id = int(telegram_id_raw)
        except Exception:
            return JsonResponse({"error": "invalid_telegram_id"}, status=400)

    if bot_user_id_raw is not None:
        try:
            bot_user_id = int(bot_user_id_raw)
        except Exception:
            return JsonResponse({"error": "invalid_bot_user_id"}, status=400)

    if telegram_user_id is None and bot_user_id is not None:
        bot_user = BotUser.objects.filter(pk=bot_user_id).first()
        if bot_user is None:
            return JsonResponse({"error": "bot_user_not_found"}, status=404)
        telegram_value = getattr(bot_user, "telegram_id", None)
        if telegram_value is None:
            return JsonResponse({"error": "bot_user_has_no_telegram_id"}, status=400)
        telegram_user_id = int(telegram_value)

    if telegram_user_id is None:
        return JsonResponse({"error": "invalid_telegram_id"}, status=400)

    now = timezone.now()
    expires_at = now + timedelta(seconds=max(60, settings.MAGIC_LINK_TTL_SECONDS))
    token = _generate_magic_token()
    WebLoginToken.objects.create(
        token=token,
        telegram_id=telegram_user_id,
        expires_at=expires_at,
        consumed_at=None,
        created_at=now,
    )

    url = settings.ACCOUNT_MAGIC_URL_TEMPLATE.format(token=token)
    return JsonResponse({"url": url})


@csrf_exempt
def telegram_webapp_auth(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)

    init_data = str(payload.get("initData", "") or "").strip()
    if not init_data:
        return JsonResponse({"error": "missing_init_data"}, status=400)

    bot_token = settings.TELEGRAM_WEBAPP_BOT_TOKEN.strip()
    if not bot_token:
        return JsonResponse({"error": "server_not_configured"}, status=500)

    try:
        parsed_pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return JsonResponse({"error": "invalid_init_data_format"}, status=400)

    parsed: dict[str, str] = {}
    for k, v in parsed_pairs:
        if k in parsed:
            return JsonResponse({"error": "duplicate_init_data_key"}, status=400)
        parsed[k] = v

    received_hash = str(parsed.pop("hash", "")).strip().lower()
    if not received_hash:
        return JsonResponse({"error": "missing_hash"}, status=400)
    if len(received_hash) != 64 or any(ch not in "0123456789abcdef" for ch in received_hash):
        return JsonResponse({"error": "invalid_hash_format"}, status=400)

    auth_date_raw = parsed.get("auth_date", "")
    try:
        auth_date = int(auth_date_raw)
    except Exception:
        return JsonResponse({"error": "invalid_auth_date"}, status=400)

    now_ts = int(timezone.now().timestamp())
    max_age = max(30, int(settings.TELEGRAM_WEBAPP_AUTH_MAX_AGE_SECONDS))
    if auth_date > now_ts + 30 or (now_ts - auth_date) > max_age:
        return JsonResponse({"error": "auth_data_expired"}, status=401)

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        return JsonResponse({"error": "invalid_signature"}, status=401)

    user_raw = parsed.get("user")
    if not user_raw:
        return JsonResponse({"error": "missing_user"}, status=400)

    try:
        user_data = json.loads(user_raw)
        telegram_id = int(user_data["id"])
    except Exception:
        return JsonResponse({"error": "invalid_user_payload"}, status=400)

    linked = LinkedAccount.objects.select_related("user").filter(telegram_id=telegram_id).first()
    if linked:
        user = linked.user
    else:
        user = _create_user_for_telegram(telegram_id)
        LinkedAccount.objects.create(user=user, telegram_id=telegram_id)

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse({"ok": True, "redirect": "/account/"})


def _generate_magic_token() -> str:
    while True:
        token = secrets.token_urlsafe(32)
        if not WebLoginToken.objects.filter(token=token).exists():
            return token


def _is_rate_limited(request: HttpRequest, *, key_prefix: str, limit_per_minute: int, suffix: str = "") -> bool:
    limit = max(1, int(limit_per_minute))
    ip = (request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "unknown").split(",")[0].strip()
    key = f"{key_prefix}:{ip}"
    if suffix:
        key = f"{key}:{suffix}"
    count = cache.get(key, 0)
    if count >= limit:
        return True
    if count == 0:
        cache.set(key, 1, timeout=60)
    else:
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, count + 1, timeout=60)
    return False


def _is_magic_link_rate_limited(request: HttpRequest) -> bool:
    return _is_rate_limited(
        request,
        key_prefix="magic_link_rl",
        limit_per_minute=settings.MAGIC_LINK_RATE_LIMIT_PER_MINUTE,
    )


def _is_webhook_rate_limited(request: HttpRequest, provider: str) -> bool:
    return _is_rate_limited(
        request,
        key_prefix="webhook_rl",
        limit_per_minute=settings.WEBHOOK_RATE_LIMIT_PER_MINUTE,
        suffix=provider,
    )


@csrf_exempt
def payment_webhook(request: HttpRequest, provider: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)

    provider_name = (provider or "").strip().lower()
    if not provider_name:
        return JsonResponse({"error": "invalid_provider"}, status=400)
    if _is_webhook_rate_limited(request, provider_name):
        _log_payment_event(
            order_id=None,
            client_code=None,
            provider=provider_name,
            event_id=None,
            provision_state="webhook_rate_limited",
        )
        return JsonResponse({"error": "rate_limited"}, status=429)

    try:
        payment_provider = get_payment_provider(provider_name=provider_name)
        webhook = payment_provider.verify_webhook(request)
    except Exception:
        _log_payment_event(
            order_id=None,
            client_code=None,
            provider=provider_name,
            event_id=None,
            provision_state="webhook_invalid",
        )
        return JsonResponse({"error": "invalid_webhook"}, status=400)

    if not webhook.event_id:
        _log_payment_event(
            order_id=None,
            client_code=None,
            provider=provider_name,
            event_id=None,
            provision_state="webhook_missing_event_id",
        )
        return JsonResponse({"error": "invalid_webhook_event_id"}, status=400)

    now = timezone.now()
    order_id_for_activation: int | None = None
    payload = dict(webhook.provider_payload or {})
    if not payload:
        payload = {"raw_body": (request.body or b"").decode("utf-8", errors="replace")}

    with transaction.atomic():
        try:
            PaymentEvent.objects.create(
                provider=provider_name,
                event_id=webhook.event_id,
                body=payload,
                created_at=now,
                processed_at=None,
            )
        except IntegrityError:
            _log_payment_event(
                order_id=None,
                client_code=None,
                provider=provider_name,
                event_id=webhook.event_id,
                provision_state="webhook_duplicate",
            )
            return JsonResponse({"ok": True, "duplicate": True}, status=200)

        status = str(webhook.status or "").strip().lower()
        if status in PAYMENT_SUCCESS_STATUSES:
            order = (
                BotOrder.objects.select_for_update()
                .filter(card_payment_id=webhook.payment_id)
                .first()
            )
            if order and str(order.status).lower() == "pending":
                order.status = "paid"
                order.paid_at = now
                order.provider_payment_charge_id = webhook.payment_id
                order.save(update_fields=["status", "paid_at", "provider_payment_charge_id"])
                order_id_for_activation = int(order.id)
                _log_payment_event(
                    order_id=order_id_for_activation,
                    client_code=getattr(order.user, "client_code", None),
                    provider=provider_name,
                    event_id=webhook.event_id,
                    provision_state="paid_marked",
                )
            elif order:
                _log_payment_event(
                    order_id=int(order.id),
                    client_code=getattr(order.user, "client_code", None),
                    provider=provider_name,
                    event_id=webhook.event_id,
                    provision_state="already_paid_or_processing",
                )
            else:
                _log_payment_event(
                    order_id=None,
                    client_code=None,
                    provider=provider_name,
                    event_id=webhook.event_id,
                    provision_state="order_not_found",
                )
        else:
            _log_payment_event(
                order_id=None,
                client_code=None,
                provider=provider_name,
                event_id=webhook.event_id,
                provision_state=f"webhook_ignored_status_{status or 'unknown'}",
            )

        PaymentEvent.objects.filter(provider=provider_name, event_id=webhook.event_id).update(processed_at=now)

    if order_id_for_activation is not None:
        _log_payment_event(
            order_id=order_id_for_activation,
            client_code=None,
            provider=provider_name,
            event_id=webhook.event_id,
            provision_state="activation_worker_spawned",
        )
        _spawn_activation_worker(order_id_for_activation)

    return JsonResponse({"ok": True}, status=200)


def _spawn_activation_worker(order_id: int) -> None:
    thread = threading.Thread(
        target=_run_activation_worker_sync,
        args=(order_id,),
        daemon=True,
        name=f"activate-order-{order_id}",
    )
    thread.start()


def _run_activation_worker_sync(order_id: int) -> None:
    try:
        asyncio.run(_activate_order_async(order_id))
    except Exception:
        LOGGER.exception("Failed to run activation worker for order_id=%s", order_id)


async def _activate_order_async(order_id: int) -> None:
    project_root = Path(__file__).resolve().parents[2]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.append(project_root_str)

    from src.config import load_settings
    from src.db import DB
    from src.domain.subscriptions import activate_subscription
    from src.xui_client import XUIClient

    app_settings = load_settings()
    db = DB(app_settings.database_url)
    xui = XUIClient(app_settings.xui_base_url, app_settings.xui_username, app_settings.xui_password)
    try:
        await db.connect()
        await xui.start()
        order = await db.get_order_by_id(order_id)
        provider = str((order or {}).get("card_provider") or (order or {}).get("payment_method") or "card")
        event_id = str((order or {}).get("provider_payment_charge_id") or "")
        user_id = int((order or {}).get("user_id") or 0)
        client_code = await db.get_user_client_code(user_id) if user_id else None
        _log_payment_event(
            order_id=order_id,
            client_code=client_code,
            provider=provider,
            event_id=event_id,
            provision_state="activation_started",
        )
        result = await activate_subscription(order_id, db=db, xui=xui, settings=app_settings)
        paid_to_ready_ms: int | None = None
        paid_at = (order or {}).get("paid_at")
        if isinstance(paid_at, datetime):
            paid_to_ready_ms = max(0, int((timezone.now() - paid_at).total_seconds() * 1000))
        _log_payment_event(
            order_id=order_id,
            client_code=client_code,
            provider=provider,
            event_id=event_id,
            provision_state="provision_ready",
            paid_to_ready_ms=paid_to_ready_ms,
        )
        await _notify_user_after_card_activation(
            db=db,
            order_id=order_id,
            telegram_bot_token=app_settings.telegram_bot_token,
            user_id=result.user_id,
        )
    except Exception:
        _log_payment_event(
            order_id=order_id,
            client_code=None,
            provider="card",
            event_id="",
            provision_state="provision_failed",
        )
        raise
    finally:
        await xui.close()
        await db.close()


async def _notify_user_after_card_activation(
    *,
    db,
    order_id: int,
    telegram_bot_token: str,
    user_id: int,
) -> None:
    if not telegram_bot_token:
        return

    telegram_id = await db.get_user_telegram_id(user_id)
    if telegram_id is None or int(telegram_id) <= 0:
        return

    is_first_notification = await db.mark_order_notified_if_pending(order_id)
    if not is_first_notification:
        return

    message_text = "Оплата получена, подписка активирована"
    await asyncio.to_thread(
        _send_telegram_message_sync,
        telegram_bot_token,
        telegram_id,
        message_text,
    )


def _send_telegram_message_sync(token: str, chat_id: int, text: str) -> None:
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urlencode({"chat_id": str(chat_id), "text": text}).encode("utf-8")
    request = Request(api_url, data=body, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urlopen(request, timeout=10):
        return
