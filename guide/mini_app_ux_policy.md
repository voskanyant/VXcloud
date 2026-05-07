# VXcloud Mini App UX Policy

Last updated: 2026-05-07

## Role

The Telegram Mini App is the primary customer account surface for:

- account status;
- active and inactive VPN accesses;
- QR and subscription access details;
- renewal and purchase entry points;
- short support and instruction entry points.

The Telegram bot stays a command layer. The public browser account pages stay a
fallback and can use a wider layout.

## Current Implementation Contract

- Telegram opens the Django `/account-app/` pages. WordPress account shortcode
  styles do not control the Mini App dashboard.
- Customer account templates live in `web/templates/cabinet/dashboard.html` and
  `web/templates/cabinet/config.html`; the matching account CSS lives in
  `web/static/css/site.css`.
- Do not edit WordPress header/footer to fix account body layout. The account
  body should fit under the inherited WordPress shell.
- The embedded dashboard is a separate mobile-first account surface, not the
  desktop account page squeezed into Telegram.
- The first dashboard screen is connect-first: `Мой VPN`, `Ваши доступы`, and
  `Подключить` must be visible before QR or secondary management.
- Each active access should include a short mini instruction: copy the
  subscription link, open Streisand/V2Box/v2rayNG, press `+`, import from
  clipboard.
- QR remains available as a fallback on the access detail page, below the
  subscription-link copy action.
- Embed pages must define their own account CSS variables and fit a narrow
  Telegram viewport without horizontal clipping.

## Dashboard Rules

- The Mini App dashboard must be compact and mobile-first.
- Do not reuse the full desktop account layout without embed-specific styling.
- The first viewport should show the account title, primary actions, and the
  user's VPN accesses without large empty vertical gaps.
- The native Telegram dashboard title should be task-first (`Мой VPN`), not a
  generic browser-account heading such as `Личный кабинет`.
- Keep the top subtitle short and operational. Use compact status metrics such
  as active access count and nearest expiry instead of a long marketing intro.
- The access list heading should say `Ваши доступы`, not a device-oriented
  label such as `Устройства`.
- Current dashboard metadata should render as a quiet identity footer after the
  access list and help block. It may show username, client ID with copy, Telegram
  link state, settings, and logout, but it must not look like the main content.
- Account metadata and summary stats are secondary in the Mini App. They should
  appear below the access list and fit in a tight mobile grid.
- Instruction and support entry points should appear as a compact help block
  near the access list. Account settings and logout are secondary account
  controls and should not compete with buy, renew, QR, or support actions.
- Subscription cards on the dashboard should show only:
  - access name;
  - active/inactive status;
  - expiration label;
  - primary connection actions in this order: `Подключить`,
    `Скопировать ссылку`, `QR и доступ`, `Настроить вручную`.
- On dashboard subscription cards, `Подключить` is the primary daily action.
  Renewal is secondary and must still target an explicit subscription id.
- The dashboard hero CTA should also be contextual: if the user has an active
  access, the primary action opens that access's `QR и доступ`; buying another
  access becomes secondary. If the user has no access at all, the primary action
  should open the bot trial deep link for `7 дней бесплатно`; paid checkout is
  the secondary path.
- Renew actions must target an explicit subscription id. If more than one access
  can be renewed, the top renew shortcut should move the user to the access
  list instead of starting checkout without a target.
- Rename fields, raw subscription links, local IDs, and delete controls belong
  on deeper detail screens, not expanded by default in the dashboard.
- Rename controls on detail screens should use access language such as
  `Название доступа`; avoid device-oriented labels unless the flow is truly
  about one physical device.
- Native WordPress Mini App dashboard cards should not render those deeper
  controls hidden in the markup. Keep them out of the list screen entirely.
- Empty dashboard states should be actionable. Show a short Russian explanation
  plus direct actions to start the 7-day trial in the bot, buy access, and open
  the compact instruction screen.
- When a trial deep link is available, the no-access dashboard should look like
  a trial-start panel, not a generic empty state. A short badge such as
  `Без карты · 7 дней` is acceptable; paid checkout remains secondary.

