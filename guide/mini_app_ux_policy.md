# VXcloud Mini App UX Policy

Last updated: 2026-05-06

## Role

The Telegram Mini App is the primary customer account surface for:

- account status;
- active and inactive VPN accesses;
- QR and subscription config details;
- renewal and purchase entry points;
- short support and instruction entry points.

The Telegram bot stays a command layer. The public browser account pages stay a
fallback and can use a wider layout.

## Dashboard Rules

- The Mini App dashboard must be compact and mobile-first.
- Do not reuse the full desktop account layout without embed-specific styling.
- The first viewport should show the account title, primary actions, and useful
  status without large empty vertical gaps.
- Summary stats should fit in a tight mobile grid.
- Subscription cards on the dashboard should show only:
  - access name;
  - active/inactive status;
  - expiration label;
  - primary actions such as renew, QR, and open details.
- Rename fields, raw subscription links, local IDs, and delete controls belong
  on deeper detail screens, not expanded by default in the dashboard.

## Instruction Rules

- Bot and Mini App instruction links should open `/account-app/?view=instructions`
  or a device variant such as `device=iphone`, not the generic public blog index.
- The Mini App instruction view should not show the public WordPress header,
  blog article chrome, or the normal account dashboard below the guide.
- Device choices should look like compact tabs/buttons and keep the selected
  device obvious.
- Long editorial guide posts can remain public browser content, but Telegram
  users should first get the compact cabinet guide with direct access to My VPN,
  QR, and support.

## Visual Rules

- Russian is the default UI language for customer-facing text.
- Keep the Mini App close to the VXcloud public style: white background, black
  text, restrained borders, and minimal red links.
- Use radius only where it helps Telegram mobile usability; keep it at 8px or
  less.
- Avoid oversized hero typography inside Telegram.
- Avoid viewport-scaled type for compact app surfaces.
- Do not hide QR/config access; move details behind explicit actions instead.

## Implementation Notes

- Embed-specific styles are scoped under `body.vx-account-embed`.
- Browser fallback pages under `/account/` should not be broken by Mini App CSS.
- `/account-app/` and `?embed=1` must remain scrollable in Telegram webviews.
- Add regression tests when changing dashboard density, subscription card
  contents, or embed-only layout behavior.
