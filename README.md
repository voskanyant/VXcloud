# VXcloud Telegram Bot (3x-ui + Reality)

MVP bot for selling VXcloud access:

- `/buy` creates or renews a 30-day subscription
- `/buy` can start card checkout or Telegram Stars flow
- `/myvpn` sends VLESS link and QR code
- `/renew` extends subscription
- background reminders before expiration

## Stack

- Python 3.11+
- Telegram Bot API (`python-telegram-bot`)
- PostgreSQL
- 3x-ui API

## Quick Start

1. Create DB schema:

```bash
psql -h 127.0.0.1 -U vpnbot -d vpnbot -f sql/schema.sql
```

2. Create virtualenv and install:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Configure:

```bash
cp .env.example .env
```

Fill `.env` values.
Set `PLAN_PRICE_STARS` (for example `250`).
Set `MAX_DEVICES_PER_SUB=1` to block shared access from multiple devices on one subscription.
Cluster mode env (optional, defaults keep single-node behavior):

- `VPN_CLUSTER_ENABLED=0`
- `VPN_CLUSTER_HEALTHCHECK_INTERVAL_SECONDS=30`
- `VPN_CLUSTER_SYNC_INTERVAL_SECONDS=60`
- `VPN_CLUSTER_SYNC_BATCH_SIZE=200`

Set `VPN_CLUSTER_ENABLED=1` only when cluster tables and node inventory are configured.

### HAProxy Config Rendering (Cluster Mode)

For cluster mode with HAProxy TCP balancing, generate `haproxy.cfg` from `vpn_nodes`:

```bash
python scripts/ops/render_haproxy_cfg.py --env-file .env
```

The script:

- selects nodes from `vpn_nodes` where `lb_enabled=true`, `is_active=true`, `needs_backfill=false`, `last_health_ok=true`
- excludes nodes whose cached REALITY signature does not match the current pool baseline
- renders config from `ops/haproxy/haproxy.cfg.tpl`
- writes to `HAPROXY_OUTPUT_PATH`
- validates with `haproxy -c -f <output>`
- executes `HAPROXY_RELOAD_CMD` (if set)

Current production recommendation:

- run HAProxy in Docker
- keep runtime config in `ops/haproxy/runtime/haproxy.cfg`
- let the HAProxy container watch that file and self-reload on change
- use `/ops/ -> VPN ноды` as source of LB state, with Django re-rendering the runtime config after node create/update/delete

Relevant env vars:

- `HAPROXY_TEMPLATE_PATH` (default: `ops/haproxy/haproxy.cfg.tpl`)
- `HAPROXY_OUTPUT_PATH` (recommended: `ops/haproxy/runtime/haproxy.cfg`)
- `HAPROXY_FRONTEND_BIND_ADDR` (default: `0.0.0.0`)
- `HAPROXY_FRONTEND_PORT` (default: `VPN_PUBLIC_PORT`)
- `HAPROXY_RELOAD_CMD` (leave empty when HAProxy is containerized and self-reloads from file changes)
- `HAPROXY_BIN` (default: `haproxy`)

Dry-run example:

```bash
python scripts/ops/render_haproxy_cfg.py --env-file .env --dry-run
```

### Backend Node Onboarding Checklist

When you buy/add a second server, use this flow:

1. Provision node and secure panel API
- Install and harden 3x-ui/Xray on the backend node.
- Allow panel API access from main server IP only (firewall).
- Ensure API endpoints are reachable (`/login`, `/panel/api/inbounds/get/{id}`).

2. Match REALITY baseline across nodes
- Keep REALITY-compatible key material aligned for your cluster model.
- Ensure accepted `shortIds` include IDs used by generated configs.
- Keep inbound behavior consistent (VLESS + REALITY TCP), with backend listening on the routed port.

3. Add node in Django Admin (`VPN Nodes`)
- Fill: `name`, `region`, `xui_base_url`, credentials, `xui_inbound_id`, `backend_host`, `backend_port`, `backend_weight`.
- Set `is_active=true`, keep `lb_enabled=false` initially.

4. Verify health telemetry
- Wait for cluster health loop updates:
  - `last_health_ok`
  - `last_health_at`
  - `last_reality_*`
- Check mismatch indicator before enabling LB.

5. Request backfill
- Run admin action `Request backfill`.
- Wait until `vpn_node_clients.sync_state` converges to `ok`.
- Confirm node `needs_backfill` clears and `last_backfill_at` is set.
- New subscriptions continue syncing to backfill nodes before they are admitted into LB.

6. Enable in LB and reload HAProxy
- Run admin action `Enable LB`.
- Render/apply config:

```bash
python scripts/ops/render_haproxy_cfg.py --env-file .env
```

7. Safe rollback
- Disable node in LB (`Disable LB`) and render HAProxy again.
- Optionally mark node inactive for maintenance.

### Single-Node Compatibility

