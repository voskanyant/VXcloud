from __future__ import annotations

import base64
import io
import os
import secrets
import string
import uuid
from datetime import datetime, timedelta
from urllib.parse import unquote

import qrcode
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import SignUpForm
from .models import BotOrder, BotSubscription, BotUser, LinkedAccount, TelegramLinkToken


ALLOWED_DEEPLINK_SCHEMES = ("vless://", "vmess://", "trojan://", "ss://", "hysteria2://", "tuic://")


def signup_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("account_dashboard")

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"].strip()
        password = form.cleaned_data["password"]
        if User.objects.filter(username=username).exists():
            form.add_error("username", "Пользователь с таким логином уже существует")
        else:
            user = User.objects.create_user(username=username, password=password)
            auth_user = authenticate(request, username=username, password=password)
            if auth_user:
                login(request, auth_user)
                return redirect("account_dashboard")
            return redirect("login")

    return render(request, "cabinet/signup.html", {"form": form})


@login_required
def account_dashboard(request: HttpRequest) -> HttpResponse:
    linked = LinkedAccount.objects.filter(user=request.user).first()
    bot_user = None
    sub = None
    if linked:
        bot_user = BotUser.objects.filter(telegram_id=linked.telegram_id).first()
        if bot_user:
            sub = BotSubscription.objects.filter(user_id=bot_user.id).order_by("-id").first()

    now = timezone.now()
    has_active = bool(sub and sub.is_active and sub.expires_at > now)
    return render(
        request,
        "cabinet/dashboard.html",
        {
            "linked": linked,
            "bot_user": bot_user,
            "subscription": sub,
            "has_active": has_active,
            "now": now,
        },
    )


@login_required
def link_telegram(request: HttpRequest) -> HttpResponse:
    linked = LinkedAccount.objects.filter(user=request.user).first()
    now = timezone.now()

    if request.method == "POST":
        TelegramLinkToken.objects.filter(user=request.user, consumed_at__isnull=True).delete()
        messages.info(request, "Создан новый код для привязки Telegram.")
        return redirect("account_link")

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
        },
    )


def _generate_link_code(length: int = 12) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@login_required
def account_config(request: HttpRequest) -> HttpResponse:
    linked = LinkedAccount.objects.filter(user=request.user).first()
    if not linked:
        messages.error(request, "Сначала привяжите Telegram ID")
        return redirect("account_link")

    bot_user = BotUser.objects.filter(telegram_id=linked.telegram_id).first()
    if not bot_user:
        messages.error(request, "Пользователь бота не найден")
        return redirect("account_link")

    sub = BotSubscription.objects.filter(user_id=bot_user.id).order_by("-id").first()
    if not sub:
        messages.error(request, "Подписка не найдена")
        return redirect("account_dashboard")

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
            "qr_b64": qr_b64,
            "copy_text": qr_data,
        },
    )


@login_required
def create_order_stub(request: HttpRequest) -> HttpResponse:
    linked = LinkedAccount.objects.filter(user=request.user).first()
    if not linked:
        messages.error(request, "Сначала привяжите Telegram ID")
        return redirect("account_link")

    bot_user = BotUser.objects.filter(telegram_id=linked.telegram_id).first()
    if not bot_user:
        messages.error(request, "Пользователь бота не найден")
        return redirect("account_link")

    amount = int(os.getenv("PLAN_PRICE_STARS", "10"))
    payload = f"web-buy:{bot_user.id}:{int(datetime.now().timestamp())}:{uuid.uuid4().hex[:6]}"
    BotOrder.objects.create(
        user_id=bot_user.id,
        amount_stars=amount,
        currency="XTR",
        payload=payload,
        status="pending",
        created_at=timezone.now(),
    )
    messages.success(
        request,
        "Заявка на оплату создана. Сейчас оплата на сайте не подключена: завершите оплату через Telegram-бота.",
    )
    return redirect("account_dashboard")


def open_app_link(request: HttpRequest) -> HttpResponse:
    raw = (request.GET.get("u") or "").strip()
    deeplink = unquote(raw)
    if not any(deeplink.startswith(prefix) for prefix in ALLOWED_DEEPLINK_SCHEMES):
        deeplink = ""
    return render(request, "cabinet/open_app.html", {"deeplink": deeplink})