## Instruction Rules

- Bot and Mini App instruction links should open `/account-app/?view=instructions`
  or a device variant such as `device=iphone`, not the generic public blog index.
- The Mini App instruction view should not show the public WordPress header,
  blog article chrome, or the normal account dashboard below the guide.
- The native instruction title should be short and task-first, for example
  `Подключение`.
- Show the current access or empty-access block before device tabs so the user
  sees the copy-link/access path before choosing platform-specific steps.
- Device choices should look like compact tabs/buttons and keep the selected
  device obvious.
- In Telegram, device tabs and step rows should be app-control size, not
  article/navigation size. Keep them tight enough that access state, tabs, and
  the first step are visible without a long scroll.
- Setup steps should be structured as a short numbered list, not one long
  paragraph with inline numbers.
- When the account already has an access, the instruction view should show the
  primary access name and a direct `Скопировать ссылку` action inside the Mini
  App. A secondary `QR и доступ` action can remain for scanning or advanced
  details. Do not make the user return to the dashboard just to find the access.
- If there is no access yet, the same area should explain that the user needs a
  trial or purchase first. The primary action should open the bot trial deep
  link when available; otherwise route them back to `Мой VPN`.
- The instruction view must always keep a direct `Мой VPN` action visible,
  even when the primary action opens QR/access.
- Legacy instruction fallback renderers must keep the same trial-first empty
  state and persistent `Мой VPN` return action as the primary instruction view.
- Long editorial guide posts can remain public browser content, but Telegram
  users should first get the compact cabinet guide with direct access to `Мой VPN`,
  subscription link, QR, and support.
- Instruction screen labels, access hints, empty states, and step text must
  stay readable Russian; no mojibake in the active renderer.

## Config Detail Rules

- In the Mini App, subscription detail pages should be copy-link first. QR is a
  useful fallback, not the primary method.
- Status, all-config navigation, rename, and other management details should
  sit below the primary import actions.
- QR panels should fit comfortably in the first mobile screen. Do not let the
  QR image grow to desktop size inside Telegram; keep nearby status/link fields
  compact so copy and scan actions stay close together.
- The access/detail page should include a short connection reminder near the
  primary copy action: copy the subscription link, open Streisand, V2Box,
  v2rayNG, Hiddify, or Nekoray, press `+`, then import from clipboard. The QR
  panel can stay below as a fallback if scanning is easier.
- The QR panel should include a short caption so the user knows the QR belongs
  in the VPN client, not in Telegram.
- The connection reminder should be compact numbered/action rows, not another
  paragraph block.
- Renewal can appear beside copy/open actions only when it targets the current
  subscription id. Delete belongs in a lower management block, never beside QR
  or copy.
- Customer-visible detail copy should say `доступ`, `QR`, and `ссылка подписки`.
  Avoid `конфиг` in destructive confirmations, empty/error states, and field
  labels even if route names and CSS classes still use config internally.
- Legacy QR/access fallback renderers must follow the same structure as the
  primary detail screen: QR hint and quick guide near the QR, delete in the
  lower management block, and `Название доступа` for rename fields.
- The desktop browser fallback can keep the wider two-column layout.

## Account Page Redesign Notes

- The public `/account/` page and the native `/account-app/` dashboard share the
  same customer priorities: connect first, then copy the subscription link,
  then show QR/manual setup, then expose renewal and management actions.
- The public account page should use the same compact account structure as the
  Mini App. It may center the content on desktop, but it should not become a
  separate desktop dashboard.
- The Mini App dashboard must not be a squeezed desktop page. It uses compact
  rounded blocks, a short identity line, link-first access cards, and one-tap
  `Скопировать ссылку` actions.
- The access detail page should read as a setup page: heading, copy-link CTA,
  subscription URL field, short import steps, status, then QR fallback.
- The instruction page must include a direct copy-link CTA when an active access
  exists. It should not force the user to go back to the dashboard only to copy
  the subscription link.
