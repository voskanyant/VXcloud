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
        self.assertIn("body.vx-account-embed .account-page-shell", self.css)
        self.assertIn("body.vx-account-embed .account-title", self.css)
        self.assertIn("body.vx-account-embed .account-summary", self.css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", self.css)

    def test_embed_dashboard_puts_vpn_devices_before_account_metadata(self):
        self.assertIn("body.vx-account-embed .account-hero", self.css)
        self.assertIn("body.vx-account-embed #account-subscriptions", self.css)
        self.assertIn("body.vx-account-embed .account-summary", self.css)
        self.assertIn("order: 1;", self.css)
        self.assertIn("order: 2;", self.css)
        self.assertIn("order: 3;", self.css)

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
        self.assertIn(
            "body.vx-account-embed #account-subscriptions .account-device-actions",
            self.css,
        )
        self.assertIn(
            "body.vx-account-embed #account-subscriptions .account-device-actions .account-primary-button",
            self.css,
        )

    def test_embed_instructions_use_compact_device_tabs(self):
        self.assertIn("body.vx-account-embed .account-page-shell-instructions", self.css)
        self.assertIn("body.vx-account-embed #account-instructions", self.css)
        self.assertIn("body.vx-account-embed .account-instructions-device-actions", self.css)
        self.assertIn("body.vx-account-embed .account-secondary-button-current", self.css)
        self.assertIn(".account-step-list", self.css)
        self.assertIn("body.vx-account-embed #account-instructions .account-step-list", self.css)

    def test_embed_config_page_is_qr_and_link_first(self):
        self.assertIn("body.vx-account-embed .account-page-shell-config", self.css)
        self.assertIn("body.vx-account-embed .account-page-shell-config .account-section-qr", self.css)
        self.assertIn("body.vx-account-embed .account-page-shell-config .account-config-link-section", self.css)
        self.assertIn("body.vx-account-embed .account-page-shell-config .account-config-status-section", self.css)
        self.assertIn("body.vx-account-embed .account-page-shell-config .account-config-list-section", self.css)
        self.assertIn("body.vx-account-embed .account-page-shell-config .account-config-rename-section", self.css)


if __name__ == "__main__":
    unittest.main()
