# VPN Telegram Bot (3x-ui + Reality)

MVP bot for selling VPN access:

- `/buy` creates or renews a 30-day subscription
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

4. Run:

```bash
python -m src.main
```

## Notes

- `XUI_BASE_URL` must include your web base path, for example:
  - `https://127.0.0.1:45659/mil993e2RzVGipj`
- Use a secret manager or environment variables in production.
- Rotate panel credentials before production launch.
