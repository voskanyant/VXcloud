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
- cleaned remaining English fallback labels in input cancellation, delete alerts,
  and raw connection-link messages

It also added a 3x-ui client update fallback for panels that reject wrapped
`updateClient` payloads with `empty client ID`.

## Next Safe Steps

Do not split `src/bot.py` until UX is stable. The next useful slices are:

- finish Russian cleanup for older CMS/default text that still contains mojibake
- move long instructions fully into the Mini App
- split one stable flow at a time into `src/bot/flows/`
- keep regression tests around menu restore behavior and Mini App button markup
