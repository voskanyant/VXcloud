# VXcloud Mini App UX Policy

Last updated: 2026-05-06

## Role

The Telegram Mini App is the primary customer account surface for:

- account status;
- active and inactive VPN accesses;
- QR and subscription access details;
- renewal and purchase entry points;
- short support and instruction entry points.

The Telegram bot stays a command layer. The public browser account pages stay a
fallback and can use a wider layout.

## Dashboard Rules

- The Mini App dashboard must be compact and mobile-first.
- Do not reuse the full desktop account layout without embed-specific styling.
- The first viewport should show the account title, primary actions, and the
  user's VPN accesses without large empty vertical gaps.
- The native Telegram dashboard title should be task-first (`Мой VPN`), not a
  generic browser-account heading such as `Личный кабинет`.
- Keep the top subtitle short and operational. Use compact status metrics such
  as active access count and nearest expiry instead of a long marketing intro.
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
  - primary actions such as renew, QR, and open details.
- On dashboard subscription cards, opening `QR и доступ` is the primary daily
  action; renewal is secondary and must still target an explicit subscription
  id.
- Renew actions must target an explicit subscription id. If more than one access
  can be renewed, the top renew shortcut should move the user to the access
  list instead of starting checkout without a target.
- Rename fields, raw subscription links, local IDs, and delete controls belong
  on deeper detail screens, not expanded by default in the dashboard.
- Native WordPress Mini App dashboard cards should not render those deeper
  controls hidden in the markup. Keep them out of the list screen entirely.
- Empty dashboard states should be actionable. Show a short Russian explanation
  plus direct actions to buy access and open the compact instruction screen.

## Instruction Rules

- Bot and Mini App instruction links should open `/account-app/?view=instructions`
  or a device variant such as `device=iphone`, not the generic public blog index.
- The Mini App instruction view should not show the public WordPress header,
  blog article chrome, or the normal account dashboard below the guide.
- Device choices should look like compact tabs/buttons and keep the selected
  device obvious.
- Setup steps should be structured as a short numbered list, not one long
  paragraph with inline numbers.
- When the account already has an access, the instruction view should show the
  primary access name and a direct `Открыть QR и доступ` action inside the Mini
  App. Do not make the user return to the dashboard just to find the QR page.
- If there is no access yet, the same area should explain that the user needs a
  trial or purchase first and route them back to `Мой VPN`.
- The instruction view must always keep a direct `Мой VPN` action visible,
  even when the primary action opens QR/access.
- Long editorial guide posts can remain public browser content, but Telegram
  users should first get the compact cabinet guide with direct access to `Мой VPN`,
  QR, and support.
- Instruction screen labels, access hints, empty states, and step text must
  stay readable Russian; no mojibake in the active renderer.

## Config Detail Rules

- In the Mini App, subscription detail pages should be QR and copy-link first.
- Status, all-config navigation, rename, and other management details should
  sit below the primary import actions.
- The QR/detail page should include a short connection reminder near the QR:
  open VPN client, scan QR or copy the subscription link, and use the compact
  instruction page if device-specific steps are needed.
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
- The desktop browser fallback can keep the wider two-column layout.

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
- The Telegram contact action should appear near the top in its own compact
  contact block. Templates and explanation text belong below it.
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
- Telegram account linking screens are customer UI too. Keep code, expiry,
  regenerate, bot-open, and dashboard-return labels readable Russian.
- Link codes should be copyable in one tap with a specific `Код скопирован`
  confirmation because Telegram deep links can fail on some clients.
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

## Instructions Rules

- Instruction screens are Mini App task screens, not public blog articles.
- Keep device selection at the top, then show the current access state, then a
  compact three-step guide.
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
- Deep Mini App views should use Telegram WebApp BackButton when it is
  available. Hide it on the dashboard and auth views; show it on config,
  instructions, support, settings, link, and checkout views. If browser history
  cannot go back, the fallback target is the account dashboard.
- Browser fallback pages under `/account/` should not be broken by Mini App CSS.
- `/account-app/` and `?embed=1` must remain scrollable in Telegram webviews.
- Add regression tests when changing dashboard density, subscription card
  contents, or embed-only layout behavior.
