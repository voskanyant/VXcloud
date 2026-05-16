# VXcloud Agent Guide

Read this first before changing code in this repository. Keep it short,
factual, and current.

## Start Here

- Run `git status --short` and preserve user changes.
- Read the relevant source before editing. Prefer `rg` for searches.
- For broad context, start with:
  - `guide/agent_context.md`
  - `guide/agent_workflow.md`
  - `guide/production_guardrails.md`
- When an operator workflow changes, update the matching runbook in `guide/`.

## Project Shape

- `web/` is Django: account pages, Telegram login, payment callbacks,
  `/ops/` backoffice, backend APIs, and Django models.
- `src/` is shared runtime code: bot entrypoint, DB access, XUI client,
  subscription provisioning, DNS aliases, node sync, and rebalance logic.
- `wordpress/` is the public WordPress site container and PHP settings.
- `scripts/` contains deploy, Docker, HAProxy, ops, and maintenance scripts.
- `sql/` contains hand-written production SQL migrations.
- `tests/` contains unit tests. Add targeted regression tests for bug fixes.
- `guide/` contains operator runbooks and project memory. Some older files have
  encoding damage; prefer the newer ASCII files listed above when moving fast.

## Ownership Boundaries

- WordPress owns public content pages such as `/`, `/blog/`, and guides.
- Django owns `/account/`, `/accounts/`, `/auth/tg/`, `/open-app/`,
  `/account-app/`, `/django-admin/`, `/ops/`, payment endpoints, and backend
  APIs.
- Telegram bot handles buying, renewing, reminders, support, and subscription
  delivery.
- PostgreSQL is the source of truth for users, orders, subscriptions, nodes,
  DNS alias assignment, and rebalance state.
- 3x-ui/Xray is an execution layer, not the source of truth.
- Cloudflare DNS is authoritative for alias-to-node routing.

## Subscription Model

- Normal client traffic uses per-subscription DNS aliases:
  `u-*.connect.vxcloud.ru`.
- The stable user artifact is the VXcloud subscription URL:
  `https://vxcloud.ru/account/feed/<token>/`.
- User-facing QR/config pages should make the subscription URL primary and
  avoid raw VLESS as the main artifact.
- HAProxy is fallback/legacy infrastructure and should not be treated as the
  steady-state endpoint for new DNS-alias subscriptions.

## Editing Rules

- Do not revert user changes unless explicitly asked.
- Do not use destructive git commands.
- Use `apply_patch` for manual edits.
- Keep new docs and code comments ASCII unless the touched file already uses
  valid non-ASCII text and there is a clear reason.
- Avoid broad regex replacements in files with mojibake. Use bounded edits and
  run `py_compile` after touching Python.
- Keep commits focused. Do not commit `.env`, logs, generated staticfiles, or
  database dumps.

## UI Rules

- Public account UI must match the WordPress visual language: minimal
  black/white layout, red links only, no Bootstrap visual components.
- `/account-app/` is the Telegram Mini App surface. Keep it compact,
  mobile-first, and scoped separately from the browser account fallback.
- Backoffice `/ops/` can keep admin styling, but broken legacy user-facing
  artifacts should be removed.
- Check responsive behavior for account-facing pages at mobile and desktop
  widths when changing templates or CSS.

## Production Safety

- Production path is normally `/srv/apps/vxcloud/app`.
- Deploy must use committed migrations only. Do not generate migrations during
  deploy.
- Request paths must not wait on long serial calls to dead nodes. XUI,
  Cloudflare, payment, and other remote calls in web requests should use short
  timeouts and best effort cleanup where safe.
- New nodes must be added with `lb_enabled=false` first, then health checked,
  backfilled, manually tested, and only then admitted.
- Deleted inactive subscriptions should delete locally even if old node cleanup
  fails; log or warn so stale remote clients can be checked manually.
- DNS alias records should be cleaned up on deletion. If Cloudflare cleanup
  fails, the user flow should not hang.

## Verification

Run checks from the repository root. Use path separators appropriate for the
current shell.

```bash
python web/manage.py check
python -m py_compile src/xui_client.py src/dns_alias.py web/backoffice/views.py web/cabinet/views.py
python -m unittest discover -s tests
docker compose --env-file .env config
```

Use targeted tests when the full suite is not needed:

```bash
python -m unittest tests.test_backoffice_subscription_delete_unit
python -m unittest tests.test_account_subscription_delete_unit
python -m unittest tests.test_dns_alias_unit
python -m unittest tests.test_rebalance_unit
```

## Fast Context Files

- `guide/agent_context.md`: compact architecture and source-of-truth notes.
- `guide/agent_workflow.md`: common development and verification workflow.
- `guide/production_guardrails.md`: production risk rules and incident notes.
- `guide/add_vpn_node_runbook.md`: operator steps for adding nodes.
- `guide/multinode_dns_rebalance_runbook.md`: DNS alias rebalance details.
