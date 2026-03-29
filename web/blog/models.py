from django.core.cache import cache
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Category(models.Model):
    title = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(unique=True, max_length=140)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title", "id"]
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self) -> str:
        return self.title


class Post(models.Model):
    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True, max_length=220)
    summary = models.CharField(max_length=280, blank=True)
    content = models.TextField()
    categories = models.ManyToManyField(Category, blank=True, related_name="posts")
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-id"]

    def __str__(self) -> str:
        return self.title


class SiteText(models.Model):
    key_validator = RegexValidator(
        regex=r"^[a-z0-9._-]+$",
        message="Используйте только a-z, 0-9, точку, дефис и нижнее подчеркивание.",
    )
    key = models.CharField(max_length=120, unique=True, validators=[key_validator])
    value = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Текст сайта"
        verbose_name_plural = "Тексты сайта"
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key

    @staticmethod
    def _cache_key(key: str) -> str:
        return f"site_text::{key}"

    @classmethod
    def get_value(cls, key: str, default: str = "") -> str:
        cache_key = cls._cache_key(key)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        value = cls.objects.filter(key=key).values_list("value", flat=True).first()
        if value is None:
            return default
        cache.set(cache_key, value, timeout=3600)
        return value

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(self._cache_key(self.key))

    def delete(self, *args, **kwargs):
        cache.delete(self._cache_key(self.key))
        super().delete(*args, **kwargs)


class Page(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(unique=True, max_length=200)
    summary = models.CharField(max_length=280, blank=True)
    content = models.TextField()
    is_published = models.BooleanField(default=True)
    is_homepage = models.BooleanField(default=False)
    show_in_nav = models.BooleanField(default=False)
    nav_title = models.CharField(max_length=60, blank=True)
    nav_order = models.PositiveSmallIntegerField(default=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Страница"
        verbose_name_plural = "Страницы"
        ordering = ["nav_order", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_homepage"],
                condition=Q(is_homepage=True),
                name="unique_homepage_page",
            )
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def nav_label(self) -> str:
        return self.nav_title or self.title

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_homepage:
            Page.objects.filter(is_homepage=True).exclude(pk=self.pk).update(is_homepage=False)
