from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Page
from django.db import models


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