- Every account surface should be checked with fresh screenshots at phone,
  Mini App, and desktop sizes before pushing UI changes.

## Support Rules

- The Mini App support view should be a compact help hub, not a dead-end note.
- Show the customer's VXcloud client ID when it is available so they can paste
  it into Telegram support.
- The support prompt should ask for one useful message: what is not working,
  device, and when the issue started.
- When a customer ID is available, show it in a compact row with a copy button
  and a specific `ID скопирован` confirmation.
- The support page may include a few copyable Russian message templates for
  common cases such as connection failure, sites not opening, and payment or
  renewal issues. Templates should include the client ID when available and
  should not replace the primary Telegram support action.
- The Telegram contact action should appear first in the body in its own compact
  contact block. Client ID, templates, and explanation text belong below it.
- In Telegram, support contact, client ID, and template blocks should use tight
  app-control sizing so the first screen shows both the support CTA and copyable
  customer ID.
- Legacy support fallback renderers must follow the same order: Telegram
  contact first, copyable client ID second, templates next, and dashboard/guide
  navigation last.
- Keep the primary support action in Telegram until richer ticket history and
  in-app forms are implemented.
- Support screen labels and helper text must stay readable Russian. The primary
  Telegram action should be visually stronger than secondary guide/dashboard
  navigation.

## Auth Rules

- The Mini App auth screen must be Russian and Telegram-first.
- Telegram WebApp `initData` sync is the primary Mini App login path. The
  Telegram login widget and email/password form are fallbacks.
- The native account shell should mark WebApp auth as synced only after the
  backend accepts `initData`. Missing Telegram data, network errors, or rejected
  responses must remain retryable on later view loads.
- If the auth form appears inside Telegram, show a short status hint explaining
  that Mini App login is normally automatic and the Telegram widget is the first
  fallback.
- Email/password auth may remain visible, but it must be visually labeled as
  the fallback path and placed in a secondary contained block below Telegram.
- Auth copy should stay short: use a direct title such as `Вход в VXcloud`,
  explain that opening from the bot is normally automatic, and label email as a
  backup path rather than equal primary navigation.
- Auth tabs, Telegram fallback, and email form controls should use compact
  Telegram app sizing. Avoid large desktop form spacing in the Mini App.
- Support/help links on auth screens should use the native Telegram link opener
  when the configured support target is a Telegram URL.
- Telegram account linking screens are customer UI too. Keep code, expiry,
  regenerate, bot-open, and dashboard-return labels readable Russian.
- Link codes should be copyable in one tap with a specific `Код скопирован`
  confirmation because Telegram deep links can fail on some clients.
- Native Telegram linking screens should use compact code panels and app-sized
  actions: open bot as the primary action, then regenerate code and return to
  `Мой VPN` as secondary actions.
- Legacy link fallback renderers must use the same native link screen structure,
  copy-code action, and Russian labels as the primary renderer.
- Link screens must not expose internal env var names, raw setup errors, or
  `/start` command syntax as the primary fallback. Tell the user to copy the
  code and send it to the VXcloud bot.
- If the user is unauthenticated and needs help, prefer a Telegram support link
  over sending them to the public instructions/blog index.
- Do not allow mojibake labels in the native auth form, tab labels, help links,
  or password reset link.
- Action toasts and confirmations must also stay readable Russian: copy,
  rename, delete, profile update, link-code, payment, and generic form errors
  are customer UI, not debug text.

## Account Settings Rules

- Account settings are a secondary Mini App page. Keep the screen compact and
  explain that changing profile data does not affect VPN accesses, QR, or
  subscription links.
- Profile fields should be grouped by purpose: login/email for account access,
  and optional display name fields separately. This keeps settings from feeling
  like the main VPN control screen.
- Use `Мой VPN` as the dashboard return label. Do not use verbose browser-style
  labels such as `Назад в кабинет` inside the Mini App.
- Legacy fallback renderers in the native account JS must follow the same
  customer copy rules as the primary renderers; stale browser labels should not
  remain hidden in fallback paths.

## Checkout Rules

