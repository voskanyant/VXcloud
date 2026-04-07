from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.db.models import Q, QuerySet
from django.db.utils import OperationalError, ProgrammingError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from blog.admin import BLOCK_EDITOR_ASSET_VERSION
from blog.models import Category, Page, Post, PostType, SiteText
from cabinet.models import BotOrder, BotSubscription, BotUser

from .forms import (
    BackofficeCategoryForm,
    BackofficePageForm,
    BackofficePostForm,
    BackofficePostTypeForm,
    BackofficeSiteTextForm,
    StaffAuthenticationForm,
)

LEGACY_CONTENT_NOTICE = (
    "Публичный контент переносится в WordPress + Flatsome. "
    "Этот раздел больше не является целевой CMS для сайта."
)


class StaffRequiredMixin:
    login_url = reverse_lazy("backoffice:login")

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return redirect(f"{self.login_url}?next={request.path}")
        if not request.user.is_staff:
            raise PermissionDenied("Доступ только для staff")
        return super().dispatch(request, *args, **kwargs)


class LegacyContentContextMixin:
    content_management = False

    def is_content_readonly(self) -> bool:
        return self.content_management and settings.WORDPRESS_CONTENT_READONLY

    def get_wordpress_notice(self) -> str:
        return LEGACY_CONTENT_NOTICE if self.content_management else ""

    def add_wordpress_context(self, ctx: dict[str, Any]) -> dict[str, Any]:
        ctx["wordpress_notice"] = self.get_wordpress_notice()
        ctx["wordpress_public_site_enabled"] = settings.WORDPRESS_PUBLIC_SITE_ENABLED
        ctx["wordpress_content_readonly"] = self.is_content_readonly()
        ctx["wordpress_public_site_url"] = settings.WORDPRESS_PUBLIC_SITE_URL or "/"
        return ctx


class LegacyContentMutationGuardMixin(LegacyContentContextMixin):
    success_url_name = ""

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if self.is_content_readonly():
            messages.warning(request, "Редактирование legacy CMS отключено. Вносите публичный контент в WordPress.")
            return redirect(reverse(self.success_url_name))
        return super().dispatch(request, *args, **kwargs)


class BackofficeLoginView(LoginView):
    template_name = "backoffice/login.html"
    authentication_form = StaffAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self) -> str:
        return self.get_redirect_url() or reverse("backoffice:dashboard")


class BackofficeLogoutView(LogoutView):
    next_page = reverse_lazy("backoffice:login")


def safe_count(qs: QuerySet) -> int:
    try:
        return qs.count()
    except (OperationalError, ProgrammingError):
        return 0


def format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if hasattr(value, "isoformat") and hasattr(value, "tzinfo"):
        try:
            value = timezone.localtime(value)
        except Exception:
            pass
        return value.strftime("%d.%m.%Y %H:%M")
    return str(value)


class DashboardView(StaffRequiredMixin, TemplateView):
    template_name = "backoffice/dashboard.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Ops Panel"
        ctx["wordpress_notice"] = LEGACY_CONTENT_NOTICE
        ctx["wordpress_public_site_enabled"] = settings.WORDPRESS_PUBLIC_SITE_ENABLED
        ctx["wordpress_content_readonly"] = settings.WORDPRESS_CONTENT_READONLY
        ctx["wordpress_public_site_url"] = settings.WORDPRESS_PUBLIC_SITE_URL or "/"
        ctx["metrics"] = [
            {"label": "Страницы", "value": safe_count(Page.objects.all())},
            {"label": "Посты", "value": safe_count(Post.objects.all())},
            {"label": "Категории", "value": safe_count(Category.objects.all())},
            {"label": "Типы постов", "value": safe_count(PostType.objects.all())},
            {"label": "Тексты сайта", "value": safe_count(SiteText.objects.all())},
            {"label": "Пользователи бота", "value": safe_count(BotUser.objects.all())},
            {
                "label": "Активные подписки",
                "value": safe_count(BotSubscription.objects.filter(is_active=True)),
            },
            {"label": "Заказы", "value": safe_count(BotOrder.objects.all())},
        ]
        try:
            ctx["recent_pages"] = Page.objects.order_by("-updated_at")[:7]
        except (OperationalError, ProgrammingError):
            ctx["recent_pages"] = []
        try:
            ctx["recent_posts"] = Post.objects.order_by("-updated_at")[:7]
        except (OperationalError, ProgrammingError):
            ctx["recent_posts"] = []
        return ctx


