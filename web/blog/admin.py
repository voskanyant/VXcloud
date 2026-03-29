from django import forms
from django.contrib import admin

from .models import Category, Page, Post, SiteText


class RichTextAdminForm(forms.ModelForm):
    class Meta:
        widgets = {
            "content": forms.Textarea(attrs={"class": "js-richtext", "rows": 28}),
        }

    class Media:
        js = (
            "https://cdn.jsdelivr.net/npm/tinymce@7/tinymce.min.js",
            "admin/post_editor.js",
        )


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
    list_display = ("title", "is_published", "published_at", "updated_at")
    list_filter = ("is_published", "categories")
    search_fields = ("title", "summary", "content")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("-published_at", "-id")
    filter_horizontal = ("categories",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
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
        "is_published",
        "is_homepage",
        "show_in_nav",
        "nav_order",
        "updated_at",
    )
    list_filter = ("is_published", "is_homepage", "show_in_nav")
    search_fields = ("title", "slug", "summary", "content")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("nav_order", "title")
    fieldsets = (
        (None, {"fields": ("title", "slug", "summary", "content")}),
        ("Публикация", {"fields": ("is_published", "is_homepage")}),
        ("Навигация", {"fields": ("show_in_nav", "nav_title", "nav_order")}),
    )


@admin.register(SiteText)
class SiteTextAdmin(admin.ModelAdmin):
    list_display = ("key", "updated_at")
    search_fields = ("key", "value")
    ordering = ("key",)
