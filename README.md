# VPN Telegram Bot (3x-ui + Reality)

MVP bot for selling VPN access:

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

4. Run:

```bash
python -m src.main
```

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
   - `menu_buy`
   - `menu_mysub`
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
