from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.embeds.blocks import EmbedBlock
from wagtail.fields import RichTextField, StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Page
from wagtail.snippets.models import register_snippet
from django.db import models
from django.core.cache import cache
from django.core.validators import RegexValidator

from .blocks import HowToStepsBlock, StepsBlock


class SiteCopy(models.Model):
    key_validator = RegexValidator(
        regex=r"^[a-z0-9._-]+$",
        message="Use only a-z, 0-9, dot, dash and underscore.",
    )
    key = models.CharField(max_length=120, unique=True, validators=[key_validator])
    text = models.TextField(blank=True)
    help_text = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    panels = [
        FieldPanel("key"),
        FieldPanel("text"),
        FieldPanel("help_text"),
    ]

    class Meta:
        ordering = ["key"]
        verbose_name = "Site copy"
        verbose_name_plural = "Site copy"

    def __str__(self) -> str:
        return self.key

    @staticmethod
    def _cache_key(key: str) -> str:
        return f"site_copy::{key}"

    @classmethod
    def get_text(cls, key: str, default: str = "") -> str:
        cache_key = cls._cache_key(key)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        value = cls.objects.filter(key=key).values_list("text", flat=True).first()
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


register_snippet(SiteCopy)


class CMSHomePage(Page):
    max_count = 1
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = ["cms.CMSContentPage"]

    intro = RichTextField(blank=True)
    sections = StreamField(
        [
            (
                "hero",
                blocks.StructBlock(
                    [
                        ("title", blocks.CharBlock(required=True)),
                        ("subtitle", blocks.TextBlock(required=False)),
                    ]
                ),
            ),
            ("rich_text", blocks.RichTextBlock(required=False)),
            (
                "content_list",
                blocks.StructBlock(
                    [
                        ("title", blocks.CharBlock(required=False)),
                        ("items", blocks.ListBlock(blocks.CharBlock(required=True), required=True)),
                    ]
                ),
            ),
            (
                "quote",
                blocks.StructBlock(
                    [
                        ("text", blocks.TextBlock(required=True)),
                        ("author", blocks.CharBlock(required=False)),
                    ]
                ),
            ),
            (
                "button_group",
                blocks.ListBlock(
                    blocks.StructBlock(
                        [
                            ("text", blocks.CharBlock(required=True)),
                            ("url", blocks.URLBlock(required=True)),
                        ]
                    ),
                    required=False,
                ),
            ),
            (
                "cta",
                blocks.StructBlock(
                    [
                        ("heading", blocks.CharBlock(required=True)),
                        ("text", blocks.TextBlock(required=False)),
                        ("button_text", blocks.CharBlock(required=False)),
                        ("button_url", blocks.URLBlock(required=False)),
                    ]
                ),
            ),
            (
                "faq",
                blocks.ListBlock(
                    blocks.StructBlock(
                        [
                            ("question", blocks.CharBlock(required=True)),
                            ("answer", blocks.TextBlock(required=True)),
                        ]
                    ),
                    required=False,
                ),
            ),
            ("steps", StepsBlock()),
            ("howto_steps", HowToStepsBlock()),
            ("embed", EmbedBlock(required=False)),
            (
                "image",
                blocks.StructBlock(
                    [
                        ("image", ImageChooserBlock(required=True)),
                        ("caption", blocks.CharBlock(required=False)),
                    ]
                ),
            ),
        ],
        blank=True,
        use_json_field=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("sections"),
    ]


class CMSContentPage(Page):
    parent_page_types = ["cms.CMSHomePage", "cms.CMSContentPage"]
    subpage_types = ["cms.CMSContentPage"]

    intro = RichTextField(blank=True)
    body = RichTextField(blank=True)
    categories = models.ManyToManyField("blog.Category", blank=True, related_name="cms_pages")
    sections = StreamField(
        [
            (
                "hero",
                blocks.StructBlock(
                    [
                        ("title", blocks.CharBlock(required=True)),
                        ("subtitle", blocks.TextBlock(required=False)),
                    ]
                ),
            ),
            ("rich_text", blocks.RichTextBlock(required=False)),
            (
                "content_list",
                blocks.StructBlock(
                    [
                        ("title", blocks.CharBlock(required=False)),
                        ("items", blocks.ListBlock(blocks.CharBlock(required=True), required=True)),
                    ]
                ),
            ),
            (
                "quote",
                blocks.StructBlock(
                    [
                        ("text", blocks.TextBlock(required=True)),
                        ("author", blocks.CharBlock(required=False)),
                    ]
                ),
            ),
            (
                "button_group",
                blocks.ListBlock(
                    blocks.StructBlock(
                        [
                            ("text", blocks.CharBlock(required=True)),
                            ("url", blocks.URLBlock(required=True)),
                        ]
                    ),
                    required=False,
                ),
            ),
            (
                "cta",
                blocks.StructBlock(
                    [
                        ("heading", blocks.CharBlock(required=True)),
                        ("text", blocks.TextBlock(required=False)),
                        ("button_text", blocks.CharBlock(required=False)),
                        ("button_url", blocks.URLBlock(required=False)),
                    ]
                ),
            ),
            (
                "faq",
                blocks.ListBlock(
                    blocks.StructBlock(
                        [
                            ("question", blocks.CharBlock(required=True)),
                            ("answer", blocks.TextBlock(required=True)),
                        ]
                    ),
                    required=False,
                ),
            ),
            ("steps", StepsBlock()),
            ("howto_steps", HowToStepsBlock()),
            ("embed", EmbedBlock(required=False)),
            (
                "image",
                blocks.StructBlock(
                    [
                        ("image", ImageChooserBlock(required=True)),
                        ("caption", blocks.CharBlock(required=False)),
                    ]
                ),
            ),
        ],
        blank=True,
        use_json_field=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("body"),
        FieldPanel("categories"),
        FieldPanel("sections"),
    ]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        context["is_blog_index"] = self.slug == "blog"
        context["blog_categories"] = []
        context["post_items"] = []

        if context["is_blog_index"]:
            from blog.models import Category

            selected_category_slug = (request.GET.get("category") or "").strip()
            categories_qs = Category.objects.filter(is_active=True).order_by("title")
            selected_category = categories_qs.filter(slug=selected_category_slug).first() if selected_category_slug else None

            posts_qs = (
                CMSContentPage.objects.live()
                .descendant_of(self)
                .exclude(id=self.id)
                .filter(depth__gte=self.depth + 2)
                .filter(numchild=0)
                .prefetch_related("categories")
                .order_by("-first_published_at", "-latest_revision_created_at")
            )
            if selected_category is not None:
                posts_qs = posts_qs.filter(categories=selected_category)

            context["blog_categories"] = list(categories_qs)
            context["selected_blog_category"] = selected_category
            context["post_items"] = posts_qs.specific()
            return context

        if self.get_children().live().exists():
            context["post_items"] = (
                self.get_children()
                .live()
                .filter(numchild=0)
                .prefetch_related("categories")
                .specific()
                .order_by("-first_published_at", "-latest_revision_created_at")
            )

        return context
