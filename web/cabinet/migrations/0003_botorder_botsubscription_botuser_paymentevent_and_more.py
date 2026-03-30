from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("cabinet", "0002_telegramlinktoken"),
    ]

    operations = [
        migrations.CreateModel(
            name="BotUser",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("telegram_id", models.BigIntegerField(unique=True)),
                ("client_code", models.TextField()),
                ("username", models.TextField(blank=True, null=True)),
                ("first_name", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField()),
            ],
            options={
                "db_table": "users",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="PaymentEvent",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("provider", models.TextField()),
                ("event_id", models.TextField()),
                ("body", models.JSONField()),
                ("created_at", models.DateTimeField()),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "payment_events",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="WebLoginToken",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("token", models.TextField(unique=True)),
                ("telegram_id", models.BigIntegerField()),
                ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField()),
            ],
            options={
                "db_table": "web_login_tokens",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="BotSubscription",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("inbound_id", models.IntegerField()),
                ("client_uuid", models.UUIDField()),
                ("client_email", models.TextField()),
                ("display_name", models.TextField()),
                ("vless_url", models.TextField()),
                ("expires_at", models.DateTimeField()),
                ("is_active", models.BooleanField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
                (
                    "user",
                    models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="cabinet.botuser",
                    ),
                ),
            ],
            options={
                "db_table": "subscriptions",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="BotOrder",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("amount_stars", models.IntegerField()),
                ("currency", models.TextField()),
                ("payload", models.TextField(unique=True)),
                ("status", models.TextField()),
                ("telegram_payment_charge_id", models.TextField(blank=True, null=True)),
                ("provider_payment_charge_id", models.TextField(blank=True, null=True)),
                ("channel", models.TextField(blank=True, null=True)),
                ("payment_method", models.TextField(blank=True, null=True)),
                ("amount_minor", models.BigIntegerField(blank=True, null=True)),
                ("currency_iso", models.TextField(blank=True, null=True)),
                ("card_provider", models.TextField(blank=True, null=True)),
                ("card_payment_id", models.TextField(blank=True, null=True)),
                ("idempotency_key", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField()),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("notified_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="cabinet.botuser",
                    ),
                ),
            ],
            options={
                "db_table": "orders",
                "managed": False,
            },
        ),
        migrations.RenameIndex(
            model_name="telegramlinktoken",
            new_name="cabinet_tel_user_id_64a3a8_idx",
            old_name="cabinet_tel_user_id_68bd83_idx",
        ),
    ]

