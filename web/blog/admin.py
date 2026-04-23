from django import forms
from django.contrib import admin

from .models import Category, Page, Post, PostType, SiteText

BLOCK_EDITOR_ASSET_VERSION = "20260423-no-bootstrap-interactive-v11"


class RichTextAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "content_blocks" in self.fields:
            self.fields["content_blocks"].help_text = (
                "Новый блочный редактор (Gutenberg-подобный): добавляйте блоки, меняйте порядок, удаляйте."
            )
        if "content" in self.fields:
            self.fields["content"].help_text = "Резервное поле HTML (используется, если блоки пустые)."

    class Meta:
        widgets = {
            "content_blocks": forms.Textarea(attrs={"class": "js-block-editor-source", "rows": 6}),
            "content": forms.Textarea(attrs={"rows": 12}),
        }

    class Media:
        css = {"all": ("admin/block_editor_v8.css",)}
        js = ("admin/block_editor_v8.js",)


class PostAdminForm(RichTextAdminForm):
    class Meta(RichTextAdminForm.Meta):
        model = Post
        fields = "__all__"


class PageAdminForm(RichTextAdminForm):
    class Meta(RichTextAdminForm.Meta):
        model = Page
        fields = "__all__"


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    form = PostAdminForm
    list_display = ("title", "post_type", "is_published", "published_at", "updated_at")
    list_filter = ("is_published", "post_type", "categories")
    search_fields = ("title", "summary", "content")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("-published_at", "-id")
    filter_horizontal = ("categories",)
    fieldsets = (
        (None, {"fields": ("title", "slug", "summary", "content_blocks", "content")}),
        ("Рубрикация", {"fields": ("post_type", "categories")}),
        ("Публикация", {"fields": ("is_published", "published_at")}),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("title",)


@admin.register(PostType)
class PostTypeAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("title",)


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    form = PageAdminForm
    list_display = (
        "title",
        "slug",
        "path",
        "is_published",
        "is_homepage",
        "show_in_nav",
        "posts_enabled",
        "posts_source",
        "nav_order",
        "updated_at",
    )
    list_filter = ("is_published", "is_homepage", "show_in_nav", "posts_enabled", "posts_source")
    search_fields = ("title", "slug", "summary", "content")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("nav_order", "title")
    filter_horizontal = ("post_types", "post_categories", "manual_posts")
    fieldsets = (
        (None, {"fields": ("title", "slug", "path", "summary", "content_blocks", "content")}),
        ("Публикация", {"fields": ("is_published", "is_homepage")}),
        ("Навигация", {"fields": ("show_in_nav", "nav_title", "nav_order")}),
        (
            "Лента постов на странице",
            {
                "fields": (
                    "posts_enabled",
                    "posts_title",
                    "posts_source",
                    "posts_limit",
                    "post_types",
                    "post_categories",
                    "manual_posts",
                )
            },
        ),
    )


@admin.register(SiteText)
class SiteTextAdmin(admin.ModelAdmin):
    list_display = ("key", "updated_at")
    search_fields = ("key", "value")
    ordering = ("key",)

