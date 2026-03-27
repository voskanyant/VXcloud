from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Page, Post


def home(request: HttpRequest) -> HttpResponse:
    page = Page.objects.filter(is_homepage=True, is_published=True).first()
    if page:
        return render(request, "blog/page_detail.html", {"page": page})
    return render(request, "blog/home.html")


def index(request: HttpRequest) -> HttpResponse:
    posts = Post.objects.filter(is_published=True, published_at__lte=timezone.now())
    return render(request, "blog/index.html", {"posts": posts})


def post_detail(request: HttpRequest, slug: str) -> HttpResponse:
    post = get_object_or_404(Post, slug=slug, is_published=True, published_at__lte=timezone.now())
    return render(request, "blog/post_detail.html", {"post": post})


def page_detail(request: HttpRequest, slug: str) -> HttpResponse:
    page = get_object_or_404(Page, slug=slug, is_published=True)
    return render(request, "blog/page_detail.html", {"page": page})
