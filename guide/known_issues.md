# VXcloud Known Issues And Rules

Этот файл нужен не для паники, а чтобы не наступать на уже известные грабли.

## 1. Known behavior

### 3x-ui expiry edits

Если поменять expiry только в 3x-ui:

- site and bot не обновятся автоматически
- правильный admin path: менять expiry через `/ops/`

### Manual 3x-ui clients in cluster mode

- DB-managed subscriptions still sync one-way from app DB to nodes
- manual clients added directly in 3x-ui do not become bot/site subscriptions automatically
- manual clients are mirrored between nodes only from the canonical node
- if a manual client exists only on a follower node and not on the canonical node, cluster sync may remove it from that follower

### Node can be "alive but bad for Telegram"

Node может:

- нормально открывать сайты
- но не иметь нормальной reachability до Telegram

В этом случае:

- HAProxy может считать его healthy
- такой node надо вручную убирать из LB

### Main server is still control-plane SPOF

Если умирает main server, падают:

- bot
- site
- ops
- payments/webhooks
- HAProxy on main server

### Main server can still be used as node-1

Current intended model:

- main server is both control plane and `node-1`
- if only VPN routing on that server goes bad, disable `lb_enabled` for `node-1`
- this should leave site, bot, `/ops/` and payments alive on the same machine
- this is not a substitute for full standby control plane

### Current production port split

- `29940` is still the current direct Xray path
- `30940` was introduced only as a temporary HAProxy test frontend
- node on/off behavior in `/ops/` has already been proven on `30940`
- do not assume disabling a node in `/ops/` will immediately stop direct `29940` traffic

## 2. Practical rules

- new configs must use public port `29940`
- bot copy action must copy `vless://...`
- card checkout from bot must open checkout directly, not just account dashboard
- stale card pending older than 30 minutes should not be treated as active checkout

## 3. Operational rules

- before launch, keep Directus disabled unless intentionally used
- before enabling a new node in LB, manually test Telegram through it
- keep current main server represented in `/ops/ -> VPN ноды` as `node-1`
- use `/ops/` as the place to add, edit, disable and delete nodes
- if one node behaves strangely, remove it from LB first and investigate second
- do not do incident response by editing random production rows without understanding source of truth
- after changing node flags in `/ops/`, re-render and restart/reload the relevant HAProxy instance before concluding anything about routing
- do not change the main 3x-ui inbound port during HAProxy tests unless the goal is an intentional production cutover

## 4. When returning to this project later

First re-read:

- [project_memory.md](./project_memory.md)
- [go_live_checklist.md](./go_live_checklist.md)
- [emergency_runbook.md](./emergency_runbook.md)
