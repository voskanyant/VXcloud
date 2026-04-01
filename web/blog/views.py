from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Category, Page, Post


def _page_posts(page: Page):
    now = timezone.now()
    base = Post.objects.filter(is_published=True, published_at__lte=now).prefetch_related("categories", "post_type")

    if not page.posts_enabled:
        return Post.objects.none()

    if page.posts_source == Page.POSTS_SOURCE_MANUAL:
        selected_ids = list(page.manual_posts.values_list("id", flat=True))
        if not selected_ids:
            return Post.objects.none()
        return base.filter(id__in=selected_ids).order_by("-published_at", "-id")

    if page.posts_source == Page.POSTS_SOURCE_TYPES:
        type_ids = list(page.post_types.values_list("id", flat=True))
        category_ids = list(page.post_categories.values_list("id", flat=True))
        if type_ids:
            base = base.filter(post_type_id__in=type_ids)
        if category_ids:
            base = base.filter(categories__id__in=category_ids).distinct()

    return base.order_by("-published_at", "-id")[: max(1, int(page.posts_limit or 24))]


def home(request: HttpRequest) -> HttpResponse:
    page = Page.objects.filter(is_homepage=True, is_published=True).first()
    if page:
        return render(request, "blog/page_detail.html", {"page": page, "page_posts": _page_posts(page)})
    return render(request, "blog/home.html")


def index(request: HttpRequest) -> HttpResponse:
    now = timezone.now()
    posts = Post.objects.filter(is_published=True, published_at__lte=now).prefetch_related("categories")
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
    return render(request, "blog/page_detail.html", {"page": page, "page_posts": _page_posts(page)})


def page_by_path(request: HttpRequest, path: str = "") -> HttpResponse:
    normalized = Page.normalize_path(path)
    page = Page.objects.filter(path=normalized, is_published=True).first()
    if page is None and normalized != "/":
        fallback_slug = normalized.strip("/").split("/")[-1]
        page = Page.objects.filter(slug=fallback_slug, is_published=True).first()

    if page is None:
        raise Http404("Page not found")

    return render(request, "blog/page_detail.html", {"page": page, "page_posts": _page_posts(page)})
