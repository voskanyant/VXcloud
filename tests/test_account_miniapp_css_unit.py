from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_CSS = REPO_ROOT / "web" / "static" / "css" / "site.css"


class AccountMiniAppCssTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = SITE_CSS.read_text(encoding="utf-8")

    def test_embed_shell_can_scroll(self):
        body_rule = self.css[self.css.index("body.vx-account-embed {") :]
        body_rule = body_rule[: body_rule.index("}")]

        self.assertIn("overflow-y: auto;", body_rule)

    def test_embed_dashboard_uses_compact_mobile_layout(self):
        self.assertIn("body.vx-account-embed .account-page-shell-mini", self.css)
        self.assertIn(".vx-account-bot .vx-bot-card", self.css)
        self.assertIn(".vx-account-bot .vx-bot-summary-row", self.css)
        self.assertIn(".vx-account-bot .vx-bot-access-meta", self.css)
        self.assertIn(".vx-account-bot .vx-bot-title", self.css)
        self.assertIn(".vx-account-bot .vx-bot-actions", self.css)

    def test_embed_dashboard_is_connect_first(self):
        self.assertIn(".vx-account-bot .vx-bot-button-primary", self.css)
        self.assertIn("background: var(--vx-bot-blue);", self.css)
        self.assertIn("grid-column: 1 / -1;", self.css)

    def test_embed_bot_buttons_wrap_cleanly(self):
        self.assertIn("text-wrap: balance;", self.css)
        self.assertIn("word-break: normal;", self.css)
        self.assertIn("overflow-wrap: break-word;", self.css)

    def test_embed_more_controls_are_polished_tap_targets(self):
        more_rule = self.css[self.css.index(".vx-account-bot .vx-bot-more summary {") :]
        more_rule = more_rule[: more_rule.index("}")]

        self.assertIn("min-height: 44px;", more_rule)
        self.assertIn("text-wrap: balance;", more_rule)
        self.assertIn("-webkit-tap-highlight-color: transparent;", more_rule)
        self.assertIn("transition: background-color 0.15s ease", more_rule)

    def test_embed_subscription_list_hides_expanded_details(self):
        self.assertIn(
            "body.vx-account-embed #account-subscriptions .account-inline-form",
            self.css,
        )
        self.assertIn(
            "body.vx-account-embed #account-subscriptions .account-device-meta",
            self.css,
        )
        self.assertIn(
            "body.vx-account-embed #account-subscriptions .account-link-block",
            self.css,
        )
        self.assertIn("display: none;", self.css)

    def test_embed_subscription_actions_remain_available(self):
        self.assertIn(".vx-account-bot .vx-bot-actions", self.css)
        self.assertIn(".vx-account-bot .vx-bot-actions-utility", self.css)
        self.assertIn(".vx-account-bot .vx-bot-more summary", self.css)

    def test_embed_instructions_use_compact_device_tabs(self):
        self.assertIn("body.vx-account-embed .account-page-shell-instructions", self.css)
        self.assertIn("body.vx-account-embed #account-instructions", self.css)
        self.assertIn("body.vx-account-embed .account-instructions-device-actions", self.css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", self.css)
        self.assertIn(
            "body.vx-account-embed .account-instructions-device-actions .account-secondary-button:nth-child(3)",
            self.css,
        )
        self.assertIn("grid-column: 1 / -1;", self.css)
        self.assertIn("body.vx-account-embed .account-secondary-button-current", self.css)
        self.assertIn(".account-step-list", self.css)
        self.assertIn("body.vx-account-embed #account-instructions .account-step-list", self.css)

    def test_embed_install_selector_and_app_cards_are_polished(self):
        self.assertIn(".vx-account-bot .vx-install-tabs", self.css)
        self.assertIn("padding: 3px;", self.css)
        self.assertIn(".vx-account-bot .vx-install-tabs .vx-bot-tab.account-secondary-button-current", self.css)
        self.assertIn(
            ".vx-account-bot .account-install-apps:not(.account-install-apps-flat) .account-install-app-card",
            self.css,
        )
        self.assertIn("border: 1px solid var(--vx-bot-line);", self.css)

    def test_embed_config_page_is_qr_and_link_first(self):
        self.assertIn("body.vx-account-embed .account-page-shell-config", self.css)
        self.assertIn(".vx-account-bot .vx-bot-status-strip", self.css)
        self.assertIn(".vx-account-bot .vx-bot-url-row", self.css)
        self.assertIn(".vx-account-bot .vx-bot-qr-frame", self.css)
        self.assertIn(".vx-account-bot .vx-bot-rename-form", self.css)

    def test_embed_url_rows_are_polished_copy_controls(self):
        self.assertIn(".vx-account-bot .vx-bot-url-row .account-link-input", self.css)
        self.assertIn(
            "font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;",
            self.css,
        )
        self.assertIn(".vx-account-bot .vx-bot-url-row .account-icon-button:focus-visible", self.css)
        self.assertIn(".vx-account-bot .vx-bot-url-row .account-icon-button:active", self.css)

    def test_embed_open_app_progress_is_visible(self):
        progress_rule = self.css[self.css.index(".vx-account-bot .vx-open-progress {") :]
        progress_rule = progress_rule[: progress_rule.index("}")]

        self.assertIn("height: 6px;", progress_rule)
        self.assertIn("box-shadow: inset 0 0 0 1px rgba(32, 33, 36, 0.04);", progress_rule)

    def test_auth_edges_use_polished_bot_controls(self):
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-widget-shell", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-form p", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .account-message-error", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-code-value", self.css)


if __name__ == "__main__":
    unittest.main()