- Default mode remains single-node: `VPN_CLUSTER_ENABLED=0`.
- Cluster mode is opt-in: `VPN_CLUSTER_ENABLED=1`.
- In cluster mode, bot link resolution uses `subscriptions.xui_sub_id` from DB to avoid dependence on one backend panel.
- You can bootstrap gradually by adding your current node into `vpn_nodes` first, then enabling cluster mode later.

### Cluster Testing Coverage

Current unit tests include:

- domain cluster activation path (`activate_subscription`)
- provisioner node fan-out and per-node sync state updates
- HAProxy config renderer output (`mode tcp`, `leastconn`, server lines)
- compatibility paths for existing single-node behavior

Run tests:

```bash
python -m unittest
```

### Production note about 3x-ui

3x-ui is commonly used in personal/self-hosted setups. For production services, apply extra hardening:

- strict network ACLs
- credential rotation
- monitoring + alerting
- backups and tested rollback procedure
For production with a domain, set:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=0`
- `DJANGO_ALLOWED_HOSTS` (example `vxcloud.example.com`)
- `DJANGO_CSRF_TRUSTED_ORIGINS` (example `https://vxcloud.example.com`)
- `VPN_PUBLIC_HOST` to the same public domain

4. Run:

```bash
python -m src.main
```

## Docker Deploy (Recommended)

The project includes:

- `Dockerfile`
- `docker-compose.yml`
- `scripts/docker/web-entrypoint.sh`
- `scripts/docker/bot-entrypoint.sh`

### Start Full Stack (bot disabled)

```bash
cp .env.example .env
# set real values in .env (token, domain, Postgres, WordPress, etc.)

docker compose up -d --build db wpdb wordpress web proxy
```

Public traffic now goes through the local nginx reverse proxy on `127.0.0.1:8088`.

- WordPress owns `/`, `/instructions/`, `/blog/`, and other public content routes
- Django keeps `/account/`, `/accounts/`, `/api/`, `/auth/tg/`, `/open-app/`, `/django-admin/`, and `/ops/`
- Old `/admin/` requests redirect to `/ops/`

### Start Bot (cutover step)

```bash
docker compose --profile bot up -d bot
```

### Stop Bot

```bash
docker compose stop bot
```

### One-command deploy on server

```bash
cd /srv/apps/vxcloud/app
chmod +x scripts/ops/deploy-auto.sh
./scripts/ops/deploy-auto.sh
```

## Legacy Django CMS

WordPress is the primary public CMS now.

- Public pages, blog, navigation, and footer content are managed in WordPress
- Django `/ops/` keeps legacy content screens only for migration support and historical review
- Django `/django-admin/` remains useful for operational data and internal models, not as the primary public CMS

### Bootstrap базовых страниц

```bash
docker compose --env-file .env exec -T web python /app/web/manage.py bootstrap_site_pages
```

## WordPress Public Site

The public marketing/content site is now scaffolded for WordPress + Flatsome.

- WordPress admin: `/wp-admin/`
- Django ops panel: `/ops/`
- Django admin: `/django-admin/`
- repo-managed WordPress files live in [`wordpress/`](wordpress/README.md)

### Django to WordPress export

Export the existing Django CMS content into the shared WordPress import directory:

```bash
docker compose --env-file .env exec -T web python /app/web/manage.py export_wordpress_content
```

This creates:

- `wordpress/import-data/django-wordpress-export.json`
- `wordpress/import-data/pages.csv`
- `wordpress/import-data/posts.csv`
- `wordpress/import-data/site_texts.csv`

### WordPress import

After WordPress starts:

1. Install the licensed Flatsome parent theme in WordPress
2. Activate `VX Flatsome Child`
3. Activate `VX Site Integration`
4. Open `Tools -> Django Import`
5. Import `/var/www/html/import-data/django-wordpress-export.json`

### Legacy Django CMS

The old Django content screens remain available under `/ops/` for migration support and operational review.
Set `WORDPRESS_CONTENT_READONLY=1` when you want to freeze legacy content editing in Django.

## Legacy Directus Content Sync From Git

Directus is now a legacy optional bridge for bot texts only. Leave it disabled in production unless you intentionally still depend on it.

- Seed files:
  - `directus_seed/bot_buttons.json`
  - `directus_seed/bot_content.json`
- Sync tool:
  - `scripts/sync_directus.py`
- Deploy workflow runs sync automatically after DB migration.

### Seed Format

`directus_seed/bot_buttons.json`:

```json
[
  { "key": "menu_buy", "label": "Купить VPN" },
  { "key": "menu_mysub", "label": "Моя подписка" }
]
```

`directus_seed/bot_content.json`:

```json
[
  { "key": "start_message", "value": "Добро пожаловать..." },
  { "key": "menu_buy_response", "value": "..." }
]
```

### Manual Run (Server)

