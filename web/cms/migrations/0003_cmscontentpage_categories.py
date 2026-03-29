from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0006_category_post_categories"),
        ("cms", "0002_streamfield_sections"),
    ]

    operations = [
        migrations.AddField(
            model_name="cmscontentpage",
            name="categories",
            field=models.ManyToManyField(blank=True, related_name="cms_pages", to="blog.category"),
        ),
    ]
