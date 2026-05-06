# VXcloud Agent Context

Use this as the compact current-state summary for coding work.

## Product Flow

1. User buys or renews from the site or Telegram bot.
2. VXcloud stores the order and subscription in PostgreSQL.
3. VXcloud provisions the client on the assigned Xray/3x-ui node.
4. VXcloud creates or reuses a stable subscription feed token.
5. VXcloud returns a subscription URL to the user.
6. The feed returns a VLESS config whose host is the stable alias
   `u-*.connect.vxcloud.ru`.
7. Rebalance or failover moves a client by changing DNS for the alias.

## Source Of Truth

- App DB is authoritative for user, order, subscription, expiry, active state,
  assigned node, alias hostname, rebalance state, and node sync state.
- Cloudflare DNS is authoritative for alias-to-node-IP routing.
- 3x-ui/Xray is the downstream runtime where client credentials are installed.
- WordPress is authoritative for public marketing/content pages.
- `/ops/` is the operator surface for subscriptions, nodes, sync, and rebalance.
- `/ops/infra/node-stats/` shows current and 7-day node load from
  `vpn_node_load_snapshots`. CPU/system load is not collected until node
  exporter or Xray metrics ingestion is wired.

## Node Model

Each active VPN node should have:

- public IP or backend host
- XUI base URL and credentials
- inbound ID
- `compatibility_pool`
- public/backend port behavior matching the pool
- Reality settings compatible with other nodes in the same pool
- health state
- `lb_enabled` only after health and backfill are complete

Subscriptions keep:

- `assigned_node_id`
- `current_node_id`
- optional `desired_node_id`
- `alias_fqdn`
- `assignment_state`
- `compatibility_pool`
- feed token
- XUI client UUID/email/sub ID

## DNS Alias Behavior

- Namespace: `connect.vxcloud.ru`.
- Alias format: `u-<random>.connect.vxcloud.ru`.
- Record type: DNS-only Cloudflare `A`.
- Default TTL: 300 seconds.
- Cutover TTL: 60 seconds.
- User imports the VXcloud subscription URL once.
- Client refresh/reconnect is enough after DNS cutover; no re-import should be
  needed if the client refreshes subscriptions correctly.

## UI Boundaries

- Public WordPress pages are calm editorial black/white.
- Django account pages must look like the same site, not a separate app.
- Login/register/account/config pages must not depend on Bootstrap visuals.
- `/ops/` may be operational/admin styled.
- User-facing QR pages should make subscription URL primary and avoid raw VLESS
  as the main artifact.
- Bot UX rules live in `guide/bot_ux_policy.md`. Keep the bot as a small
  Russian command/control layer and move full account work into the Mini App.
- Mini App UX rules live in `guide/mini_app_ux_policy.md`. Keep `/account-app/`
  compact, mobile-first, and scoped separately from the wider browser fallback.

## Known Production Risks

- A deleted or unreachable old node can make naive XUI operations hang.
- Cloudflare token or zone misconfiguration breaks alias creation/deletion.
- Main server remains a control-plane SPOF unless a standby is built.
- HAProxy and Xray PROXY protocol settings must match if HAProxy fallback is
  used.
- Manual 3x-ui edits do not automatically become DB subscriptions.
