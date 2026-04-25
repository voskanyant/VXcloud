# VXcloud Go-Live Audit Report

Last updated: 2026-04-25

## Verdict

`ready with warnings`

The core Django checks and unit tests pass locally. The code path now defaults to the DNS-alias subscription model, deploy checks migrations before public service recreation, and stale public-facing raw VLESS output was reduced. Final launch still requires production-only verification on the server because DNS, Telegram, payment, and external client import behavior depend on live secrets and infrastructure.

## Blockers

- Rotate the Cloudflare API token before launch if the setup token was shared outside the server. Do not launch with a token that was pasted into chats, screenshots, logs, or terminals.
- Production `.env` must be verified on the server, not from local defaults: `DJANGO_DEBUG=0`, real Telegram settings, real Cloudflare zone/token, real payment settings, and no `YOUR_` placeholders.

## High

- GitHub Actions deploy must not discover new migrations after public containers are already recreated. The deploy workflow now runs `makemigrations --check --dry-run` before recreating the public web/proxy path.
- Default alias namespace is now `connect.vxcloud.ru`; server `.env` should still set `VPN_ALIAS_NAMESPACE=connect.vxcloud.ru` explicitly.
- WordPress account embed now prefers `feed_url`/subscription URL over raw `vless_url` when it renders config cards.
- Public account pages should remain Bootstrap-free visually. Keep future changes inside the account CSS system and avoid reintroducing admin/sidebar dashboard components.

## Medium

- `vless_url` remains in the database and code intentionally. It is still required for Xray/3x-ui compatibility and fallback, but it should not be the primary customer-facing copy/QR path.
- `/legacy/` routing and Legacy CMS backoffice labels remain as migration support. Remove only after WordPress ownership of those pages is confirmed in production.
- Cloudflare alias deletion is best-effort on subscription/user deletion. If provider deletion fails, `/ops/` warns; operators should clean the DNS record manually.

## Cleanup Completed

- Removed unreferenced old static files: obsolete block editor versions and stale `web/static/site.css`.
- Updated stale operational notes that still described HAProxy direct-port configs as the new-config rule.
- Fixed the broken default meta-description fallback text.

## Manual Launch Checks

Run on the server before switching traffic:

```bash
cd /srv/apps/vxcloud/app
grep -nE 'DJANGO_DEBUG|DJANGO_ALLOWED_HOSTS|CSRF|TELEGRAM|CLOUDFLARE|VPN_ALIAS|PAYMENT|DIRECTUS|SECRET|YOUR_|PLACEHOLDER' .env
docker compose --env-file .env config --quiet
docker compose --env-file .env ps
docker compose --env-file .env logs --tail=200 web bot proxy
```

Then create one test subscription and verify:

- Cloudflare creates a DNS-only `u-*.connect.vxcloud.ru` A record pointing to the assigned node IP.
- `/account/feed/<token>/` returns base64 subscription content.
- Decoded VLESS host is the alias hostname, not the direct node IP.
- Deleting the test subscription removes the Cloudflare DNS record or shows an actionable cleanup warning in `/ops/`.
- Telegram login, account dashboard, QR page, and Shadowrocket/Streisand import all work from a real phone.

