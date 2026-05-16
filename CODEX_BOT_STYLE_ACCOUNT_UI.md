# Bot-style account UI — design spec for Codex

Reference mockup: `account_ui_preview.html` (open it in a browser at iPhone width). All four target screens are mocked as a Telegram-like one-column app: stacked "message bubble" cards, full-width inline-keyboard buttons, no sidebars, no hero banners, no two-column layouts.

This spec **supersedes** P0 #1, #4, #7 of `CODEX_LAUNCH_UI_TASKS.md`. The other items in that file still stand.

## Visual rules (apply to every account-app/ template)

- Background: `#f4f4f5`. Cards: `#ffffff`, `border-radius: 10px`, padding `12–14px`, soft shadow `0 1px 2px rgba(0,0,0,.04)`.
- Typography: system font stack. Body `15px`, card title `16px/600`, eyebrow `11px uppercase letter-spacing .06em color #6b6b70`.
- Single column. Max content width inside the card stack = full viewport. Never two-column inside `/account-app/`.
- Buttons look like Telegram inline keyboard:
  - Full-width by default (`display: grid`), 1 or 2 per row max.
  - Primary: `background: #2481cc; color: #fff;` (Telegram blue).
  - Secondary: `background: #f0f0f3; color: #111;`.
  - All buttons: `border-radius: 8px; padding: 12px 14px; font-size: 14px;`.
- Status as pills: `Активен` green `#e6f4ea / #1f7a3a`, `Скоро истекает` amber, `Истёк` red. Inline next to the date line, never as a big banner.
- No gradients, no large shadows, no hero CTAs `font-size: 32px`, no `letter-spacing` games.

## Screens

### 1. Мой VPN  (`web/templates/cabinet/dashboard.html`, `account-page-shell-mini` block)

Replace the current hero + actions + access list structure with this stack:

```
[ identity card — tight ]
  ID клиента: VX-…
  Активных доступов: N · ближайший до DD.MM

[ access card — repeats per active subscription ]
  eyebrow: Доступ
  title: <display_name>
  line: действует до DD.MM.YYYY · pill(Активен/Истёк)
  buttons:
    [🔗 Скопировать ссылку]                  ← primary, full width
    [⚡ Подключить]   [📱 QR и доступ]        ← row of 2
    <details>Ещё</details>
      [🔄 Продлить]   [Настроить вручную]

[ utility card — tight ]
  line: Купить ещё доступ или открыть инструкцию.
  buttons:
    [💳 Купить]   [📖 Инструкция]
    [🆘 Поддержка]
```

Drop the `account-mini-hero` heading "Мой VPN" — Telegram's own header bar already shows it. Drop the long subtitle paragraph.

### 2. Доступ  (`web/templates/cabinet/config.html`)

Same stack pattern. Order:

```
[ status strip — tight ]
  pill + действует до DD.MM.YYYY

[ subscription link card ]
  eyebrow: Подключение
  title: Ссылка подписки
  line: short import hint (3 actions in one sentence)
  buttons:
    [🔗 Скопировать ссылку]                ← primary
    [⚡ Подключить автоматически]
  urlbox (truncated, with copy icon)

[ QR card ]
  eyebrow: QR
  title: QR для импорта
  qr image (max-height ~180px in the Mini App)
  line: Сканируйте только если приложение не умеет импортировать ссылку.

[ identity / settings card — tight ]
  kv: ID клиента / VX-…
  kv: ID доступа / #214
  buttons:
    [🔄 Продлить]   [Переименовать]
```

Remove the existing `account-config-hero-actions` row (it currently has 6 buttons). Remove the secondary aside layout (`account-config-side`). The QR is just one card in the same column.

### 3. Подключить  (`web/templates/cabinet/install.html`)

Replace the current 6-card layout (hero + warning + section + tabs + apps + connect + manual) with:

