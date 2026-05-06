# Bot UX Policy

Last updated: 2026-05-06

## Role Split

The Telegram bot is the command/control layer. It should stay small and fast:

- onboarding
- reminders and emergency notices
- quick subscription actions
- Telegram Stars payment
- support message intake
- payment confirmations

The Telegram Mini App is the customer dashboard:

- account overview
- subscriptions and config cards
- QR and subscription URLs
- card checkout
- renewal
- instructions
- richer support history

Django remains the source of truth for account data, Telegram auth validation,
payments, subscriptions, and ops. 3x-ui, Xray, and Cloudflare are execution
layers only.

## Language And Icons

Customer-facing bot defaults are Russian. English should only remain for product
or platform names where users expect them: VXcloud, VPN, Telegram, Stars,
iPhone, Android, Windows, and macOS. In customer copy, describe the Telegram
Mini App as "кабинет внутри Telegram" unless the exact platform term is needed.

Icons are allowed in the persistent menu and primary call-to-action buttons.
Do not add icons to every small contextual button. This keeps the bot scannable
without turning every screen into a wall of buttons.

## Persistent Menu

Default persistent menu:

- 🛡 Мой VPN
- 🎁 7 дней бесплатно
- 💳 Купить
- 🔄 Продлить
- 📖 Инструкция
- 🆘 Поддержка
- 📱 Кабинет

The menu should be visible after normal bot flows. Hide the full menu only while
waiting for free text input:

- support message
- subscription rename
- future promo code or similar input states

When input completes, is empty, or is cancelled by a menu button, restore the
persistent menu. The bot should also understand old plain labels such as
"Мой VPN" and "Кабинет" so users with a cached keyboard are not stuck.
Slash commands that interrupt support, rename, or other text-input states must
also restore the persistent menu before opening the requested screen.
Inline buttons from older messages follow the same rule: normal actions cancel
the text-input state and restore the menu; actions that start another input
state replace it and keep only `Отмена` visible.

During text input states, show a one-button `Отмена` keyboard instead of a blank
keyboard. This keeps the full menu hidden while giving users an obvious escape.

## Inline Buttons

Use inline buttons only inside contextual messages. Avoid duplicating the full
main menu inside inline keyboards.

Good contextual examples:

- 📱 QR и доступ for buttons that open one exact subscription
- 📱 Кабинет for buttons that open the dashboard or support history
- QR
- 🔄 Продлить
- Скопировать ссылку
- Переименовать
- Удалить
- Отмена for destructive confirmations

Do not add a global inline "Назад" button to every screen. Users navigate with
the persistent menu. Add `Назад` only on deep contextual screens where it returns
to a clear parent in the same flow, for example a subscription card back to
`🛡 Мой VPN`, renewal checkout back to subscription selection, or an instruction
subpage back to the instruction hub. CMS inline JSON that contains only a global
Back/Назад button should be ignored by the bot.

## Flow Rules

- `/start`: short welcome, compact subscription summary, persistent menu.
  The home copy should simply ask the user to choose an action in the menu and
  mention that the cabinet inside Telegram contains QR, card payment,
  instructions, and settings. Show active access count, nearest expiry, soon
  expiring count, and expired access count when available. If all access is
  expired, say that there are no active accesses and point the user to the
  persistent renew menu item. Do not add duplicate inline navigation to the
  home screen.
- Legacy slash commands should route to the same current screens as the
  persistent menu. For example `/myvpn` must use the same My VPN flow instead
  of old active-subscription-only delivery copy. Customer slash commands must
  also clear active text-input states such as support message and rename before
  opening the requested screen. Keep slash command coverage aligned with the
  main menu: `/myvpn`, `/trial`, `/buy`, `/renew`, `/instructions`, `/support`,
  and `/app` or `/cabinet`.
- My VPN: if the user has one subscription, open its card directly. If the
  user has several subscriptions, show a compact list sorted by active and
  nearest expiry first. Status icons are allowed in this list because they help
  users spot active, expiring, and expired devices quickly. The list should show
  a short count summary and put the same status icon on each selector button.
  Keep this list to one button per device; do not add QR/renew/app action rows
  below every device. Those actions belong on the selected subscription card.
  Subscription cards contain QR, renew, copy, rename, and delete actions. Do not print long
  subscription or raw connection links in the message body by default; keep them
  inside QR and copy buttons. Delete confirmations should say "device" and
  "access", not "config", "3x-ui", "node", or other execution-layer wording.
  Rename input should normalize whitespace and reject overlong names with a
  clear limit instead of silently truncating. Empty My VPN should offer the
  7-day trial first, then card and Stars purchase actions. Active subscription
  cards are link-first: `🔗 Скопировать ссылку` is the first action, then
  `📱 Открыть доступ`, then QR and renewal. Expired subscription cards still
  put `🔄 Продлить` first, then copy link, then access/QR. Subscription card
  copy should give a short practical import hint: copy the subscription link,
  open Streisand, V2Box, or v2rayNG, press `+`, then import from clipboard.
  Do not print long subscription or raw connection links in the message body.
  QR messages for expired devices must warn that renewal is needed and include
  the same renewal-first action layout.
