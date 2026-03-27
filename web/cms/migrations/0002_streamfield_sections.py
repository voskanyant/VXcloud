from django.db import migrations
import wagtail.blocks
import wagtail.fields
import wagtail.images.blocks


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
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
        migrations.AddField(
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
