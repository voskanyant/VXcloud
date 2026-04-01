from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0008_posttype_page_manual_posts_page_post_categories_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="page",
            name="content_blocks",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="post",
            name="content_blocks",
            field=models.JSONField(blank=True, default=list),
        ),
    ]