```
[ device tabs card — tight ]
  pill-tabs: iPhone / Android / Windows / Mac (active highlighted)
  line: Устройство определено автоматически. Можно сменить выше.

[ step 1 card ]
  eyebrow: Шаг 1
  title: Установите приложение
  line: <recommended app for platform> — короткое описание
  button: [Установить <app>]
  (iOS only) line: App Store country tip + link

[ step 2 card ]
  eyebrow: Шаг 2
  title: Подключите ссылку
  line: Ссылка скопирована. Мы попробуем открыть apps по очереди.
  buttons:
    [⚡ Подключить]                          ← primary
    [У меня другое приложение]               ← reveals app list inline

[ manual install card — tight ]
  <details>Установить вручную</details>
    line + urlbox + steps (3 short lines)
```

When "У меня другое приложение" is tapped, render the rest of the platform's apps as plain rows under that card (use existing `INSTALL_APP_MATRIX` data, but in a flat list, not heavy cards).

### 4. /open-app/  (`web/templates/cabinet/open_app.html`)

Replace the current textarea + button stack with:

```
[ active step card ]
  eyebrow: Шаг N из M
  title: Пробуем открыть <app>
  line: instruction + "вернитесь сюда"
  progress strip: ▰▱▱
  buttons:
    [Открыть <app>]                          ← primary
    [Не открылось — попробовать <next>]      ← always visible

[ manual fallback — tight, collapsed ]
  <details>Скопировать ссылку вручную</details>
    urlbox

[divider] если ничего не помогло

[ rescue card — tight ]
  buttons:
    [Установить рекомендуемое приложение]
    [📖 Открыть инструкцию]
    [🆘 Поддержка]
```

When `index >= links.length`, swap the active card for: `Не получилось автоматически` + the rescue card becomes primary.

## CSS

Either:
- **A (preferred)** — add a `.vx-account-bot/` block of styles inside `web/static/css/site.css`, scoped under `body.vx-account-embed` (the embed marker is already used).
- **B** — add the styles inline at the top of each cabinet template inside `{% block extra_head %}`.

The mockup file uses CSS variables (`--accent`, `--surface`, `--ink`, `--muted`, `--line`, `--radius`). Lift those into `site.css` so all four templates share them.

## What stays

- All existing Django views, URL patterns, context keys, JS event handlers (`js-copy-config`, `copyCfg()`, `openNext()`, `renderApps()`).
- `INSTALL_APP_MATRIX` keys and shape — only the rendering changes.
- Telegram WebApp `initData` auth, magic link, support hub logic.
- The browser fallback layout (`/account/` outside Mini App) — leave the wider two-column layout alone, only `/account-app/` and `?embed=1` get the bot-style stack.

## What to remove

- `account-mini-hero`, `account-config-hero`, `account-install-hero` blocks (Telegram bar already gives the title).
- All `account-dashboard-side` / aside layout in `dashboard.html`.
- Status text element (`#install-status`) and the `account-install-connect` block in `install.html`.
- Visible `<textarea id="deeplink-box">` in `open_app.html` — replace with hidden input + urlbox in collapsed `<details>`.

## Acceptance

At iPhone 375 × 812 viewport in `?embed=1`:
- Each screen's first 700px tall fits: `[Telegram bar] + [first 1–2 cards] + first primary button`.
- No horizontal scroll on any screen.
- Buttons are tappable (≥44px tall).
- Open `account_ui_preview.html` next to your live screenshots — visual rhythm should match: card spacing, button width, eyebrow weight, pill style.

## Verification

```bash
cd /Users/tigran/Desktop/MyProjects/VXcloud
.venv/bin/python web/manage.py check
.venv/bin/python -m py_compile web/cabinet/views.py
.venv/bin/python -m unittest tests.test_account_app_state_resilience_unit tests.test_account_miniapp_css_unit tests.test_account_subscription_delete_unit
```

Then `runserver` and screenshot the four `/account-app/` screens at 375px width. Compare to `account_ui_preview.html`.
