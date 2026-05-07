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
        self.assertIn(".vx-account-bot .vx-bot-utility .vx-bot-line", self.css)
        self.assertIn(".vx-account-bot .vx-bot-utility .vx-bot-actions-utility", self.css)
        access_meta_rule = self.css[self.css.index(".vx-account-bot .vx-bot-access-meta {") :]
        access_meta_rule = access_meta_rule[: access_meta_rule.index("}")]
        self.assertIn("padding: 9px 10px;", access_meta_rule)
        self.assertIn("background: #f7f8fa;", access_meta_rule)

    def test_embed_dashboard_is_connect_first(self):
        self.assertIn(".vx-account-bot .vx-bot-button-primary", self.css)
        self.assertIn("background: var(--vx-bot-blue);", self.css)
        self.assertIn("grid-column: 1 / -1;", self.css)

    def test_embed_empty_dashboard_state_is_polished(self):
        self.assertIn(".vx-account-bot .account-mini-empty", self.css)
        self.assertIn(".vx-account-bot .account-mini-empty-mark", self.css)
        self.assertIn(".vx-account-bot .account-mini-empty > strong", self.css)
        self.assertIn(".vx-account-bot .account-mini-empty > span:not(.account-mini-empty-mark)", self.css)
        self.assertIn("box-shadow: inset 0 0 0 1px rgba(32, 33, 36, 0.02);", self.css)

    def test_embed_bot_buttons_wrap_cleanly(self):
        button_rule = self.css[self.css.index(".vx-account-bot .vx-bot-button,\n.vx-account-bot .vx-bot-tab {") :]
        button_rule = button_rule[: button_rule.index("}")]

        self.assertIn("gap: 7px;", self.css)
        self.assertIn("text-wrap: balance;", self.css)
        self.assertIn("word-break: normal;", self.css)
        self.assertIn("overflow-wrap: break-word;", self.css)
        self.assertIn(".vx-account-bot .vx-bot-button > span:not(.vx-bot-button-icon)", self.css)
        self.assertIn(".vx-account-bot .vx-bot-button:focus-visible", self.css)
        self.assertIn("-webkit-tap-highlight-color: transparent;", button_rule)
        self.assertIn("transition: background-color 0.15s ease, color 0.15s ease, transform 0.15s ease", button_rule)
        self.assertIn(".vx-account-bot .vx-bot-button:active", self.css)
        self.assertIn("transform: translateY(1px);", self.css)

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
        self.assertIn(".vx-account-bot .vx-bot-actions-secondary", self.css)
        self.assertIn(".vx-account-bot .vx-bot-actions-utility", self.css)
        self.assertIn(".vx-account-bot .vx-bot-button-icon", self.css)
        self.assertIn(".vx-account-bot .vx-bot-actions-utility .vx-bot-button", self.css)
        self.assertIn(".vx-account-bot .vx-bot-actions > .vx-bot-button:only-child", self.css)
        self.assertIn(".vx-account-bot .vx-bot-actions:not(:has(> .vx-bot-button-primary:first-child))", self.css)
        self.assertIn(".vx-account-bot .vx-bot-actions > .vx-bot-button-primary:first-child + .vx-bot-button:last-child", self.css)

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
        self.assertIn(".vx-account-bot .account-step-list", self.css)
        self.assertIn("display: grid;", self.css)
        self.assertIn(".vx-account-bot .account-instructions-device-actions .vx-bot-tab:hover", self.css)
        self.assertIn(
            ".vx-account-bot .account-instructions-device-actions .vx-bot-tab.account-secondary-button-current",
            self.css,
        )
        self.assertIn(".vx-account-bot .account-step-list li::marker", self.css)
        self.assertIn(".vx-account-bot .account-support-hint", self.css)
        self.assertIn(".vx-account-bot .account-support-id-row", self.css)
        self.assertIn(".vx-account-bot .account-support-id .vx-bot-line", self.css)
        self.assertIn(".vx-account-bot .account-instructions-access .vx-bot-line", self.css)
        self.assertIn(".vx-account-bot .account-device-headline", self.css)
        self.assertIn(".vx-account-bot .account-instructions-access .vx-bot-button", self.css)

    def test_embed_install_selector_and_app_cards_are_polished(self):
        self.assertIn(".vx-account-bot .vx-install-tabs", self.css)
        self.assertIn("padding: 3px;", self.css)
        self.assertIn(".vx-account-bot .vx-install-tabs .vx-bot-tab.account-secondary-button-current", self.css)
        self.assertIn(
            ".vx-account-bot .account-install-apps:not(.account-install-apps-flat) .account-install-app-card",
            self.css,
        )
        self.assertIn(".vx-account-bot .account-install-app-mark", self.css)
        self.assertIn(".vx-account-bot .account-install-app-text", self.css)
        self.assertIn(".vx-account-bot .account-install-app-badges", self.css)
        self.assertIn(".vx-account-bot .account-install-app-badge-primary", self.css)
        self.assertIn(".vx-account-bot .account-install-app-badge-paid", self.css)
        self.assertIn(".vx-account-bot .account-install-app-card-flat .account-install-app-mark", self.css)
        self.assertIn("border: 1px solid var(--vx-bot-line);", self.css)
        self.assertIn(".vx-account-bot .account-install-note-inline strong", self.css)
        self.assertIn(".vx-account-bot .account-install-note-inline a", self.css)
        self.assertIn("Инструкция VXcloud", (REPO_ROOT / "web" / "templates" / "cabinet" / "install.html").read_text(encoding="utf-8"))

    def test_embed_config_page_is_qr_and_link_first(self):
        self.assertIn("body.vx-account-embed .account-page-shell-config", self.css)
        self.assertIn(".vx-account-bot .vx-bot-status-strip", self.css)
        self.assertIn(".vx-account-bot .vx-bot-url-row", self.css)
        self.assertIn(".vx-account-bot .vx-bot-qr-frame", self.css)
        self.assertIn(".vx-account-bot .account-config-link-section", self.css)
        self.assertIn(".vx-account-bot .account-config-data-actions", self.css)
        self.assertIn(".vx-account-bot .vx-bot-rename-form", self.css)
        self.assertIn(".vx-account-bot .vx-bot-key-row span", self.css)
        self.assertIn("align-items: center;", self.css)

    def test_embed_config_access_list_uses_bot_rows(self):
        self.assertIn(".vx-account-bot .account-config-item", self.css)
        self.assertIn('grid-template-areas:', self.css)
        self.assertIn('"id name"', self.css)
        self.assertIn(".vx-account-bot .account-config-item-id", self.css)
        self.assertIn("border-radius: 999px;", self.css)
        self.assertIn(".vx-account-bot .account-config-item-current .account-config-item-meta", self.css)
        self.assertIn("color: rgba(255, 255, 255, 0.72);", self.css)

    def test_embed_url_rows_are_polished_copy_controls(self):
        self.assertIn(".vx-account-bot .vx-bot-url-row .account-link-input", self.css)
        self.assertIn(
            "font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;",
            self.css,
        )
        self.assertIn(".vx-account-bot .vx-bot-url-row .account-icon-button:focus-visible", self.css)
        self.assertIn(".vx-account-bot .vx-bot-url-row .account-icon-button:active", self.css)
        self.assertIn(".vx-account-bot .vx-bot-url-row .account-icon-glyph", self.css)
        self.assertIn("font-weight: 800;", self.css)
        self.assertIn("background: #fbfbfc;", self.css)
        self.assertIn(".vx-account-bot .vx-bot-qr-frame .account-qr-image", self.css)
        self.assertIn("box-shadow: inset 0 0 0 1px rgba(32, 33, 36, 0.02);", self.css)
        self.assertIn("padding: 6px;", self.css)

    def test_embed_open_app_progress_is_visible(self):
        progress_rule = self.css[self.css.index(".vx-account-bot .vx-open-progress {") :]
        progress_rule = progress_rule[: progress_rule.index("}")]

        self.assertIn("height: 6px;", progress_rule)
        self.assertIn("box-shadow: inset 0 0 0 1px rgba(32, 33, 36, 0.04);", progress_rule)
        self.assertIn(".vx-account-bot .vx-open-app-note", self.css)
        self.assertIn(".vx-account-bot .vx-open-app-manual", self.css)
        self.assertIn(".vx-account-bot .vx-open-app-rescue .vx-bot-actions", self.css)
        self.assertIn(".vx-account-bot .vx-open-app-rescue .vx-bot-line", self.css)
        self.assertIn("box-shadow: inset 0 0 0 1px rgba(32, 33, 36, 0.02);", self.css)

    def test_auth_edges_use_polished_bot_controls(self):
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-widget-shell", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-widget-copy", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-widget-mark", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-email-panel", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-form p", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .account-message-error", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-code-value", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-divider", self.css)
        self.assertIn("text-transform: uppercase;", self.css)


if __name__ == "__main__":
    unittest.main()
