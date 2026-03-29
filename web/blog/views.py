from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Category, Page, Post


def home(request: HttpRequest) -> HttpResponse:
    page = Page.objects.filter(is_homepage=True, is_published=True).first()
    if page:
        return render(request, "blog/page_detail.html", {"page": page})
    return render(request, "blog/home.html")


def index(request: HttpRequest) -> HttpResponse:
    now = timezone.now()
    posts = (
        Post.objects.filter(is_published=True, published_at__lte=now)
        .prefetch_related("categories")
    )
    categories = Category.objects.filter(is_active=True).order_by("title")
    return render(
        request,
        "blog/index.html",
        {
            "posts": posts,
            "categories": categories,
            "selected_category": None,
        },
    )


def category_detail(request: HttpRequest, slug: str) -> HttpResponse:
    now = timezone.now()
    category = get_object_or_404(Category, slug=slug, is_active=True)
    posts = (
        Post.objects.filter(is_published=True, published_at__lte=now, categories=category)
        .prefetch_related("categories")
        .distinct()
    )
    categories = Category.objects.filter(is_active=True).order_by("title")
    return render(
        request,
        "blog/index.html",
        {
            "posts": posts,
            "categories": categories,
            "selected_category": category,
        },
    )


def post_detail(request: HttpRequest, slug: str) -> HttpResponse:
    post = get_object_or_404(
        Post.objects.prefetch_related("categories"),
        slug=slug,
        is_published=True,
        published_at__lte=timezone.now(),
    )
    return render(request, "blog/post_detail.html", {"post": post})


def page_detail(request: HttpRequest, slug: str) -> HttpResponse:
    page = get_object_or_404(Page, slug=slug, is_published=True)
    return render(request, "blog/page_detail.html", {"page": page})
