# VXcloud Agent Workflow

Follow this workflow for most code changes.

## Before Editing

```powershell
git status --short
```

Read the relevant files first. Prefer `rg` where available, but on Windows
PowerShell `Select-String` is acceptable if `rg` has access issues.

Useful scans:

```powershell
Get-ChildItem -Recurse -File -Include *.py |
  Where-Object { $_.FullName -notmatch '\\.git\\|\\.venv\\|__pycache__|staticfiles' } |
  Select-String -Pattern 'XUIClient\(|Cloudflare|_run_async_from_sync|TODO|FIXME|bootstrap|raw_vless'
```

## Common Verification

Run at least the checks matching the touched area:

```powershell
python web\manage.py check
python -m py_compile web\cabinet\views.py web\backoffice\views.py src\xui_client.py src\dns_alias.py
python -m unittest discover -s tests
```

For Docker/deploy-sensitive changes:

```powershell
docker compose --env-file .env config
```

For Django static/UI changes, also check that templates load and no Bootstrap
visual dependency was reintroduced into public account pages.

## Slow Request Bug Pattern

If a web request calls XUI, DNS, payment, or another remote service:

- use short explicit timeout values
- avoid serial loops across nodes
- use `asyncio.gather(..., return_exceptions=True)` where safe
- let inactive subscription delete proceed locally even if remote cleanup fails
- log actionable warnings for manual cleanup
- write regression tests

Relevant env defaults:

- `XUI_API_TIMEOUT_SECONDS=12`
- `XUI_API_MAX_RETRIES=1`
- `BACKOFFICE_XUI_TIMEOUT_SECONDS=6`
- `BACKOFFICE_XUI_MAX_RETRIES=0`
- `CLOUDFLARE_API_TIMEOUT_SECONDS=8`

## Backoffice Node Work

When changing node CRUD, sync, or rebalance:

- preserve health gating
- exclude inactive, disabled, unhealthy, backfill, incompatible, or cooldown
  nodes from assignment/rebalance
- do not put a new node into LB automatically
- keep DNS alias flow separate from HAProxy fallback
- update the runbook if operator steps changed

## Documentation Memory

Treat runbooks as project memory. When an operator session teaches a new exact
command, field mapping, failure mode, or recovery step, update the matching file
in `guide/` before closing the task. Documentation should improve over time as
we learn from real VXcloud setup, deploy, and support work.

For node setup specifically, keep `guide/add_vpn_node_runbook.md` current with:

- installer prompts that behave unexpectedly
- exact `/ops/` field mappings
- current DNS-alias versus HAProxy responsibilities
- validation commands from the main server and from the node
- health, backfill, and rebalance acceptance criteria

## Account UI Work

Rules:

- black/white first, red for links only
- minimal borders and strong spacing hierarchy
- no Bootstrap visual components
- same header/footer rhythm as WordPress
- responsive at 375, 430, 768, 1024, and desktop widths
- login buttons must be visible without hover and keyboard-focusable
- long subscription URLs must not break layout

## Commit Guidance

Keep commits focused. Good examples:

- `Make subscription cleanup fail fast`
- `Fix Telegram login callback polling`
- `Tighten account layout responsiveness`
- `Add node readiness guardrails`

Do not commit local `.env`, logs, generated staticfiles, or database dumps.
