# VXcloud Telegram Bot (3x-ui + Reality)

MVP bot for selling VXcloud access:

- `/buy` creates or renews a 30-day subscription
- `/buy` sends Telegram Stars invoice (`XTR`)
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

### Start DB + Web (bot disabled)

```bash
cp .env.example .env
# set real values in .env (token, domain, POSTGRES_PASSWORD, etc.)

docker compose up -d --build db web
```

Note: `web/staticfiles` is bind-mounted from host to container so nginx alias
`/srv/apps/vxcloud/app/web/staticfiles/` works after every deploy.

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

## Wagtail CMS (Optional, safe with existing bot)

Wagtail can be enabled without touching bot logic or `/account/` flows.

Routes:

- `https://vxcloud.ru/cms-admin/` - Wagtail admin
- `https://vxcloud.ru/` - Wagtail public tree (main site)
- `https://vxcloud.ru/legacy/` - old Django blog routes

Server setup after pull:

```bash
cd /srv/apps/vxcloud/app
./scripts/ops/deploy-auto.sh
docker compose --env-file .env exec -T web python /app/web/manage.py migrate
```

Use existing Django superuser to sign in at `/cms-admin/`.

Included editable page types:

- `CMSHomePage`
- `CMSContentPage`

Ready StreamField sections:

- `hero` (title + subtitle)
- `rich_text`
- `cta` (heading, text, button text/url)
- `faq` (list of question/answer)
- `image` (image + caption)

### Bootstrap payment-compliance pages (YooKassa)

To create/update required public pages in Wagtail (services/prices, digital delivery, offer, privacy, contacts/bank details):

```bash
docker compose --env-file .env exec -T web python /app/web/manage.py bootstrap_yookassa_pages
```

This command is idempotent and safe to run multiple times.

## Directus Content Sync From Git

Directus content can be versioned in repo and synced on every deploy.

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
- Admin: `http://127.0.0.1:8088/admin/`

Add posts in admin (`Post`) and they appear on the public guide page.

### Account Cabinet

After login, users can open:

- `/account/` - subscription status
- `/account/link/` - link Telegram ID to bot user
- `/account/config/` - show config link + QR + copy button

Note: payment on site is currently a lightweight stub (`/account/renew/`) to create an order record.
Real card payment requires payment provider webhook integration.

## Card Payments Providers

By default the project uses `ReferencePaymentProvider` (`PAYMENT_PROVIDER=reference`).

There is also a contract-only scaffold provider: `PAYMENT_PROVIDER=yookassa`.
It implements the same contract (`create_payment`, `verify_webhook`) but does not perform real API integration yet.

### Required env vars to enable card payments

Minimal:

- `ENABLE_CARD_PAYMENTS=1`
- `PAYMENT_PROVIDER=reference` (or `yookassa`)
- `CARD_PAYMENT_AMOUNT_MINOR` (example `29900`)
- `CARD_PAYMENT_CURRENCY` (example `RUB`)

For `reference` provider:

- `PAYMENT_REFERENCE_BASE_URL`
- `PAYMENT_REFERENCE_WEBHOOK_SECRET`

For `yookassa` scaffold provider:

- `PAYMENT_YOOKASSA_CHECKOUT_BASE_URL`
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
