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
- direct production traffic on `29940` still goes straight to Xray and does not yet depend on HAProxy

Important operational rule:

- changing node flags in `/ops/` does not magically reconfigure the host HAProxy process
- after changing node flags, HAProxy config must be re-rendered and the relevant HAProxy instance must be restarted/reloaded
- without that step, old routing behavior can continue
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
