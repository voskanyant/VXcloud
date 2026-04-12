# VXcloud Project Memory

Этот файл нужен как короткая рабочая память по проекту.
Его надо обновлять после заметных production-изменений.

## 1. Что это за проект

VXcloud состоит из 3 основных частей:

- WordPress: публичный сайт и контент
- Django: кабинет, backoffice `/ops/`, payment/webhook/backend routes
- Telegram bot: продажи, renew, reminders, support, выдача конфигов

## 2. Текущая production topology

Сейчас основной production server совмещает:

- site
- bot
- backoffice
- payments/webhooks
- HAProxy
- databases
- и одновременно текущий VPN node

То есть сейчас main server = control plane + node-1.

Это удобно на старте, но это всё ещё single point of failure для control plane.

Current intended node management model:

- current main server should exist in `/ops/ -> VPN ноды` as `node-1`
- this lets one physical server stay both control plane and one LB-manageable VPN node
- if routing problem happens only on the VPN side of the main server, disable `lb_enabled` for `node-1`
- site, bot, backoffice and payments can still keep working on that server while new VPN traffic goes to other nodes

Важно:
- это помогает только когда сам сервер жив
- это не спасает от полного падения main server

## 3. Источник правды

Что считается source of truth:

- subscriptions / expiry / active state: app database
- 3x-ui: downstream execution layer, не главный источник правды
- bot content overrides: `/ops/bot/content/`
- публичный контент сайта: WordPress

Важно:
- ручные изменения expiry только в 3x-ui не отражаются автоматически в site/bot
- admin expiry нужно менять через `/ops/`, чтобы обновлялись и DB, и 3x-ui
- cluster sync is still DB-first for managed subscriptions
- manual clients created directly in 3x-ui are now mirrored between nodes too, but only from the canonical node
- canonical node for manual mirroring is the first healthy LB-capable node, normally `node-1-main`
- do not manually create clients on random follower nodes; they can be removed on the next sync if they do not exist on the canonical node

## 4. Production domains and public endpoints

- public site: `https://vxcloud.ru`
- account frontend: `https://vxcloud.ru/account/`
- ops/backoffice: `https://vxcloud.ru/ops/`
- Django admin: `https://vxcloud.ru/django-admin/`

VPN/public ports:

- main VPN public port: `29940`
- current public production flow: `client -> HAProxy:29940 -> Xray:29941`
- temporary HAProxy test frontend used to prove LB routing: `30940`
- subscription port: `2096`
- legacy 3x-ui/admin-like port observed on server: `24886` and must be reviewed carefully before launch exposure

## 5. Payments

Current intended payment provider:

- YooKassa

Expected env:

- `PAYMENT_PROVIDER=yookassa`
- `ENABLE_CARD_PAYMENTS=1`
- `PAYMENT_YOOKASSA_SHOP_ID` filled
- `PAYMENT_YOOKASSA_API_KEY` filled

Card checkout behavior:

- bot card flow does not require separate manual site signup
- Telegram magic-link creates or reuses a site account automatically
- abandoned card checkout should expire after 30 minutes

## 6. Bot behavior assumptions

Current intended UX:

- card is primary payment path
- Stars remain optional, not primary
- `Мой доступ` should show concrete configs, not abstract access only
- `Скопировать ссылку` in bot must copy `vless://...`, not subscription URL
- config expiry reminders must mention which config expired or is expiring

## 7. HAProxy and nodes

Current HAProxy behavior:

- balances new TCP connections
- uses structural node health, not app-specific health
- does not detect "Telegram broken but node otherwise alive"
- does not migrate already established VPN sessions

Current proven state on production:

- current main server is registered in `/ops/ -> VPN ноды` as `node-1-main`
- cluster mode is enabled in app env
- `/ops/ -> Node sync` shows subscriptions mirrored to `node-1-main`
- test HAProxy frontend on `30940` was verified end-to-end:
  - when `node-1-main` is enabled and HAProxy test config is rendered/restarted, VPN works through `30940`
  - when `node-1-main` is disabled in `/ops/` and HAProxy test config is rendered/restarted, VPN through `30940` stops working
- this proves `/ops/ -> VPN ноды` really controls HAProxy-routed traffic
- production cutover is now complete:
  - public `29940` is owned by HAProxy
  - backend `node-1-main` points to `82.21.117.154:29941`
  - local Xray inbound listens on `29941`
  - client configs still use public port `29940`
  - current working chain is `client -> HAProxy:29940 -> Xray:29941`
