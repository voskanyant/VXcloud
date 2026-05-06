import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cabinet", "0009_vpnnode_ssh_install_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="BotUserEvent",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("telegram_id", models.BigIntegerField(blank=True, null=True)),
                ("event_name", models.TextField()),
                ("subscription_id", models.BigIntegerField(blank=True, null=True)),
                ("metadata", models.JSONField()),
                ("created_at", models.DateTimeField()),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        db_column="user_id",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="cabinet.botuser",
                    ),
                ),
            ],
            options={
                "db_table": "bot_user_events",
                "managed": False,
            },
        ),
    ]
