from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from blog.models import Category, Page, Post, PostType, SiteText


class StaffAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise ValidationError("Доступ в админ-панель только для staff-пользователей.", code="not_staff")


class BootstrapFormMixin:
    def _apply_bootstrap_classes(self):
        for name, field in self.fields.items():
            widget = field.widget
            classes = widget.attrs.get("class", "")
            base = classes.split()

            if isinstance(widget, forms.CheckboxInput):
                target = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                target = "form-select"
            else:
                target = "form-control"

            if target not in base:
                base.append(target)
            widget.attrs["class"] = " ".join(c for c in base if c)

            if name == "content_blocks":
                widget.attrs["class"] += " js-block-editor-source"
                widget.attrs.setdefault("rows", 6)
            if name == "content":
                widget.attrs.setdefault("rows", 14)

            if isinstance(widget, forms.DateTimeInput):
                widget.input_type = "datetime-local"


class BackofficePostForm(BootstrapFormMixin, forms.ModelForm):
    published_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M"),
        label="Дата публикации",
    )

    class Meta:
        model = Post
        fields = [
            "title",
            "slug",
            "summary",
            "post_type",
            "categories",
            "is_published",
            "published_at",
            "content_blocks",
            "content",
        ]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 3}),
            "content_blocks": forms.Textarea(attrs={"rows": 6}),
            "content": forms.Textarea(attrs={"rows": 14}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categories"].queryset = Category.objects.order_by("title")
        self.fields["post_type"].queryset = PostType.objects.order_by("title")
        self.fields["title"].label = "Заголовок"
        self.fields["slug"].label = "Slug"
        self.fields["summary"].label = "Краткое описание"
        self.fields["post_type"].label = "Тип поста"
        self.fields["categories"].label = "Категории"
        self.fields["is_published"].label = "Опубликован"
        self.fields["content_blocks"].label = "Контент (блоки)"
        self.fields["content"].label = "HTML fallback"
        self.fields["content_blocks"].help_text = "Gutenberg-подобный редактор блоков."
        self.fields["content"].help_text = "Резервное поле HTML, если блоки не используются."
        self._apply_bootstrap_classes()


class BackofficePageForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Page
        fields = [
            "title",
            "slug",
            "path",
            "summary",
            "is_published",
            "is_homepage",
            "show_in_nav",
            "nav_title",
            "nav_order",
            "posts_enabled",
            "posts_title",
            "posts_source",
            "posts_limit",
            "post_types",
            "post_categories",
            "manual_posts",
            "content_blocks",
            "content",
        ]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 3}),
            "content_blocks": forms.Textarea(attrs={"rows": 6}),
            "content": forms.Textarea(attrs={"rows": 14}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["post_types"].queryset = PostType.objects.order_by("title")
        self.fields["post_categories"].queryset = Category.objects.order_by("title")
        self.fields["manual_posts"].queryset = Post.objects.order_by("-published_at", "-id")
        self.fields["title"].label = "Заголовок"
        self.fields["slug"].label = "Slug"
        self.fields["path"].label = "Путь URL"
        self.fields["summary"].label = "Краткое описание"
        self.fields["is_published"].label = "Опубликована"
        self.fields["is_homepage"].label = "Главная страница"
        self.fields["show_in_nav"].label = "Показывать в меню"
        self.fields["nav_title"].label = "Название в меню"
        self.fields["nav_order"].label = "Порядок в меню"
        self.fields["posts_enabled"].label = "Показывать ленту постов"
        self.fields["posts_title"].label = "Заголовок ленты"
        self.fields["posts_source"].label = "Источник постов"
        self.fields["posts_limit"].label = "Лимит постов"
        self.fields["post_types"].label = "Типы постов"
        self.fields["post_categories"].label = "Категории постов"
        self.fields["manual_posts"].label = "Выбранные посты"
        self.fields["content_blocks"].label = "Контент (блоки)"
        self.fields["content"].label = "HTML fallback"
        self.fields["path"].help_text = "Например: /instructions/ или /help/ios/"
        self.fields["content_blocks"].help_text = "Gutenberg-подобный редактор блоков."
        self.fields["content"].help_text = "Резервное поле HTML, если блоки не используются."
        self._apply_bootstrap_classes()


class BackofficeCategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["title", "slug", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].label = "Название"
        self.fields["slug"].label = "Slug"
        self.fields["is_active"].label = "Активна"
        self._apply_bootstrap_classes()


class BackofficePostTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PostType
        fields = ["title", "slug", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].label = "Название"
        self.fields["slug"].label = "Slug"
        self.fields["is_active"].label = "Активен"
        self._apply_bootstrap_classes()


class BackofficeSiteTextForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SiteText
        fields = ["key", "value"]
        widgets = {"value": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["key"].label = "Ключ"
        self.fields["value"].label = "Значение"
        self._apply_bootstrap_classes()
