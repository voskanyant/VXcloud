from __future__ import annotations

import base64
import io
import os
import uuid
from datetime import datetime

import qrcode
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import LinkTelegramForm, SignUpForm
from .models import BotOrder, BotSubscription, BotUser, LinkedAccount


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
    form = LinkTelegramForm(request.POST or None, initial={"telegram_id": linked.telegram_id if linked else None})

    if request.method == "POST" and form.is_valid():
        telegram_id = form.cleaned_data["telegram_id"]
        bot_user = BotUser.objects.filter(telegram_id=telegram_id).first()
        if not bot_user:
            form.add_error("telegram_id", "Такой Telegram ID не найден в базе бота")
        else:
            LinkedAccount.objects.update_or_create(user=request.user, defaults={"telegram_id": telegram_id})
            messages.success(request, "Telegram аккаунт привязан")
            return redirect("account_dashboard")

    return render(request, "cabinet/link_telegram.html", {"form": form})


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
