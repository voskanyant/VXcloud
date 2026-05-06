from django.db import migrations, models


SQL = """
ALTER TABLE vpn_nodes
    ADD COLUMN IF NOT EXISTS ssh_host TEXT,
    ADD COLUMN IF NOT EXISTS ssh_port INTEGER NOT NULL DEFAULT 22,
    ADD COLUMN IF NOT EXISTS ssh_user TEXT,
    ADD COLUMN IF NOT EXISTS ssh_password TEXT;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("cabinet", "0008_metrics_dashboard"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="vpnnode",
                    name="ssh_host",
                    field=models.TextField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="vpnnode",
                    name="ssh_port",
                    field=models.IntegerField(default=22),
                ),
                migrations.AddField(
                    model_name="vpnnode",
                    name="ssh_user",
                    field=models.TextField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="vpnnode",
                    name="ssh_password",
                    field=models.TextField(blank=True, null=True),
                ),
            ],
        )
    ]
