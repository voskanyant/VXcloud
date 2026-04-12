# VXcloud Servers And Ports

Этот файл нужен как быстрая инвентаризация.

## 1. Current main production server

Roles:

- WordPress
- Django web
- Telegram bot
- HAProxy / proxy
- Postgres
- MariaDB
- current VPN node (`node-1`)

Operational model:

- this same server should be represented in `/ops/ -> VPN ноды`
- node record purpose: allow enabling/disabling only the VPN role in LB without turning off site/bot/backend
- if this server has VPN routing trouble but site is still alive, set `lb_enabled = false` for `node-1`
- new VPN traffic should then go only to the other enabled nodes

## 2. Ports that are intentionally important

Public:

- `80/tcp` - site HTTP
- `443/tcp` - site HTTPS
- `29940/tcp` - current production VPN public frontend on HAProxy
- `30940/tcp` - temporary HAProxy test frontend used to verify node/LB routing
- `2096/tcp` - subscription/config delivery port

Internal/localhost:

- `8088/tcp` - local app/proxy health path
- `29941/tcp` - current Xray backend port behind HAProxy
- `5432/tcp` - Postgres
- `3306/tcp` - MariaDB
- `62789/tcp` - x-ui/api internal observed

Observed and must be reviewed:

- `24886/tcp` - public on current server, do not forget this exists

## 3. Expected env values

- `VPN_PUBLIC_HOST=vxcloud.ru`
- `VPN_PUBLIC_PORT=29940`
- `HAPROXY_FRONTEND_PORT=29940`
- `HAPROXY_BACKEND_SEND_PROXY=1`

## 4. Node strategy

Current:

- main server acts as node-1
- control plane and node-1 are still on the same physical server

Target future architecture:

- separate control server
- separate node-1
- node-2
- node-3

Current `/ops/` capabilities:

- create node
- edit node
- disable/enable LB participation
- delete node

## 5. Node checklist before enabling LB

- inbound listens on expected port
- firewall open for that port
- REALITY values match pool expectations
- manual app test passes:
  - Telegram
  - normal websites
  - config import
- backfill complete
- `lb_enabled = false` until all above is true

Suggested field values:

- for current main server / `node-1`:
  - `backend_host = 127.0.0.1` when HAProxy runs in Docker host-network mode on the same server as Xray
  - `backend_port = 29941`
  - `is_active = true`
  - `needs_backfill = false`
- for a fresh new node:
  - `is_active = true`
  - `lb_enabled = false`
  - `needs_backfill = true` until first sync and manual tests are done

## 6. Proven test state

- `30940` was tested as a separate HAProxy frontend on the main server
- client config with only `29940 -> 30940` changed works when `node-1-main` is enabled and HAProxy test config is rendered/restarted
- the same `30940` client config stops working when `node-1-main` is disabled in `/ops/` and HAProxy test config is rendered/restarted
- this proves `/ops/ -> VPN ноды` already controls HAProxy-routed traffic
- production `29940` no longer bypasses HAProxy
- current production chain is:
  - `client -> 29940/tcp (HAProxy) -> 29941/tcp (Xray backend)`
- current active HAProxy backend line must look like:
  - `server node_10_node-1-main 82.21.117.154:29941 check weight 100 send-proxy check-send-proxy`
- current 3x-ui inbound for the production node should keep `Proxy Protocol = on`
- current runtime ownership:
  - HAProxy should run as Docker service `haproxy`
  - runtime config should live in `ops/haproxy/runtime/haproxy.cfg`
  - host `haproxy.service` should no longer be the intended runtime
- current result:
  - HAProxy sees the real client IP
  - Xray access log also sees the real client IP
  - Xray-log-based IP analytics are meaningful again