- current working production HAProxy/Xray state:
  - 3x-ui inbound `Proxy Protocol = on`
  - `.env` `HAPROXY_BACKEND_SEND_PROXY=1`
  - active backend lines must contain `send-proxy check-send-proxy`
  - Xray access log now sees the real client IP again
- current codebase target after HAProxy container migration:
  - runtime config lives in `ops/haproxy/runtime/haproxy.cfg`
  - Docker service name is `haproxy` / container name `vxcloud-haproxy`
  - legacy host `haproxy.service` should be stopped by deploy
  - `/ops/ -> VPN ноды` create/update/delete now re-renders the shared runtime config automatically
  - the HAProxy container watches that file and self-reloads

Important operational rule:

- changing node flags in `/ops/` must still end in a runtime config refresh
- with the new containerized HAProxy path, `/ops/ -> VPN ноды` now re-renders `ops/haproxy/runtime/haproxy.cfg` automatically
- the HAProxy container is responsible for detecting the file change and reloading itself
- if runtime auto-render fails, Django should show a warning and the old routing behavior can continue
- manual 3x-ui clients are now mirrored from the canonical node to follower nodes during cluster sync
- this does not create DB subscriptions or attach those manual clients to bot/site users

Safe node-add rule:

1. add node
2. keep `lb_enabled = false`
3. wait for health
4. complete backfill
5. verify manually
6. only then enable LB

Backoffice support now exists for node CRUD:

- `/ops/ -> VPN ноды` shows inventory
- add node
- edit node
- disable or enable LB participation
- delete node

Recommended meanings of key flags:

- `is_active = true`: node is a live cluster member
- `lb_enabled = true`: HAProxy may send new VPN connections there
- `needs_backfill = true`: do not put into LB yet; sync and manual checks are still pending

Safe node-remove rule:

1. disable `lb_enabled`
2. reload HAProxy
3. wait
4. then stop/remove node

Current tested safe procedure for the temporary HAProxy test path:

1. edit node flags in `/ops/`
2. re-render test HAProxy config:
   - `docker compose --env-file .env exec -T web python /app/scripts/ops/render_haproxy_cfg.py --env-file /app/.env --frontend-port 30940 --dry-run > /tmp/haproxy-vpn-test.cfg`
3. restart test HAProxy instance:
   - `sudo pkill -f "/tmp/haproxy-vpn-test.cfg" || true`
   - `sudo haproxy -f /tmp/haproxy-vpn-test.cfg -p /tmp/haproxy-vpn-test.pid -D`
4. wait about 10 seconds for checks/warm-up
5. reconnect the client using the same config but with port `30940`

Current tested safe procedure for the real production path:

1. keep client configs unchanged on public port `29940`
2. keep Xray inbound on backend port `29941`
3. keep 3x-ui inbound `Proxy Protocol = on`
4. keep `.env` with `HAPROXY_BACKEND_SEND_PROXY=1`
5. render production HAProxy config:
   - `docker compose --env-file .env exec -T web python /app/scripts/ops/render_haproxy_cfg.py --env-file /app/.env --frontend-port 29940 --dry-run > /tmp/haproxy-prod-cutover.cfg`
6. verify generated backend line:
   - `grep -n "server " /tmp/haproxy-prod-cutover.cfg`
   - expected: `server ... 82.21.117.154:29941 check weight 100 send-proxy check-send-proxy`
7. for containerized HAProxy, write the runtime file that the container watches:
   - `docker compose --env-file .env exec -T web python /app/scripts/ops/render_haproxy_cfg.py --env-file /app/.env --output-path /app/ops/haproxy/runtime/haproxy.cfg --skip-validate --skip-reload`
8. verify HAProxy container state:
   - `docker compose --env-file .env logs --tail=100 haproxy`
9. reconnect client on the same old `29940` config

Recommended initial values:

- current main server as `node-1`:
  - `is_active = true`
  - `lb_enabled = true` only if you want it serving LB traffic
  - `needs_backfill = false`
- brand new extra node:
  - `is_active = true`
  - `lb_enabled = false`
  - `needs_backfill = true` until sync and manual validation are complete

## 8. Current launch-critical risks

- control plane still lives on one server
- Telegram-only node failures are not automatically detected by HAProxy
- standby main server recovery is not yet a fully tested process

## 9. What not to do

- do not treat 3x-ui manual edits as primary admin workflow
- do not add a node directly into LB before backfill and manual checks
- do not leave Directus configured if it is no longer used
- do not expose unexpected admin ports publicly without clear reason

## 10. Key guide files

- [go_live_checklist.md](./go_live_checklist.md)
- [emergency_runbook.md](./emergency_runbook.md)
- [servers_and_ports.md](./servers_and_ports.md)
- [known_issues.md](./known_issues.md)