- Buy and renew deep links should show a native Mini App progress screen before
  redirecting to the external payment page. Avoid blank pages while the checkout
  order is being prepared.
- Checkout progress screens must be Russian, compact, and include safe secondary
  actions back to `Мой VPN` and support.
- Checkout progress screens should show a simple 3-step status: create order,
  open secure payment, then see the new or renewed access in `Мой VPN`. This
  reduces confusion when provider redirects are slow.
- Checkout screens should also explain what happens after the external bank or
  payment page opens: finish payment, return to `Мой VPN`, and the access will
  update automatically.
- If the bank page opens in an external window, tell the user not to close
  Telegram. If the payment page does not open, send the user back to `Мой VPN`
  to retry or contact support.

## Instructions Rules

- Instruction screens are Mini App task screens, not public blog articles.
- Show the current access state first, then device selection, then a compact
  three-step guide.
- Steps should be short numbered rows: install client, open QR/access, import
  VPN. Avoid long paragraph instructions inside the Mini App.
- The primary action on instruction screens should open the user's QR/access
  when available. Support and dashboard return are secondary actions.

## Error State Rules

- Mini App error states should be compact recovery screens, not standalone red
  debug boxes.
- Always offer safe actions back to `Мой VPN` and support when an account page,
  checkout, or API-backed view cannot load.
- Recovery screens should include one primary `Повторить` action and keep
  dashboard/support as secondary routes.
- Legacy error fallback renderers must use the same compact recovery card as
  the primary error screen, including retry, `Мой VPN`, and support actions.
- Loading screens should say what is happening in Russian instead of showing
  only anonymous skeleton blocks.

## Visual Rules

- Russian is the default UI language for customer-facing text.
- Keep the Mini App close to the VXcloud public style: white background, black
  text, restrained borders, and minimal red links.
- Use radius only where it helps Telegram mobile usability; keep it at 8px or
  less.
- Native Mini App cards, buttons, QR panels, support panels, and instruction
  panels should render without decorative gradients or soft card shadows.
- Native Mini App section and detail headers should be compact: small padding,
  normal letter spacing, and app-scale titles instead of desktop hero-scale
  typography.
- Primary action groups in the Mini App should be explicit, not inherited from
  broad responsive browser rules. Main CTA rows should keep the primary action
  first and full width when that reduces ambiguity.
- Avoid oversized hero typography inside Telegram.
- Avoid viewport-scaled type for compact app surfaces.
- Keep native Mini App letter spacing at `0`; do not use tracked-out labels or
  negative heading tracking inside Telegram.
- Do not hide QR/access details; move them behind explicit actions instead.

## Implementation Notes

- Embed-specific styles are scoped under `body.vx-account-embed`.
- The WordPress native account shell (`vx-site-integration/assets/account-app.*`)
  must also honor `?view=instructions`, `?view=support`, and config routes.
  Bot Mini App buttons often land on `/account/?view=...`, so the JS shell must
  not ignore query-driven account views.
- Config detail routes should work both as `/account/config/<id>/` and as
  `/account/?view=config&subscription_id=<id>` so bot buttons and future deep
  links can use either form safely.
- The WordPress native account shell must load Telegram WebApp JS and POST
  `initData` to `/api/auth/telegram/webapp` before showing the auth form. The
  Telegram login widget is a browser fallback, not the primary Mini App login.
- Telegram handoff links from the Mini App, such as trial activation, support,
  and account linking, should use Telegram WebApp `openTelegramLink` when it is
  available. Keep normal `href` links as browser fallback.
- Deep Mini App views should use Telegram WebApp BackButton when it is
  available. Hide it on the dashboard and auth views; show it on config,
  instructions, support, settings, link, and checkout views. If browser history
  cannot go back, the fallback target is the account dashboard.
- Browser fallback pages under `/account/` should not be broken by Mini App CSS.
- `/account-app/` and `?embed=1` must remain scrollable in Telegram webviews.
- Add regression tests when changing dashboard density, subscription card
  contents, or embed-only layout behavior.
