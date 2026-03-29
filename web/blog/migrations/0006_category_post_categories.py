from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0005_delete_homepagecontent_page_is_homepage_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120, unique=True)),
                ("slug", models.SlugField(max_length=140, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Категория",
                "verbose_name_plural": "Категории",
                "ordering": ["title", "id"],
            },
        ),
        migrations.AddField(
            model_name="post",
            name="categories",
            field=models.ManyToManyField(blank=True, related_name="posts", to="blog.category"),
        ),
    ]
