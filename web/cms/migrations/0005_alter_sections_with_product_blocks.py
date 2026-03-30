from django.db import migrations
import wagtail.blocks
import wagtail.embeds.blocks
import wagtail.fields
import wagtail.images.blocks

import cms.blocks


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0004_sitecopy"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cmscontentpage",
            name="sections",
            field=wagtail.fields.StreamField(
                [
                    (
                        "hero",
                        wagtail.blocks.StructBlock(
                            [
                                ("title", wagtail.blocks.CharBlock(required=True)),
                                ("subtitle", wagtail.blocks.TextBlock(required=False)),
                            ]
                        ),
                    ),
                    ("rich_text", wagtail.blocks.RichTextBlock(required=False)),
                    (
                        "content_list",
                        wagtail.blocks.StructBlock(
                            [
                                ("title", wagtail.blocks.CharBlock(required=False)),
                                ("items", wagtail.blocks.ListBlock(wagtail.blocks.CharBlock(required=True), required=True)),
                            ]
                        ),
                    ),
                    (
                        "quote",
                        wagtail.blocks.StructBlock(
                            [
                                ("text", wagtail.blocks.TextBlock(required=True)),
                                ("author", wagtail.blocks.CharBlock(required=False)),
                            ]
                        ),
                    ),
                    (
                        "button_group",
                        wagtail.blocks.ListBlock(
                            wagtail.blocks.StructBlock(
                                [
                                    ("text", wagtail.blocks.CharBlock(required=True)),
                                    ("url", wagtail.blocks.URLBlock(required=True)),
                                ]
                            ),
                            required=False,
                        ),
                    ),
                    (
                        "cta",
                        wagtail.blocks.StructBlock(
                            [
                                ("heading", wagtail.blocks.CharBlock(required=True)),
                                ("text", wagtail.blocks.TextBlock(required=False)),
                                ("button_text", wagtail.blocks.CharBlock(required=False)),
                                ("button_url", wagtail.blocks.URLBlock(required=False)),
                            ]
                        ),
                    ),
                    (
                        "faq",
                        wagtail.blocks.ListBlock(
                            wagtail.blocks.StructBlock(
                                [
                                    ("question", wagtail.blocks.CharBlock(required=True)),
                                    ("answer", wagtail.blocks.TextBlock(required=True)),
                                ]
                            ),
                            required=False,
                        ),
                    ),
                    ("steps", cms.blocks.StepsBlock()),
                    ("howto_steps", cms.blocks.HowToStepsBlock()),
                    ("embed", wagtail.embeds.blocks.EmbedBlock(required=False)),
                    (
                        "image",
                        wagtail.blocks.StructBlock(
                            [
                                ("image", wagtail.images.blocks.ImageChooserBlock(required=True)),
                                ("caption", wagtail.blocks.CharBlock(required=False)),
                            ]
                        ),
                    ),
                ],
                blank=True,
                use_json_field=True,
            ),
        ),
        migrations.AlterField(
            model_name="cmshomepage",
            name="sections",
            field=wagtail.fields.StreamField(
                [
                    (
                        "hero",
                        wagtail.blocks.StructBlock(
                            [
                                ("title", wagtail.blocks.CharBlock(required=True)),
                                ("subtitle", wagtail.blocks.TextBlock(required=False)),
                            ]
                        ),
                    ),
                    ("rich_text", wagtail.blocks.RichTextBlock(required=False)),
                    (
                        "content_list",
                        wagtail.blocks.StructBlock(
                            [
                                ("title", wagtail.blocks.CharBlock(required=False)),
                                ("items", wagtail.blocks.ListBlock(wagtail.blocks.CharBlock(required=True), required=True)),
                            ]
                        ),
                    ),
                    (
                        "quote",
                        wagtail.blocks.StructBlock(
                            [
                                ("text", wagtail.blocks.TextBlock(required=True)),
                                ("author", wagtail.blocks.CharBlock(required=False)),
                            ]
                        ),
                    ),
                    (
                        "button_group",
                        wagtail.blocks.ListBlock(
                            wagtail.blocks.StructBlock(
                                [
                                    ("text", wagtail.blocks.CharBlock(required=True)),
                                    ("url", wagtail.blocks.URLBlock(required=True)),
                                ]
                            ),
                            required=False,
                        ),
                    ),
                    (
                        "cta",
                        wagtail.blocks.StructBlock(
                            [
                                ("heading", wagtail.blocks.CharBlock(required=True)),
                                ("text", wagtail.blocks.TextBlock(required=False)),
                                ("button_text", wagtail.blocks.CharBlock(required=False)),
                                ("button_url", wagtail.blocks.URLBlock(required=False)),
                            ]
                        ),
                    ),
                    (
                        "faq",
                        wagtail.blocks.ListBlock(
                            wagtail.blocks.StructBlock(
                                [
                                    ("question", wagtail.blocks.CharBlock(required=True)),
                                    ("answer", wagtail.blocks.TextBlock(required=True)),
                                ]
                            ),
                            required=False,
                        ),
                    ),
                    ("steps", cms.blocks.StepsBlock()),
                    ("howto_steps", cms.blocks.HowToStepsBlock()),
                    ("embed", wagtail.embeds.blocks.EmbedBlock(required=False)),
                    (
                        "image",
                        wagtail.blocks.StructBlock(
                            [
                                ("image", wagtail.images.blocks.ImageChooserBlock(required=True)),
                                ("caption", wagtail.blocks.CharBlock(required=False)),
                            ]
                        ),
                    ),
                ],
                blank=True,
                use_json_field=True,
            ),
        ),
    ]