- Trial: visible menu entry, one activation CTA, short one-time-use copy, then
  compact success with expiry plus cabinet, QR, and guide after activation. If
  activation fails, show a clear Russian failure message and a support action;
  do not leak node or provisioning internals to the customer. If the trial is
  already used and the user has active access, point to the current subscription
  instead of pushing another purchase.
- Buy: two payment choices only, card checkout in Mini App and Stars in bot.
  Copy should say that one access is for one device and mention where access
  appears after payment, not repeat delivery mechanics. If the user already has
  active access, the buy screen should make "buy another device" and "renew
  this access" explicit and target renewal to the active subscription when
  possible.
- Renew: always target one explicit subscription before showing payment. If
  several subscriptions can be renewed, show the same active/nearest-expiry
  ordering and status icons as My VPN. Keep the selector to one button per
  device; do not add cabinet or payment rows until the user selects a device.
  Copy should say renewal adds time to the selected device, not that it creates
  a new access. If there is nothing to renew, offer the 7-day trial first, then
  card and Stars purchase actions.
- Payment success: compact confirmation only. Do not explain every possible
  action in prose when the buttons already show QR/access. Do not add an
  "Открыть в боте" button on success screens; the user is already in the bot.
- Stars invoices: if the bot sends a pre-invoice notice, keep it short and
  specific to buy or renew. Do not add carrier or platform payment advice to
  every invoice screen. Button labels should distinguish the action: use
  `Купить за Stars` for new access and `Продлить за Stars` for renewal. Payment
  CTA buttons should show the price when it is known, for example
  `Купить за Stars · 250 Stars` or `Купить картой · 249 RUB`.
- Reminders: short expiration notices that name the device and include direct
  `🔄 Продлить` and `📱 QR и доступ` Mini App buttons. Do not use node, x-ui,
  inbound, or execution-layer wording in customer reminders.
- Support: hub first with a short prompt and user ID. The hub should explain
  that the answer comes in Telegram and ask for one useful message: device,
  what does not work, and when it started. Keep two actions: `✍️ Написать в
  поддержку` and `📱 Поддержка в кабинете`. Writing a message hides the menu until
  submit/cancel. Overlong messages should not create tickets; keep the user in
  input mode, explain the limit, and keep only `Отмена` visible.
  Submitted-ticket confirmation should restore the persistent menu, include the
  ticket number, and point to `📱 Кабинет` -> `Поддержка` for support history
  without replacing the menu with inline navigation.
- Instructions: bot shows only device choices and opens Mini App guide pages.
  Copy must say the full guide opens in the cabinet, not in a separate site.
  Legacy cached labels and typed phrases such as "Как подключить" should still
  route to this hub. Instructions are a persistent menu item because setup help
  is a primary customer task. Device choice buttons should use plain labels like
  `iPhone`, `Android`, and `Windows/macOS`; do not add decorative icons there.

## Screen Copy

Each bot screen should answer one question clearly:

- where the user is
- what the current account or subscription state is
- which button to press next

Keep copy short. Prefer two payment lines, for example "Картой: ... в кабинете"
and "Stars: внутри Telegram", instead of long payment explanations. Avoid
repeating the full product structure on every screen.

Do not expose implementation details in customer alerts. If XUI, DNS, or
Cloudflare cleanup fails, tell the user what they can do next and log the
internal reason for operators.

## Mini App Buttons

Use Telegram `web_app=WebAppInfo(url=...)` buttons for cabinet entrypoints.
The bot URL builder maps account routes into `/account-app/` and adds
`embed=1`.

Examples:

- `/account/` -> `/account-app/?embed=1`
- `/account/buy/` -> `/account-app/buy/?embed=1`
- `/account/renew/?subscription_id=42` -> `/account-app/renew/?subscription_id=42&embed=1`
- `/account/config/42/` -> `/account-app/config/42/?embed=1`

Backend Mini App identity must be validated with Telegram initData before
trusting user identity. Magic links are browser fallback only.

## Ops Labels

The `/ops/` bot settings page should expose only current runtime keys. Stale
menu keys such as `menu_site`, `menu_mysub`, `menu_buy`, `menu_renew`, and
`back_button` should not be editable as active customer menu labels.

If old DB overrides still exist, runtime fallback should prevent stale English,
mojibake, or old plain menu labels from replacing the canonical Russian menu.
The editor defaults should match the current bot copy: short Mini App-first
instructions, compact Stars buy/renew text, and support confirmations with a
ticket number plus `📱 Кабинет` history pointer. Obsolete site/about and old
instruction button override keys should be cleared when the editor is saved.

The `/ops/` editor UI itself should use Russian operator labels for the active
bot concepts: settings title, editable-key status, JSON override fields, Stars
invoice fields, support ticket subjects, and reminder labels. Avoid mixed
labels such as "Advanced JSON", "Stars invoice", "Subject", or "Reminder" in
the visible admin page unless they are part of a product name.

## Next Safe Steps

Do not split `src/bot.py` until UX is stable. The next useful slices are:

- move long instructions fully into the Mini App
- keep reducing taps in My VPN and Renew without adding global Back buttons
- split one stable flow at a time into `src/bot/flows/`
- keep regression tests around menu restore behavior and Mini App button markup
