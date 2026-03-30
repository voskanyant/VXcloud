from django.core.validators import RegexValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0003_cmscontentpage_categories"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteCopy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "key",
                    models.CharField(
                        max_length=120,
                        unique=True,
                        validators=[
                            RegexValidator(
                                message="Use only a-z, 0-9, dot, dash and underscore.",
                                regex="^[a-z0-9._-]+$",
                            )
                        ],
                    ),
                ),
                ("text", models.TextField(blank=True)),
                ("help_text", models.CharField(blank=True, max_length=255)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Site copy",
                "verbose_name_plural": "Site copy",
                "ordering": ["key"],
            },
        ),
    ]
