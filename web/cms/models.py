from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Page


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
        FieldPanel("sections"),
    ]
