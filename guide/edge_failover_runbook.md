# VXcloud Edge Failover Runbook

Use this runbook after the project is split into:

- site/backend on `vxcloud.ru`
- public VPN edge on `connect.vxcloud.ru`
- backend VPN nodes behind the edge

## 1. Inventory assumptions

In `/ops -> HAProxy edges` you should have at least:

- one `primary` edge
- optionally one `secondary` / standby edge

The `primary` edge in `/ops` is the edge that **should** match the current DNS target for `connect.vxcloud.ru`.

## 2. Before promoting a standby edge

Check:

- standby edge `is_active = true`
- standby edge `accept_new_clients = true`
- `last_health_ok = true`
- backend node pool on standby edge is current

Recommended command:

```bash
python web/manage.py check_haproxy_edges
python scripts/ops/render_haproxy_cfg.py --env-file .env --dry-run
```

## 3. Planned cutover

1. In `/ops -> HAProxy edges`, confirm the standby edge is healthy.
2. Mark the standby edge as `primary`.
3. Update DNS for `connect.vxcloud.ru` to the standby edge public IP.
4. Wait for DNS TTL / resolver cache rollover.
5. Check new client configs and a real VPN connection.

## 4. Emergency cutover

1. Mark broken edge `is_active = false`.
2. Set standby edge `is_primary = true` and `accept_new_clients = true`.
3. Change DNS `connect.vxcloud.ru` to standby edge public IP.
4. Verify:
   - new configs still use `connect.vxcloud.ru:443`
   - standby edge accepts traffic
   - Xray access log on nodes still sees real client IP

## 5. Important limitation

`/ops` is the control plane for edge inventory. It does **not** switch public traffic by itself.

Actual user failover still depends on:

- DNS cutover
- or floating IP
- or provider-level traffic switching