```bash
/opt/vpnbot/.venv/bin/python /opt/vpnbot/scripts/sync_directus.py \
  --env-file /opt/vpnbot/.env \
  --buttons-file /opt/vpnbot/directus_seed/bot_buttons.json \
  --content-file /opt/vpnbot/directus_seed/bot_content.json
```

Use `--dry-run` to preview changes.

## Notes

- `XUI_BASE_URL` must include your web base path, for example:
  - `https://127.0.0.1:45659/mil993e2RzVGipj`
- `XUI_SUB_PORT` is used for subscription links (`/sub/<subId>`), usually `2096`.
- Use a secret manager or environment variables in production.
- Rotate panel credentials before production launch.

## Optional CMS (Directus)

You can edit bot texts and button labels from Directus without redeploy.

1. Configure `.env`:
   - `CMS_BASE_URL` (for example `https://cms.example.com`)
   - `CMS_TOKEN` (static token with read access to your collections)
   - optionally collection names (`CMS_CONTENT_COLLECTION`, `CMS_BUTTON_COLLECTION`)

2. Create collection for content (default `bot_content`) with fields:
   - `key` (string, unique)
   - `value` (text)

3. Create collection for buttons (default `bot_buttons`) with fields:
   - `key` (string, unique)
   - `label` (string)

4. Supported button keys:
   - `menu_trial`
   - `menu_buy`
   - `menu_renew`
   - `menu_mysub`
   - `menu_instructions`
   - `contact_share`
   - `contact_cancel`

5. Supported content keys (main):
   - `start_message`
   - `buy_intro_message`
   - `menu_unknown_message`
   - `cancel_message`
   - `phone_missing_message`
   - `sending_invoice_message`
   - `share_contact_hint_message`
   - `contact_missing_message`
   - `contact_self_only_message`
   - `phone_invalid_message`
   - `phone_saved_message` (supports `{phone}` placeholder)
   - `invoice_title`
   - `invoice_description`
   - `no_subscription_message`

6. Force refresh from Telegram (admin only):
   - `/admin_reload`

## Lightweight Help Site

A minimal static instruction site is included in `guide/`:

- `guide/index.html`
- `guide/styles.css`

### Quick Deploy (Nginx)

```bash
sudo mkdir -p /var/www/vxcloud-help
sudo cp -r guide/* /var/www/vxcloud-help/
```

Example Nginx location:

```nginx
server {
    listen 80;
    server_name help.your-domain.com;

    root /var/www/vxcloud-help;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

## Django Guide CMS (Blog + Admin)

A lightweight Django guide CMS is included in `web/` with admin panel.

### Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd web
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8088
```

Open:

- Guide: `http://127.0.0.1:8088/`
- Ops Panel: `http://127.0.0.1:8088/ops/`

Add posts in admin (`Post`) and they appear on the public guide page.

### Account Cabinet

After login, users can open:

- `/account/` - subscription status
- `/account/link/` - link Telegram ID to bot user
- `/account/config/` - show config link + QR + copy button

Site card payment is implemented through provider checkout plus webhook confirmation.

## Card Payments Providers

By default the project uses `YooKassaPaymentProvider` (`PAYMENT_PROVIDER=yookassa`).

There is also a legacy local/mock provider: `PAYMENT_PROVIDER=reference`.
Use it only for local testing, not for production checkout.

### Required env vars to enable card payments

Minimal:

- `ENABLE_CARD_PAYMENTS=1`
- `PAYMENT_PROVIDER=yookassa`
- `CARD_PAYMENT_AMOUNT_MINOR` (example `24900`)
- `CARD_PAYMENT_CURRENCY` (example `RUB`)

For `reference` provider:

- `PAYMENT_REFERENCE_BASE_URL`
- `PAYMENT_REFERENCE_WEBHOOK_SECRET`

For `yookassa` provider:

- `PAYMENT_YOOKASSA_WEBHOOK_SECRET`
- `PAYMENT_YOOKASSA_SHOP_ID`
- `PAYMENT_YOOKASSA_API_KEY`

### Webhook deduplication guarantee

`POST /api/webhooks/<provider>` always writes incoming events to `payment_events`.
Uniqueness is enforced by `(provider, event_id)` and duplicate events are acknowledged with `200 OK` without re-processing the order.

## DNS for New Domain

If your server public IPv4 is `1.2.3.4` and domain is `vxcloud.example.com`, add:

- `A` record: host `@` -> `1.2.3.4` (optional, if you also use root domain)
- `A` record: host `vxcloud` -> `1.2.3.4`

After DNS propagation:

1. Configure Nginx `server_name vxcloud.example.com;`
2. Issue TLS certificate (`certbot --nginx -d vxcloud.example.com`)
3. Set `.env`:
   - `DJANGO_ALLOWED_HOSTS=vxcloud.example.com`
   - `DJANGO_CSRF_TRUSTED_ORIGINS=https://vxcloud.example.com`
   - `VPN_PUBLIC_HOST=vxcloud.example.com`
