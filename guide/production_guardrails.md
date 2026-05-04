# VXcloud Production Guardrails

This file lists rules that protect the live service.

## Production Deployment

Production app path:

```bash
/srv/apps/vxcloud/app
```

Deploy should use committed code and migrations:

```bash
cd /srv/apps/vxcloud/app
git pull origin main
./scripts/ops/deploy-auto.sh
docker compose --env-file .env ps
```

Do not run `makemigrations` during deploy. If Django says models changed
without migrations, create and commit the migration in development first.

## Required Production Env Checks

Check these before launch or after major deploys:

```bash
grep -nE 'DJANGO_DEBUG|DJANGO_ALLOWED_HOSTS|CSRF|TELEGRAM|CLOUDFLARE|VPN_ALIAS|PAYMENT|DIRECTUS|SECRET|XUI_API|BACKOFFICE_XUI' .env
```

Expected direction:

- `DJANGO_DEBUG=0`
- real Telegram token/admin values
- real Cloudflare token and zone ID
- `VPN_ALIAS_NAMESPACE=connect.vxcloud.ru`
- `VPN_ALIAS_PROVIDER=cloudflare`
- payment provider set to the intended live provider
- no `YOUR_...` placeholders
- Directus disabled unless intentionally reintroduced

## Dead Node Handling

If a node is deleted, dead, or unreachable:

1. Go to `/ops/infra/nodes/`.
2. Edit the node.
3. Disable `lb_enabled`.
4. Disable active state if it should not receive sync.
5. Add or enable a healthy replacement node.
6. Run manual failover/rebalance only after replacement health is confirmed.

The app should not hang on dead-node cleanup. Inactive subscription deletion is
allowed to complete locally even if old remote XUI cleanup fails.

## DNS Alias Cleanup

When a subscription is deleted:

- VXcloud should attempt to delete the Cloudflare alias.
- Failure should log or display a warning.
- Failure should not block inactive local deletion.
- Orphaned `u-*.connect.vxcloud.ru` records are not immediately dangerous, but
  should be periodically cleaned to keep Cloudflare tidy.

For many subscriptions, per-user aliases are expected. Thousands of DNS-only A
records are operationally acceptable, but record cleanup must remain monitored.

## Rebalance And Failover

Safe rebalance flow:

1. plan
2. presync destination node
3. lower TTL where needed
4. update DNS alias
5. keep overlap credentials
6. cleanup old node credentials
7. record history

Never move subscriptions to a node that is:

- inactive
- `lb_enabled=false` for normal placement
- unhealthy
- marked `needs_backfill`
- in another compatibility pool
- cooling down after recent moves

Emergency failover is allowed when a source node is bad, but still requires a
healthy compatible destination.

## HAProxy Notes

HAProxy is fallback/legacy infrastructure. If used:

- public frontend and Xray backend ports must be intentional
- `HAPROXY_BACKEND_SEND_PROXY=1` must match 3x-ui inbound `Proxy Protocol = on`
- changing one side without the other can break clients
- after node flag changes, confirm runtime HAProxy config is refreshed

## Quick Health Commands

```bash
docker compose --env-file .env ps
docker compose --env-file .env logs --tail=200 web
docker compose --env-file .env logs --tail=200 bot
docker compose --env-file .env logs --tail=200 proxy
```

Subscription feed check:

```bash
curl -i 'https://vxcloud.ru/account/feed/<token>/'
```

Expected:

- HTTP 200 for valid active token
- body is base64 subscription content
- decoded VLESS host is `u-*.connect.vxcloud.ru`
