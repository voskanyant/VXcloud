from __future__ import annotations

import csv
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from blog.models import Category, Page, Post, PostType, SiteText


class Command(BaseCommand):
    help = "Export Django CMS content into a WordPress-friendly JSON/CSV bundle."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default="",
            help="Output directory. Defaults to <repo>/wordpress/import-data.",
        )

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"] or "").expanduser()
        if not output_dir:
            output_dir = settings.BASE_DIR.parent / "wordpress" / "import-data"
        output_dir.mkdir(parents=True, exist_ok=True)

        categories = list(Category.objects.order_by("slug"))
        post_types = list(PostType.objects.order_by("slug"))
        posts = list(
            Post.objects.order_by("slug")
            .select_related("post_type")
            .prefetch_related("categories")
        )
        pages = list(
            Page.objects.order_by("path", "slug")
            .prefetch_related("post_types", "post_categories", "manual_posts")
        )
        site_texts = list(SiteText.objects.order_by("key"))

        payload = {
            "schema_version": 1,
            "source": {
                "app": "django",
                "site_name": "VXcloud",
            },
            "categories": [
                {
                    "slug": category.slug,
                    "title": category.title,
                    "is_active": category.is_active,
                }
                for category in categories
            ],
            "post_types": [
                {
                    "slug": post_type.slug,
                    "title": post_type.title,
                    "is_active": post_type.is_active,
                }
                for post_type in post_types
            ],
            "posts": [self.serialize_post(post) for post in posts],
            "pages": [self.serialize_page(page) for page in pages],
            "site_texts": [
                {
                    "key": site_text.key,
                    "value": site_text.value,
                }
                for site_text in site_texts
            ],
            "navigation": [
                {
                    "title": page.nav_label,
                    "path": page.path,
                    "slug": page.slug,
                    "order": page.nav_order,
                }
                for page in pages
                if page.show_in_nav and page.is_published
            ],
        }

        json_path = output_dir / "django-wordpress-export.json"
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        self.write_csv(
            output_dir / "pages.csv",
            ["path", "slug", "title", "status", "is_homepage", "posts_enabled"],
            [
                {
                    "path": page.path,
                    "slug": page.slug,
                    "title": page.title,
                    "status": "publish" if page.is_published else "draft",
                    "is_homepage": "1" if page.is_homepage else "0",
                    "posts_enabled": "1" if page.posts_enabled else "0",
                }
                for page in pages
            ],
        )
        self.write_csv(
            output_dir / "posts.csv",
            ["slug", "title", "status", "published_at", "categories", "legacy_post_type"],
            [
                {
                    "slug": post.slug,
                    "title": post.title,
                    "status": "publish" if post.is_published else "draft",
                    "published_at": post.published_at.isoformat() if post.published_at else "",
                    "categories": ",".join(category.slug for category in post.categories.all()),
                    "legacy_post_type": post.post_type.slug if post.post_type else "",
                }
                for post in posts
            ],
        )
        self.write_csv(
            output_dir / "site_texts.csv",
            ["key", "value"],
            [{"key": site_text.key, "value": site_text.value} for site_text in site_texts],
        )

        self.stdout.write(self.style.SUCCESS(f"Exported WordPress bundle to {output_dir}"))

    def serialize_post(self, post: Post) -> dict:
        return {
            "slug": post.slug,
            "title": post.title,
            "summary": post.summary,
            "status": "publish" if post.is_published else "draft",
            "published_at": post.published_at.isoformat() if post.published_at else "",
            "created_at": post.created_at.isoformat() if post.created_at else "",
            "updated_at": post.updated_at.isoformat() if post.updated_at else "",
            "categories": [category.slug for category in post.categories.all()],
            "legacy_post_type": post.post_type.slug if post.post_type else "",
            "rendered_html": post.rendered_content,
            "fallback_html": post.content,
        }

    def serialize_page(self, page: Page) -> dict:
        return {
            "path": page.path,
            "slug": page.slug,
            "title": page.title,
            "summary": page.summary,
            "status": "publish" if page.is_published else "draft",
            "is_homepage": page.is_homepage,
            "show_in_nav": page.show_in_nav,
            "nav_title": page.nav_title,
            "nav_order": page.nav_order,
            "created_at": page.created_at.isoformat() if page.created_at else "",
            "updated_at": page.updated_at.isoformat() if page.updated_at else "",
            "rendered_html": page.rendered_content,
            "fallback_html": page.content,
            "feed": {
                "enabled": page.posts_enabled,
                "title": page.posts_title,
                "source": page.posts_source,
                "limit": page.posts_limit,
                "category_filters": [category.slug for category in page.post_categories.all()],
                "manual_post_slugs": [post.slug for post in page.manual_posts.order_by("slug")],
                "legacy_post_type_filters": [post_type.slug for post_type in page.post_types.order_by("slug")],
            },
        }

    def write_csv(self, path: Path, fieldnames: list[str], rows: list[dict]):
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
