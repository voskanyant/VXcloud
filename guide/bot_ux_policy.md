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
payments, subscriptions, and ops. 3x-ui/Xray/Cloudflare are execution layers.

## Language

Customer-facing bot defaults are Russian. English should only remain for product
or platform names where users expect them, for example VXcloud, VPN, Telegram,
Mini App, Stars, iPhone, Android, Windows, and macOS.

If CMS overrides exist, they can still replace defaults. New default labels and
fallback text should be Russian.

## Persistent Menu

Default persistent menu:

- Мой VPN
- Купить
- Продлить
- Поддержка
- Кабинет

The menu should be visible after normal bot flows. Hide it only while waiting
for free text input, currently:

- support message
- subscription rename
- future promo code or similar input states

When input completes, is empty, or is cancelled by a menu button, restore the
persistent menu.

## Inline Buttons

Use inline buttons only inside contextual messages. Avoid duplicating the full
main menu inside inline keyboards.

Good contextual examples:

- Открыть кабинет
- QR
- Продлить
- Скопировать ссылку
- Переименовать
- Удалить
- Назад

Avoid adding browser fallback buttons to every card. Keep browser fallback where
it is genuinely useful, such as the top-level cabinet entry or card checkout
entrypoints for older Telegram clients.

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
trusting user identity. Magic links are only browser fallback.

## Current Cleanup

The 2026-05-06 cleanup did three things:

- changed bot default labels from English to Russian
- reduced noisy duplicate inline rows on config and payment success cards
- kept Mini App as the primary account surface, with limited browser fallback
- reduced buy, renew, and trial contextual keyboards to primary action, Stars
  where applicable, and Back; browser fallback stays on top-level cabinet and
  post-payment entrypoints instead of every payment choice
- localized the Mini App support view opened from the bot, so support copy and
  actions stay Russian
- moved bot instruction choices to Mini App instruction views instead of
  opening public `/instructions/` directly from Telegram
- localized account dashboard/config labels that Telegram users see after
  opening Mini App from the bot
- made bot CMS fallback reject stale English customer-facing overrides, so old
  `/ops/` labels such as `Buy access` or `Open app` do not replace Russian
  defaults
- fixed Mini App Telegram auth handoff to load Telegram WebApp JS, post
  `initData` with the current `/account-app/` return path, and redirect back
  into the embedded account UI after Django creates the session
- kept the 7-day trial as a Russian persistent-menu entry while removing
  inline `Back` navigation rows from bot screens; users should use the
  persistent menu for navigation, while inline buttons stay reserved for
  immediate contextual actions
- cleaned remaining English fallback labels in input cancellation, delete alerts,
  and raw connection-link messages
- made bot CMS fallback reject mojibake overrides, so broken stored labels do
  not replace clean Russian defaults

It also added a 3x-ui client update fallback for panels that reject wrapped
`updateClient` payloads with `empty client ID`.

## Next Safe Steps

Do not split `src/bot.py` until UX is stable. The next useful slices are:

- finish Russian cleanup for older CMS/default text that still contains mojibake
- move long instructions fully into the Mini App
- split one stable flow at a time into `src/bot/flows/`
- keep regression tests around menu restore behavior and Mini App button markup