class BaseListView(LegacyContentContextMixin, StaffRequiredMixin, ListView):
    template_name = "backoffice/list.html"
    paginate_by = 25
    context_object_name = "items"

    title = ""
    add_url_name = ""
    edit_url_name = ""
    delete_url_name = ""
    columns: list[tuple[str, str]] = []
    search_fields: list[str] = []
    readonly = False

    def get_queryset(self):
        try:
            qs = super().get_queryset()
            query = (self.request.GET.get("q") or "").strip()
            if query and self.search_fields:
                where = Q()
                for field in self.search_fields:
                    where |= Q(**{f"{field}__icontains": query})
                qs = qs.filter(where)
            return qs
        except (OperationalError, ProgrammingError):
            return self.model.objects.none()

    def get_table_rows(self) -> list[dict[str, Any]]:
        rows = []
        for item in self.object_list:
            cells = [format_cell(getattr(item, field, "")) for field, _ in self.columns]
            rows.append({"obj": item, "cells": cells})
        return rows

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = self.title
        ctx["query"] = (self.request.GET.get("q") or "").strip()
        ctx["headers"] = [label for _, label in self.columns]
        ctx["rows"] = self.get_table_rows()
        ctx["add_url_name"] = self.add_url_name
        ctx["edit_url_name"] = self.edit_url_name
        ctx["delete_url_name"] = self.delete_url_name
        ctx["readonly"] = self.readonly or self.is_content_readonly()
        return self.add_wordpress_context(ctx)


class PostListView(BaseListView):
    model = Post
    title = "Посты"
    add_url_name = "backoffice:post_create"
    edit_url_name = "backoffice:post_update"
    delete_url_name = "backoffice:post_delete"
    columns = [
        ("id", "ID"),
        ("title", "Заголовок"),
        ("slug", "Slug"),
        ("is_published", "Опубликован"),
        ("published_at", "Дата публикации"),
        ("updated_at", "Обновлён"),
    ]
    search_fields = ["title", "slug", "summary"]
    content_management = True

    def get_queryset(self):
        return super().get_queryset().order_by("-published_at", "-id")


class PageListView(BaseListView):
    model = Page
    title = "Страницы"
    add_url_name = "backoffice:page_create"
    edit_url_name = "backoffice:page_update"
    delete_url_name = "backoffice:page_delete"
    columns = [
        ("id", "ID"),
        ("title", "Заголовок"),
        ("path", "Путь"),
        ("is_published", "Опубликована"),
        ("show_in_nav", "В меню"),
        ("updated_at", "Обновлена"),
    ]
    search_fields = ["title", "slug", "path", "summary"]
    content_management = True

    def get_queryset(self):
        return super().get_queryset().order_by("nav_order", "title")


class CategoryListView(BaseListView):
    model = Category
    title = "Категории"
    add_url_name = "backoffice:category_create"
    edit_url_name = "backoffice:category_update"
    delete_url_name = "backoffice:category_delete"
    columns = [
        ("id", "ID"),
        ("title", "Название"),
        ("slug", "Slug"),
        ("is_active", "Активна"),
        ("updated_at", "Обновлена"),
    ]
    search_fields = ["title", "slug"]
    content_management = True


class PostTypeListView(BaseListView):
    model = PostType
    title = "Типы постов"
    add_url_name = "backoffice:post_type_create"
    edit_url_name = "backoffice:post_type_update"
    delete_url_name = "backoffice:post_type_delete"
    columns = [
        ("id", "ID"),
        ("title", "Название"),
        ("slug", "Slug"),
        ("is_active", "Активен"),
        ("updated_at", "Обновлён"),
    ]
    search_fields = ["title", "slug"]
    content_management = True


class SiteTextListView(BaseListView):
    model = SiteText
    title = "Тексты сайта"
    add_url_name = "backoffice:site_text_create"
    edit_url_name = "backoffice:site_text_update"
    delete_url_name = "backoffice:site_text_delete"
    columns = [
        ("id", "ID"),
        ("key", "Ключ"),
        ("updated_at", "Обновлён"),
    ]
    search_fields = ["key", "value"]
    content_management = True


class BotUserListView(BaseListView):
    model = BotUser
    title = "Пользователи бота"
    readonly = True
    columns = [
        ("id", "ID"),
        ("telegram_id", "Telegram ID"),
        ("username", "Username"),
        ("first_name", "Имя"),
        ("created_at", "Создан"),
    ]
    search_fields = ["telegram_id", "username", "first_name", "client_code"]

    def get_queryset(self):
        return super().get_queryset().order_by("-id")


class BotSubscriptionListView(BaseListView):
    model = BotSubscription
    title = "Подписки бота"
    readonly = True
    columns = [
        ("id", "ID"),
        ("user_id", "User ID"),
        ("display_name", "Имя"),
        ("is_active", "Активна"),
        ("expires_at", "Истекает"),
        ("updated_at", "Обновлена"),
    ]
    search_fields = ["display_name", "client_email"]

    def get_queryset(self):
        return super().get_queryset().order_by("-id")


