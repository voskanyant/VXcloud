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

4. Run:

```bash
python -m src.main
```

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
