# VXcloud Launch UI Polish — Tasks for Codex

Status: pre-launch (going live in a few hours).
Goal: bot + Mini App + install flow feel like one polished product. No new features.
Rules: do NOT touch DB schema, payment provider code, HAProxy/cluster code, or auth. UI-only.
Read first (in this order, then start):
1. `guide/mini_app_ux_policy.md`
2. `guide/bot_ux_policy.md`
3. `AGENTS.md`

When you finish, run the verification block at the bottom and report back which files you changed plus screenshots of the 4 key screens (My VPN, Access card, Install page, Open-app retry page) at iPhone width (375px).

---

## P0 — must ship before launch

### 1. Install page (`web/templates/cabinet/install.html`) — make it feel like one decision, not a wall of cards

Current issue: the page shows the device tabs, then a status string, then a `<div id="install-apps">` rendering every app for the platform as a card with badges, then the "Подключить" CTA, then a manual section. For a normal user that's 6+ visual blocks before the primary action. The conversation with Tigran landed on: detect device → recommended app + one big "Подключить" → "У меня другое приложение" reveals the rest.

Do this:
- Make the primary `Подключить` CTA the very first thing under the H1 (move it out of `account-install-connect`).
- Show only the **recommended** app for the detected platform as a single highlighted card (use the `recommended: true` flag from `INSTALL_APP_MATRIX` in `web/cabinet/views.py:78`). Do NOT render the full per-platform list by default.
- Below the recommended card, add one button: `У меня другое приложение`. Tapping it reveals the full app list (the current `renderApps()` output) inline.
- Move "Manual install / clipboard" under a second collapsed section (`details/summary` is fine), titled `Установить вручную`.
- Keep the platform tabs, but render them as a small row above the H1 as a quiet secondary control, not a hero block. The auto-detected platform should be selected; the user only touches the row if detection is wrong.
- iOS App Store country note: keep it, but only show inside the iOS recommended-app card, not as a separate banner above status.
- Status text (`#install-status`) is noisy — remove it. The CTAs already speak for themselves.

Acceptance: on iPhone width, first viewport shows H1 + "Подключить" + one recommended app + "У меня другое приложение" + "Установить вручную". No horizontal scroll. No more than ~480px tall above the fold.

### 2. Install matrix (`web/cabinet/views.py:78` `INSTALL_APP_MATRIX`) — fill out Windows and macOS

Right now `windows` has only Furious, `macos` has Furious + Shadowrocket. The bot UX policy and dashboard hint at Hiddify, Nekoray, v2rayN, V2Box for desktop. Add them:
- `windows`: Hiddify (recommended), Nekoray, v2rayN, Furious (keep as alt).
- `macos`: Hiddify (recommended), V2Box, Streisand, Furious.
- For each new entry include `key`, `name`, `label`, `install_url` (use the official release/store URL — search `github.com/hiddify/hiddify-next`, Microsoft Store, App Store). Do NOT invent deeplink schemes you can't verify; leave `import_url_template` off if unsure.
- `recommended: True` should appear once per platform.

### 3. Open-app retry page (`web/templates/cabinet/open_app.html`) — polish the auto-sequence UX

Current issue: shows a `<textarea>` with the raw subscription URL, all deeplink buttons stacked, and an info message about V2Box. For an auto-sequence flow the user shouldn't see the raw URL textarea by default — it makes the page look like a debug screen.

