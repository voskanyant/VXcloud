# Multi-node DNS alias rebalance runbook

VXcloud multi-node mode uses stable per-subscription DNS aliases. Users import one subscription URL once. The VLESS host inside the feed is a stable alias such as `u-abc.connect.vxcloud.ru`; Cloudflare points that alias to the currently assigned node IP.

## Required environment

Enable cluster mode first, then rebalance mode after at least two compatible nodes are healthy.

```env
VPN_CLUSTER_ENABLED=1
VPN_REBALANCE_ENABLED=1
VPN_REBALANCE_WORKFLOW_TICK_SECONDS=300

VPN_ALIAS_NAMESPACE=connect.vxcloud.ru
VPN_ALIAS_PROVIDER=cloudflare
VPN_ALIAS_DEFAULT_TTL=300
VPN_ALIAS_CUTOVER_TTL=60
VPN_ALIAS_OVERLAP_MINUTES=310

CLOUDFLARE_API_TOKEN=...
CLOUDFLARE_ZONE_ID=...
```

Cloudflare records must be DNS-only, not proxied. The API token needs zone read plus DNS record read/edit for `vxcloud.ru`.

## Node compatibility contract

Only nodes in the same `compatibility_pool` can exchange users. Keep the default pool as `default` unless you intentionally operate separate pools.

Every node in one pool must share:

- same VLESS inbound behavior
- same public port, normally `443`
- same transport and security, normally TCP + Reality
- same flow, normally `xtls-rprx-vision`
- compatible Reality public key, short ID strategy, SNI, and fingerprint
- same client naming/sub-id expectations

## Required node fields

For each node in `/ops/infra/nodes/`, configure:

- `xui_base_url`, `xui_username`, `xui_password`, `xui_inbound_id`
- `public_ip` or `backend_host` as a routable node IP
- `backend_port`, normally `443`
- `lb_enabled=true`
- `compatibility_pool=default`
- `backend_weight`, `bandwidth_capacity_mbps`, `connection_capacity`

Healthcheck must populate `last_health_ok=true` and Reality fields before the node can receive new assignments or rebalance traffic.

## Weekly workflow

The bot process runs the rebalance loop only when both `VPN_CLUSTER_ENABLED=1` and `VPN_REBALANCE_ENABLED=1`.

With the default tick of `300` seconds:

- Sunday 01:00-01:09 Europe/Moscow: build plan.
- Next tick: presync user credentials on destination nodes.
- Next tick: cut over Cloudflare `A` records to destination node IPs.
- After `VPN_ALIAS_OVERLAP_MINUTES`: delete old-node credentials and restore alias TTL.

The planner ignores inactive, unhealthy, disabled, backfill-pending, Reality-missing, or incompatible-pool nodes.

## Manual rebalance

If a node is overloaded and you do not want to wait for the Sunday workflow, use:

```text
/ops/infra/system/
```

In the `Rebalance dry-run` panel, review planned moves, then press `Start manual rebalance now`.

The button runs the same guarded workflow immediately:

- bootstrap missing aliases
- backfill unassigned active subscriptions
- plan eligible moves using the normal score/cooldown/max-move rules
- presync destination credentials
- cut over Cloudflare alias A records
- clean up any moves whose overlap window has already expired

It does not bypass planner safety. It still ignores unhealthy, disabled, backfill-pending, incompatible, cooldown-blocked, or low-benefit moves.

## Delete behavior

When a config is deleted, VXcloud now attempts to remove:

- the Xray/3x-ui client
- node sync state
- the Cloudflare per-subscription `A` record
- the database subscription row

DNS deletion is best-effort. If Cloudflare is temporarily unavailable, access is still revoked because the Xray/3x-ui client is removed, but the stale DNS record should be checked in Cloudflare.

## Pre-live test

Before enabling live multi-node rebalance:

1. Add node 1 and node 2 with the same `compatibility_pool`.
2. Confirm both show healthy in `/ops/infra/nodes/`.
3. Create a test subscription and verify Cloudflare creates `u-*.connect.vxcloud.ru`.
4. Import the subscription into a client and connect.
5. Use `/ops/infra/cluster/` dry-run to confirm a planned move is reasonable.
6. Force or wait for the workflow on a test config.
7. Confirm DNS changes from node 1 IP to node 2 IP.
8. Confirm the client works after refresh/reconnect without re-import.
9. Confirm cleanup removes old-node credentials after the overlap window.
