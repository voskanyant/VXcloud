# VXcloud Runbook: Add A VPN Node

This runbook documents the current VXcloud node setup workflow. Update it after
every real operator session when a command, field, failure mode, or UI label
changes. The documentation should get better as we learn from each deployment.

## Current Model

- VXcloud is DNS-alias-first for normal client traffic.
- Each subscription gets a stable alias like `u-xxxx.connect.vxcloud.ru`.
- Cloudflare DNS-only A records point aliases to the assigned node public IP.
- The stable user artifact is the subscription URL:
  `https://vxcloud.ru/account/feed/<token>/`.
- 3x-ui/Xray is the execution layer. PostgreSQL is the source of truth.
- HAProxy remains fallback/legacy and should not be used as the normal endpoint
  for new DNS-alias subscriptions.

## Safety Rules

- Add a new node with `lb_enabled=false` first.
- Keep `needs_backfill=true` until the node is health checked and synchronized.
- Do not move production users to a node until the test subscription works.
- Do not commit real panel usernames, passwords, or private Reality keys.
- For seamless DNS cutover without client re-import, nodes in the same
  compatibility pool must share the same VLESS/Reality behavior:
  port, transport, SNI, fingerprint, public key, short ID strategy, and flow.
- If Reality keys differ between nodes, clients may need a subscription refresh
  after reassignment.

## 1. Check The New Server

On the new node:

```bash
ss -ltnp | grep -E ':80|:443|:36726|xray|x-ui' || true
```

Expected before install:

- no service on `443`
- no existing `x-ui` panel unless this server was already configured

If SSH warns that the host key changed, remove the old key only if you know the
server was rebuilt:

```powershell
ssh-keygen -R <node-ip>
```

Then connect again:

```bash
ssh root@<node-ip>
```

## 2. Install 3x-ui

Run:

```bash
bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)
```

Installer choices:

- When asked to customize panel port, answer exactly `y` if you want a fixed
  port. Typing `yes` may be treated as not matching and a random port can be
  generated.
- Panel port can be random or fixed. Record it.
- Use SSL certificate setup option `2` for IP certificate if you do not have a
  node hostname yet.
- Save the generated panel username, password, port, and base path somewhere
  secure. Do not commit them.

Check panel settings:

```bash
x-ui settings
ss -ltnp | grep -E ':80|:443|:<panel-port>|xray|x-ui' || true
```

Expected:

- `x-ui` listens on the panel port.
- after inbound creation, `xray` listens on `443`.

## 3. Create The VLESS Reality Inbound

In 3x-ui, create an inbound with:

- Protocol: `VLESS`
- Port: `443`
- Network: `tcp`
- Security: `reality`
- Flow: `xtls-rprx-vision`
- SNI / server name: normally `www.apple.com`
- Fingerprint: `chrome`
- SpiderX: `/`
- Sniffing: disabled
- Proxy Protocol: disabled for DNS-alias direct-node traffic

After saving, verify:

```bash
ss -ltnp | grep ':443' || true
```

Expected:

```text
LISTEN ... *:443 ... xray-linux-amd64
```

## 4. Verify 3x-ui API From Main Server

Run this on the VXcloud main server, not on the node:

```bash
curl -k -s -X POST 'https://<node-ip>:<panel-port>/<base-path>/login' \
  -H 'Content-Type: application/json' \
  --data '{"username":"<panel-user>","password":"<panel-password>"}'
```

Expected:

```json
{"success":true,...}
```

Then verify inbound ID and Reality values:

```bash
curl -k -s -c /tmp/newnode.cookies \
  -X POST 'https://<node-ip>:<panel-port>/<base-path>/login' \
  -H 'Content-Type: application/json' \
  --data '{"username":"<panel-user>","password":"<panel-password>"}' >/dev/null

curl -k -s -b /tmp/newnode.cookies \
  'https://<node-ip>:<panel-port>/<base-path>/panel/api/inbounds/list'
```

Record these values for `/ops/`:

- inbound ID, usually `1`
- public key
- one valid short ID
- SNI
- fingerprint
- port

## 5. Install The Node Metrics Agent

Install the lightweight VXcloud agent on the VPN node so `/ops/infra/node-stats/`
can show server CPU, RAM, disk, swap, load, network counters, uptime, and socket
counts directly from the VPS. This is more reliable than treating 3x-ui as the
source of truth for OS metrics.

From the app checkout copied to the node, or after uploading the two scripts:

```bash
cd /srv/apps/vxcloud/app
bash scripts/ops/install-vxnode-metrics-agent.sh
```

Open the firewall only from the VXcloud main server:

```bash
ufw allow from <main-server-ip> to any port 9109 proto tcp
systemctl status vxnode-metrics-agent --no-pager
curl -H "Authorization: Bearer <token>" http://127.0.0.1:9109/metrics
```

The token is stored on the node in:

```text
/etc/vxnode-metrics-agent.env
```

## 6. Add The Node In `/ops/`

Open:

```text
https://vxcloud.ru/ops/infra/nodes/
```

Click `+ Create` / `+ Создать`.

Required field mapping:

```text
Name: node-<short-id>-main
Region: Germany
3x-ui base URL: https://<node-ip>:<panel-port>/<base-path>
3x-ui username: <panel-user>
3x-ui password: <panel-password>
3x-ui inbound ID: 1

Public IP: <node-ip>
Node FQDN: node-<node-ip-or-name>.vxcloud.ru
Compatibility pool: default

Xray API host: 127.0.0.1
Xray API port: 0
Xray metrics host: 127.0.0.1
Xray metrics port: 0

Node metrics agent enabled: checked after agent install
Node metrics agent URL: http://<node-ip>:9109/metrics
Node metrics token: <VXNODE_METRICS_TOKEN from /etc/vxnode-metrics-agent.env>

Bandwidth capacity (Mbps): 1000
Connection capacity: 10000
Backend host: <node-ip>
Backend port: 443
HAProxy weight: 100
```

Checkboxes for first save:

```text
Node active: checked
Requires backfill: checked
Enable in load balancer: unchecked
```

Notes:

- `Backend host`, `Backend port`, and `HAProxy weight` are still required
  because HAProxy fallback/legacy code exists.
- For DNS-alias steady-state, users connect to `u-*.connect.vxcloud.ru`, which
  resolves directly to `Public IP`.
- `Node FQDN` is metadata unless you also create a DNS record for the node.
- If the metrics agent is not installed yet, leave it disabled. The stats page
  will still collect 3x-ui client counters, but OS resource gauges will stay
  empty or use 3x-ui fallback values.

## 7. Wait For Health And Backfill

After saving, refresh `/ops/infra/nodes/`.

Expected initial states:

- `unknown` for a short time is normal.
- `backfill_pending` is normal until sync runs.
- do not enable new assignments while `backfill_pending` or unhealthy.

If the node stays unhealthy, check main server logs:

```bash
cd /srv/apps/vxcloud/app
docker compose --env-file .env logs --tail=120 web
docker compose --env-file .env logs --tail=120 bot
```

Common causes:

- wrong panel base path
- wrong username/password
- panel port blocked by firewall
- inbound ID is not `1`
- xray not listening on `443`

Open `/ops/infra/node-stats/` after sync has run. It should show current
assigned users, observed clients, CPU/RAM/disk gauges, traffic, peak
concurrency, probe latency, health sample percentage, capacity usage, recent
events, and projection data for the node.

## 8. Test A New Subscription

Only after the node is healthy:

1. Create a test subscription in `/ops/bot/subscriptions/new/`.
2. Confirm it shows the new node.
3. Confirm it has alias host `u-*.connect.vxcloud.ru`.
4. Confirm Cloudflare has a DNS-only A record pointing to the node public IP.
5. Import the subscription URL in a VPN client.

Check the feed:

```bash
curl -s 'https://vxcloud.ru/account/feed/<token>/'
```

The feed should return a base64 subscription payload. When decoded, the VLESS
host should be the alias hostname, not the direct node IP.

## 9. Enable For Production Assignments

After a successful test:

- clear `Requires backfill`
- enable `Enable in load balancer` only if HAProxy fallback should include it
- keep `Node active` checked

For DNS-alias assignments, the important production readiness values are:

- healthy
- `lb_enabled=true` only if you want the node eligible for new assignments
- `needs_backfill=false`
- compatibility pool set
- capacity values set

## 10. Rebalance Or Failover Existing Users

Use `/ops/infra/system/` for manual dry-run, rebalance, or emergency failover.

Rules:

- normal rebalance should avoid unhealthy, disabled, backfill, incompatible, or
  cooldown-blocked nodes
- failover can be used when the old assigned node is down
- DNS aliases update in Cloudflare; users keep the same subscription URL
- if the destination node uses different Reality keys, users may need the client
  to refresh the subscription before it works

## 11. Cloudflare Notes

No manual Cloudflare record is required for each node.

VXcloud creates and updates per-subscription records:

```text
u-xxxx.connect.vxcloud.ru -> <assigned-node-public-ip>
```

Deleted subscriptions should delete their alias DNS record. If Cloudflare
cleanup fails, deletion should still finish and an actionable warning should be
logged.

Having 1000+ per-subscription DNS records is acceptable for this architecture.
The operational concern is cleanup correctness, not the record count itself.

## Current Session Example

Example values from the May 2026 test-node setup. Do not copy passwords into
commits or public notes.

```text
Node IP: 95.169.201.246
Panel port: 61662
Base path: /HXyjUhmVwqZqRGmTBe/
Inbound ID: 1
Inbound port: 443
Reality SNI: www.apple.com
Reality fingerprint: chrome
Reality public key: 31Uye-wUuuy3WgyvJDlLBNALpqO-j73WgmjKVgIsPzQ
Example short IDs: 2d, 459859afc4f5, d8d0
```

Ops values for that session:

```text
Name: node-95-main
Region: Germany
Public IP: 95.169.201.246
Compatibility pool: default
Xray API host: 127.0.0.1
Xray API port: 0
Xray metrics host: 127.0.0.1
Xray metrics port: 0
Bandwidth capacity (Mbps): 1000
Connection capacity: 10000
Backend host: 95.169.201.246
Backend port: 443
HAProxy weight: 100
```