class BotOrderListView(BaseListView):
    model = BotOrder
    title = "Заказы бота"
    readonly = True
    columns = [
        ("id", "ID"),
        ("user_id", "User ID"),
        ("username", "Username"),
        ("amount_stars", "Stars"),
        ("status", "Статус"),
        ("created_at", "Создан"),
        ("paid_at", "Оплачен"),
    ]
    search_fields = ["payload", "status", "telegram_payment_charge_id", "provider_payment_charge_id", "user__username", "user__first_name"]

    def get_queryset(self):
        return super().get_queryset().select_related("user").order_by("-id")

    def get_table_rows(self) -> list[dict[str, Any]]:
        rows = []
        for item in self.object_list:
            username = getattr(getattr(item, "user", None), "username", "") or ""
            cells = [
                format_cell(getattr(item, "id", "")),
                format_cell(getattr(item, "user_id", "")),
                format_cell(username),
                format_cell(getattr(item, "amount_stars", "")),
                format_cell(getattr(item, "status", "")),
                format_cell(getattr(item, "created_at", "")),
                format_cell(getattr(item, "paid_at", "")),
            ]
            rows.append({"obj": item, "cells": cells})
        return rows


class BaseEditView(LegacyContentMutationGuardMixin, StaffRequiredMixin):
    template_name = "backoffice/form.html"
    success_url_name = ""
    title_create = "Создать"
    title_update = "Редактировать"

    def get_success_url(self):
        return reverse(self.success_url_name)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = self.title_update if getattr(self, "object", None) else self.title_create
        ctx["block_editor_asset_version"] = BLOCK_EDITOR_ASSET_VERSION
        return self.add_wordpress_context(ctx)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Сохранено")
        return response


class LegacyContentDeleteView(LegacyContentMutationGuardMixin, StaffRequiredMixin, DeleteView):
    content_management = True


class PostCreateView(BaseEditView, CreateView):
    model = Post
    form_class = BackofficePostForm
    success_url_name = "backoffice:post_list"
    title_create = "Новый пост"
    content_management = True


class PostUpdateView(BaseEditView, UpdateView):
    model = Post
    form_class = BackofficePostForm
    success_url_name = "backoffice:post_list"
    title_update = "Редактирование поста"
    content_management = True


class PostDeleteView(LegacyContentDeleteView):
    model = Post
    template_name = "backoffice/confirm_delete.html"
    success_url_name = "backoffice:post_list"
    success_url = reverse_lazy("backoffice:post_list")


class PageCreateView(BaseEditView, CreateView):
    model = Page
    form_class = BackofficePageForm
    success_url_name = "backoffice:page_list"
    title_create = "Новая страница"
    content_management = True


class PageUpdateView(BaseEditView, UpdateView):
    model = Page
    form_class = BackofficePageForm
    success_url_name = "backoffice:page_list"
    title_update = "Редактирование страницы"
    content_management = True


class PageDeleteView(LegacyContentDeleteView):
    model = Page
    template_name = "backoffice/confirm_delete.html"
    success_url_name = "backoffice:page_list"
    success_url = reverse_lazy("backoffice:page_list")


class CategoryCreateView(BaseEditView, CreateView):
    model = Category
    form_class = BackofficeCategoryForm
    success_url_name = "backoffice:category_list"
    title_create = "Новая категория"
    content_management = True


class CategoryUpdateView(BaseEditView, UpdateView):
    model = Category
    form_class = BackofficeCategoryForm
    success_url_name = "backoffice:category_list"
    title_update = "Редактирование категории"
    content_management = True


class CategoryDeleteView(LegacyContentDeleteView):
    model = Category
    template_name = "backoffice/confirm_delete.html"
    success_url_name = "backoffice:category_list"
    success_url = reverse_lazy("backoffice:category_list")


class PostTypeCreateView(BaseEditView, CreateView):
    model = PostType
    form_class = BackofficePostTypeForm
    success_url_name = "backoffice:post_type_list"
    title_create = "Новый тип поста"
    content_management = True


class PostTypeUpdateView(BaseEditView, UpdateView):
    model = PostType
    form_class = BackofficePostTypeForm
    success_url_name = "backoffice:post_type_list"
    title_update = "Редактирование типа поста"
    content_management = True


class PostTypeDeleteView(LegacyContentDeleteView):
    model = PostType
    template_name = "backoffice/confirm_delete.html"
    success_url_name = "backoffice:post_type_list"
    success_url = reverse_lazy("backoffice:post_type_list")


class SiteTextCreateView(BaseEditView, CreateView):
    model = SiteText
    form_class = BackofficeSiteTextForm
    success_url_name = "backoffice:site_text_list"
    title_create = "Новый текст"
    content_management = True


class SiteTextUpdateView(BaseEditView, UpdateView):
    model = SiteText
    form_class = BackofficeSiteTextForm
    success_url_name = "backoffice:site_text_list"
    title_update = "Редактирование текста"
    content_management = True


class SiteTextDeleteView(LegacyContentDeleteView):
    model = SiteText
    template_name = "backoffice/confirm_delete.html"
    success_url_name = "backoffice:site_text_list"
    success_url = reverse_lazy("backoffice:site_text_list")