Do this:
- Replace the visible `<textarea id="deeplink-box">` with a hidden `<input type="hidden">` used only as the copy source. Show a single `Скопировать ссылку` button that calls the existing `copyLink()`.
- Add a top status block: "Пробуем открыть приложение N из M…" that updates as `openNext()` advances (`index` is already tracked).
- Add a "Не открылось, попробовать следующее" button that triggers the next `openNext()` immediately when the user knows the current attempt failed (don't only rely on the `visibilitychange` heuristic).
- After the last app is tried, swap the layout to: `Не получилось автоматически` + 3 buttons: `Установить рекомендуемое приложение` (link to install page for the active platform), `Скопировать ссылку`, `Открыть инструкцию` (link to `/account/?view=instructions`).
- Keep the existing Streisand/V2Box/v2rayTun/HAPP/Hiddify retry-on-return logic, it's good.

Acceptance: when a user lands on `/open-app/?mode=ios-auto&u=…`, they see "Пробуем открыть Streisand…" with one obvious "не открылось" button, not a textarea full of URL.

### 4. My VPN dashboard (`web/templates/cabinet/dashboard.html`) — tighten action ordering on the access card

Current ordering on each active access card (mini view, lines 94–106): `Подключить` (primary) → `Скопировать ссылку` → `QR и доступ` → `Настроить вручную` → `Продлить`. That's 5 buttons in a row inside Telegram. The mini-app policy in `guide/mini_app_ux_policy.md` says copy-link should be the absolute first daily action, and details belong on deeper screens.

Do this on the mini view (`account-page-shell-mini` block):
- Reduce per-card actions to exactly 3: `Подключить` (primary), `Скопировать ссылку`, `QR и доступ`. Move `Настроить вручную` and `Продлить` into a `<details><summary>Ещё</summary>` block at the bottom of the card.
- Same change on the wider `account-access-card` block (lines 267–308) for consistency.
- Keep the "Скопировать ID" pattern on the support card — that one is fine.

### 5. Bot config card (`src/bot.py:1525` `_config_card_markup`) — collapse keyboard rows

Current keyboard for an active subscription:
```
[Подключить]
[Скопировать ссылку]
[QR и доступ]
[Настроить вручную]
[QR, 🔄 Продлить]
[Переименовать, Удалить]
[Назад]
```
That's 7 rows in Telegram. Bot UX policy wants subscription cards link-first with copy as first action.

Do this:
- New layout for active card:
  ```
  [🔗 Скопировать ссылку]
  [⚡ Подключить]
  [📱 QR и доступ]                  # mini app
  [QR][🔄 Продлить]
  [Настроить вручную]               # mini app, only if user explicitly needs it — keep but move down
  [Переименовать][Удалить]
  [Назад]
  ```
  Reasoning: `copy_text` is what 95% of users actually need. Auto-import is a faster shortcut for the rest. The "Настроить вручную" Mini App link is a power-user fallback — it can stay, but not above QR/Renew.
- For expired (`renewal_first=True`): `[🔄 Продлить]` first row, then `[🔗 Скопировать ссылку]`, then `[📱 QR и доступ]`, then `[QR]`, then management row, then back. (Keep current intent, just normalize labels and remove `Настроить вручную` — they can't connect anyway.)
- Add the same emoji prefixes (`🔗`, `⚡`, `📱`, `🔄`) consistently — the bot UX policy permits icons on primary CTAs.

### 6. WordPress device instructions — confirm pages exist

Tigran asked earlier for `/instructions/iphone/`, `/instructions/android/`, `/instructions/windows/`, `/instructions/macos/` as WordPress pages, plus `/instructions/` hub.

Do this:
- Check `wordpress/wp-content/plugins/vx-site-integration/includes/class-vx-site-importer.php` and the seed JSON at `wordpress/import-data/` to confirm those page slugs are in the import seed. If missing, add stub Page entries (title + a `[vx_account_app view="instructions" device="…"]` shortcode block if such a shortcode exists, or plain content placeholder).
- The Mini App's instructions deep links already point to `/account/?view=instructions&device=iphone|android|desktop` — leave those alone. The WordPress pages exist for the public site/SEO and should link OUT to those deep links via a "Открыть инструкцию в кабинете" button.
- This is a stub task: if the importer/seed structure is unclear in 15 min, skip and just add a sentence to `guide/known_issues.md` saying "WordPress device pages still need to be created manually in `/wp-admin/`".

---

## P1 — do if there's time after P0

### 7. Config detail page (`web/templates/cabinet/config.html`) — secondary action sizing

Hero has 6 buttons in `account-config-hero-actions` (lines 13–22). On Telegram width that wraps to 3 rows. Reduce to: `Подключить` (primary), `Скопировать ссылку`, `QR и доступ` anchor. Move `Настроить вручную`, `Продлить`, `Мой VPN` into a smaller secondary row below using `account-secondary-button-large` only for `Продлить`.

### 8. Empty state copy (`web/templates/cabinet/dashboard.html` line 113 and 332)

Current empty-state copy on mini and full view both say "Активируйте пробный период или купите доступ". Make them identical and add the trial badge mentioned in `guide/mini_app_ux_policy.md`:
```
Без карты · 7 дней
```
Render this as a small pill above the H1 when `telegram_trial_url` is set and there are no subs.

### 9. Bot home (`src/bot.py` `_send_start_screen` / `_start_message_text`)

Per `guide/bot_ux_policy.md`: home should be short, show active access count + nearest expiry + soon-expiring + expired count. Audit the current text and trim anything that duplicates inline button labels. Don't add new inline navigation.

### 10. Loading polish in Mini App (`wordpress/wp-content/plugins/vx-site-integration/assets/account-app.js`)

Per `guide/mini_app_ux_policy.md` "Loading screens should say what is happening in Russian instead of showing only anonymous skeleton blocks" — find the skeleton render block and replace with a one-line Russian status: `Загружаем кабинет…`.

---

## P2 — post-launch follow-up (do not do before launch)

- True "scan installed apps" flow — platform doesn't allow it. Documented decision is "guided retry," already implemented in P0 #3.
- Splitting `src/bot.py` into `src/bot/flows/` — the policy explicitly says don't split before UX is stable.
- Adding more payment providers, new node types, anything in `src/cluster/`.
- Editing 3x-ui inbound config or HAProxy templates.

---

## Verification (run all of these before reporting done)

```bash
cd /Users/tigran/Desktop/MyProjects/VXcloud
.venv/bin/python web/manage.py check
.venv/bin/python -m py_compile src/bot.py web/cabinet/views.py
.venv/bin/python -m unittest tests.test_account_app_state_resilience_unit
.venv/bin/python -m unittest tests.test_account_miniapp_css_unit
.venv/bin/python -m unittest tests.test_bot_main_menu_unit
.venv/bin/python -m unittest tests.test_account_subscription_delete_unit
.venv/bin/python -m unittest discover -s tests
```

Then start the local server and screenshot at iPhone 375px width:
```bash
.venv/bin/python web/manage.py runserver 0.0.0.0:8000
```
Open in a 375px-wide browser:
- `http://127.0.0.1:8000/account-app/?embed=1` — My VPN
- `http://127.0.0.1:8000/account-app/config/<id>/?embed=1` — Access card
- `http://127.0.0.1:8000/account-app/install/<id>/?embed=1` — Install page
- `http://127.0.0.1:8000/open-app/?mode=ios-auto&u=https://vxcloud.ru/account/feed/<token>/` — Auto-import retry

If any of P0 #1, #3, #4, #5 don't fit on the first 700px vertical without scroll on iPhone width, fix before reporting done.

---

## What to commit

One commit per task is fine, but small focused PR-size changes only. Commit message style (matches `AGENTS.md`):
- `Tighten install page to one decision`
- `Polish open-app auto-sequence UX`
- `Reorder bot config card actions`
- `Trim My VPN access card actions`

Do NOT:
- commit `.env`, generated staticfiles, DB dumps
- run `makemigrations`
- touch anything outside `web/templates/cabinet/`, `web/cabinet/views.py` (matrix only), `src/bot.py` (markup only), `wordpress/wp-content/plugins/vx-site-integration/assets/`, and the targeted test files
