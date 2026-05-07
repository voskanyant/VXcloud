from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_CSS = REPO_ROOT / "web" / "static" / "css" / "site.css"
DASHBOARD_TEMPLATE = REPO_ROOT / "web" / "templates" / "cabinet" / "dashboard.html"
CONFIG_TEMPLATE = REPO_ROOT / "web" / "templates" / "cabinet" / "config.html"
INSTALL_TEMPLATE = REPO_ROOT / "web" / "templates" / "cabinet" / "install.html"
OPEN_APP_TEMPLATE = REPO_ROOT / "web" / "templates" / "cabinet" / "open_app.html"
ACCOUNT_PREVIEW = REPO_ROOT / "account_ui_preview.html"
LINK_TELEGRAM_TEMPLATE = REPO_ROOT / "web" / "templates" / "cabinet" / "link_telegram.html"


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
        self.assertIn(".vx-account-bot .vx-bot-topbar", self.css)
        self.assertIn(".vx-account-bot .vx-bot-topbar-title", self.css)
        self.assertIn(".vx-account-bot .vx-bot-card", self.css)
        self.assertIn(".vx-account-bot .vx-bot-summary-row", self.css)
        self.assertIn(".vx-account-bot .vx-bot-access-meta", self.css)
        self.assertIn(".vx-account-bot .vx-bot-title", self.css)
        self.assertIn(".vx-account-bot .vx-bot-pill-active::before", self.css)
        self.assertIn(".vx-account-bot .vx-bot-actions", self.css)
        self.assertIn(".vx-account-bot .vx-bot-utility .vx-bot-line", self.css)
        self.assertIn(".vx-account-bot .vx-bot-utility .vx-bot-actions-utility", self.css)
        topbar_rule = self.css[self.css.index(".vx-account-bot .vx-bot-topbar {") :]
        topbar_rule = topbar_rule[: topbar_rule.index("}")]
        self.assertIn("grid-template-columns: 28px minmax(0, 1fr) 28px;", topbar_rule)
        self.assertIn("min-height: 44px;", topbar_rule)
        topbar_action_rule = self.css[self.css.index(".vx-account-bot .vx-bot-topbar-back,\n.vx-account-bot .vx-bot-topbar-action {") :]
        topbar_action_rule = topbar_action_rule[: topbar_action_rule.index("}")]
        self.assertIn("-webkit-tap-highlight-color: transparent;", topbar_action_rule)
        self.assertIn("transition: background-color 0.15s ease, color 0.15s ease, transform 0.15s ease;", topbar_action_rule)
        self.assertIn(".vx-account-bot .vx-bot-topbar-back:hover", self.css)
        self.assertIn(".vx-account-bot .vx-bot-topbar-action:active", self.css)
        title_rule = self.css[self.css.index(".vx-account-bot .vx-bot-title {") :]
        title_rule = title_rule[: title_rule.index("}")]
        self.assertIn("font-size: 17px;", title_rule)
        self.assertIn("font-weight: 700;", title_rule)
        access_card_rule = self.css[self.css.index(".vx-account-bot .vx-bot-access-card {") :]
        access_card_rule = access_card_rule[: access_card_rule.index("}")]
        self.assertIn("gap: 8px;", access_card_rule)
        secondary_actions_rule = self.css[self.css.index(".vx-account-bot .vx-bot-actions-secondary {") :]
        secondary_actions_rule = secondary_actions_rule[: secondary_actions_rule.index("}")]
        self.assertIn("margin-top: 0;", secondary_actions_rule)
        bot_card_rule = self.css[self.css.index(".vx-account-bot .vx-bot-card {") :]
        bot_card_rule = bot_card_rule[: bot_card_rule.index("}")]
        self.assertIn("box-shadow: inset 0 0 0 1px rgba(32, 33, 36, 0.03)", bot_card_rule)
        access_meta_rule = self.css[self.css.index(".vx-account-bot .vx-bot-access-meta {") :]
        access_meta_rule = access_meta_rule[: access_meta_rule.index("}")]
        self.assertIn("padding: 9px 10px;", access_meta_rule)
        self.assertIn("background: #f7f8fa;", access_meta_rule)
        self.assertIn("font-variant-numeric: tabular-nums;", access_meta_rule)
        summary_value_rule = self.css[self.css.index(".vx-account-bot .vx-bot-summary-row strong {") :]
        summary_value_rule = summary_value_rule[: summary_value_rule.index("}")]
        self.assertIn("font-variant-numeric: tabular-nums;", summary_value_rule)
        pill_rule = self.css[self.css.index(".vx-account-bot .vx-bot-pill {") :]
        pill_rule = pill_rule[: pill_rule.index("}")]
        self.assertIn("gap: 5px;", pill_rule)
        self.assertIn("width: 6px;", self.css)
        self.assertIn("background: currentColor;", self.css)

    def test_embed_dashboard_is_connect_first(self):
        self.assertIn(".vx-account-bot .vx-bot-button-primary", self.css)
        self.assertIn("background: var(--vx-bot-blue);", self.css)
        self.assertIn("grid-column: 1 / -1;", self.css)
        primary_rule = self.css[self.css.index(".vx-account-bot .vx-bot-button-primary,\n.vx-account-bot .vx-bot-actions > .vx-bot-button-primary:first-child {") :]
        primary_rule = primary_rule[: primary_rule.index("}")]
        self.assertIn("box-shadow: inset 0 -1px 0 rgba(0, 0, 0, 0.12), 0 8px 16px rgba(36, 129, 204, 0.16);", primary_rule)

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
        self.assertIn("box-shadow: inset 0 0 0 1px rgba(32, 33, 36, 0.03);", button_rule)
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
        self.assertIn(".vx-account-bot .vx-bot-button:not(.vx-bot-button-primary) .vx-bot-button-icon", self.css)
        icon_rule = self.css[self.css.index(".vx-account-bot .vx-bot-button-icon {") :]
        icon_rule = icon_rule[: icon_rule.index("}")]
        self.assertIn("font-weight: 800;", icon_rule)
        secondary_icon_rule = self.css[self.css.index(".vx-account-bot .vx-bot-button:not(.vx-bot-button-primary) .vx-bot-button-icon {") :]
        secondary_icon_rule = secondary_icon_rule[: secondary_icon_rule.index("}")]
        self.assertIn("font-size: 14px;", secondary_icon_rule)

    def test_dashboard_action_icons_are_visually_consistent(self):
        template = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('aria-hidden="true">⧉</span><span>Скопировать ссылку', template)
        self.assertIn('aria-hidden="true">▦</span><span>QR и доступ', template)
        self.assertIn('aria-hidden="true">↻</span><span>Продлить', template)
        self.assertIn('aria-hidden="true">₽</span><span>Купить', template)

    def test_connected_account_pages_share_action_glyphs(self):
        config = CONFIG_TEMPLATE.read_text(encoding="utf-8")
        install = INSTALL_TEMPLATE.read_text(encoding="utf-8")
        open_app = OPEN_APP_TEMPLATE.read_text(encoding="utf-8")
        link_telegram = LINK_TELEGRAM_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('aria-hidden="true">⧉</span><span>Скопировать ссылку', config)
        self.assertIn('aria-hidden="true">↻</span><span>Продлить', config)
        self.assertIn('aria-hidden="true">✓</span><span>Сохранить', config)
        self.assertIn('aria-hidden="true">⧉</span><span>Скопировать ссылку', install)
        self.assertIn('aria-hidden="true">i</span><span>Подробная инструкция', install)
        self.assertIn('aria-hidden="true">i</span><span>Открыть инструкцию', open_app)
        self.assertIn('aria-hidden="true">?</span><span>Поддержка', open_app)
        self.assertIn('aria-hidden="true">›</span><span>{{ cabinet_link_open_bot_action }}', link_telegram)
        self.assertIn('aria-hidden="true">↻</span><span>{{ cabinet_link_regen_action }}', link_telegram)

    def test_bot_style_pages_have_compact_topbars(self):
        dashboard = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
        config = CONFIG_TEMPLATE.read_text(encoding="utf-8")
        install = INSTALL_TEMPLATE.read_text(encoding="utf-8")
        open_app = OPEN_APP_TEMPLATE.read_text(encoding="utf-8")
        preview = ACCOUNT_PREVIEW.read_text(encoding="utf-8")

        self.assertIn('aria-label="Поддержка"', dashboard)
        self.assertIn('aria-label="Инструкция"', dashboard)
        self.assertIn('<h1 class="vx-bot-topbar-title">Доступ</h1>', config)
        self.assertIn('<h1 class="vx-bot-topbar-title">Подключить</h1>', install)
        self.assertIn('<h1 class="vx-bot-topbar-title">Открытие приложения</h1>', open_app)
        self.assertNotIn("‹ Мой VPN", preview)
        self.assertIn("width: 24px;", self.css)
        self.assertIn("box-shadow: inset 0 0 0 1px rgba(32, 33, 36, 0.04);", self.css)
        self.assertIn(".vx-account-bot .vx-bot-actions-utility .vx-bot-button", self.css)
        self.assertIn(".vx-account-bot .vx-bot-actions > .vx-bot-button:only-child", self.css)
        self.assertIn(".vx-account-bot .vx-bot-actions:not(:has(> .vx-bot-button-primary:first-child))", self.css)
        self.assertIn(".vx-account-bot .vx-bot-actions > .vx-bot-button-primary:first-child + .vx-bot-button:last-child", self.css)

    def test_dashboard_template_drops_legacy_browser_dashboard_branch(self):
        dashboard = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")

        self.assertNotIn("account-dashboard-shell", dashboard)
        self.assertNotIn("account-hero-redesigned", dashboard)
        self.assertNotIn("account-access-card", dashboard)
        self.assertNotIn("account-dashboard-side", dashboard)

    def test_embed_instructions_use_compact_device_tabs(self):
        dashboard = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")

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
        self.assertIn('.vx-account-bot .account-instructions-device-actions .vx-bot-tab[aria-current="page"]', self.css)
        self.assertIn(".vx-account-bot .account-step-list li::marker", self.css)
        self.assertIn(".vx-account-bot .account-support-hint", self.css)
        self.assertIn(".vx-account-bot .account-support-actions", self.css)
        self.assertIn(".vx-account-bot .account-support-id,\n.vx-account-bot .account-support-hint", self.css)
        self.assertIn(".vx-account-bot .account-support-id-row", self.css)
        self.assertIn(".vx-account-bot .account-support-id .vx-bot-line", self.css)
        self.assertIn(".vx-account-bot .account-instructions-access .vx-bot-line", self.css)
        self.assertIn(".vx-account-bot .account-device-headline", self.css)
        self.assertIn(".vx-account-bot .account-instructions-access-actions", self.css)
        self.assertIn("QR и доступ", dashboard)
        self.assertLess(
            dashboard.index("account-instructions-access-actions"),
            dashboard.index("account-guide-card"),
        )
        self.assertLess(
            dashboard.index("account-support-actions"),
            dashboard.index("account-support-hint"),
        )
        self.assertIn('aria-current="page"', dashboard)

    def test_embed_install_selector_and_app_cards_are_polished(self):
        install = (REPO_ROOT / "web" / "templates" / "cabinet" / "install.html").read_text(encoding="utf-8")

        self.assertIn(".vx-account-bot .vx-install-tabs", self.css)
        self.assertIn("padding: 3px;", self.css)
        self.assertIn(".vx-account-bot .vx-install-tabs .vx-bot-tab.account-secondary-button-current", self.css)
        self.assertIn('.vx-account-bot .vx-install-tabs .vx-bot-tab[aria-pressed="true"]', self.css)
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
        recommended_app_rule = self.css[
            self.css.index(".vx-account-bot .account-install-apps:not(.account-install-apps-flat) .account-install-app-card {") :
        ]
        recommended_app_rule = recommended_app_rule[: recommended_app_rule.index("}")]
        self.assertIn("background: #f7f8fa;", recommended_app_rule)
        self.assertIn("box-shadow: inset 0 0 0 1px rgba(32, 33, 36, 0.02);", recommended_app_rule)
        self.assertIn(".vx-account-bot .account-install-note-inline strong", self.css)
        self.assertIn(".vx-account-bot .account-install-note-inline a", self.css)
        self.assertIn(".vx-account-bot .vx-install-manual-card", self.css)
        self.assertIn(".vx-account-bot .vx-install-manual-card .vx-bot-line", self.css)
        self.assertIn("Инструкция VXcloud", install)
        self.assertIn('class="vx-bot-card vx-install-manual-card" id="install-manual"', install)
        self.assertIn("<h2 class=\"vx-bot-title\">Настроить вручную</h2>", install)
        self.assertNotIn('<details class="vx-bot-more" id="install-manual">', install)
        self.assertIn('id="install-show-apps"><span class="vx-bot-button-icon" aria-hidden="true">▦</span><span>У меня другое приложение', install)
        self.assertIn("function setButtonContent", install)
        self.assertIn("setButtonContent(\n          showAppsButton,", install)
        self.assertIn("appsRoot.hidden ? '▦' : '×'", install)
        self.assertIn('data-platform-choice="ios" aria-pressed="false"', install)
        self.assertIn("button.setAttribute('aria-pressed', isCurrent ? 'true' : 'false')", install)

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
        current_item_rule = self.css[self.css.index(".vx-account-bot .account-config-item-current {") :]
        current_item_rule = current_item_rule[: current_item_rule.index("}")]
        self.assertIn("background: #ffffff;", current_item_rule)
        self.assertIn("color: var(--vx-bot-text);", current_item_rule)
        current_id_rule = self.css[self.css.index(".vx-account-bot .account-config-item-current .account-config-item-id {") :]
        current_id_rule = current_id_rule[: current_id_rule.index("}")]
        self.assertIn("background: #202124;", current_id_rule)
        current_meta_rule = self.css[self.css.index(".vx-account-bot .account-config-item-current .account-config-item-meta {") :]
        current_meta_rule = current_meta_rule[: current_meta_rule.index("}")]
        self.assertIn("color: var(--vx-bot-muted);", current_meta_rule)

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
        qr_frame_rule = self.css[self.css.index(".vx-account-bot .vx-bot-qr-frame {") :]
        qr_frame_rule = qr_frame_rule[: qr_frame_rule.index("}")]
        self.assertIn("display: flex;", qr_frame_rule)
        self.assertIn("align-items: center;", qr_frame_rule)
        self.assertIn("justify-content: center;", qr_frame_rule)
        self.assertIn("height: 188px;", qr_frame_rule)
        self.assertIn(".vx-account-bot .vx-bot-qr-frame .account-qr-image", self.css)
        self.assertIn("box-shadow: inset 0 0 0 1px rgba(32, 33, 36, 0.02);", self.css)
        self.assertIn("padding: 6px;", self.css)
        self.assertIn("0 8px 16px rgba(32, 33, 36, 0.04);", self.css)

    def test_embed_open_app_progress_is_visible(self):
        open_app = OPEN_APP_TEMPLATE.read_text(encoding="utf-8")
        progress_rule = self.css[self.css.index(".vx-account-bot .vx-open-progress {") :]
        progress_rule = progress_rule[: progress_rule.index("}")]

        self.assertIn("height: 6px;", progress_rule)
        self.assertIn("box-shadow: inset 0 0 0 1px rgba(32, 33, 36, 0.04);", progress_rule)
        self.assertIn(".vx-account-bot .vx-open-app-note", self.css)
        self.assertIn(".vx-account-bot .vx-open-app-manual", self.css)
        self.assertIn(".vx-account-bot .vx-open-app-rescue .vx-bot-actions", self.css)
        self.assertIn(".vx-account-bot .vx-open-app-rescue .vx-bot-line", self.css)
        self.assertIn("box-shadow: inset 0 0 0 1px rgba(32, 33, 36, 0.02);", self.css)
        self.assertIn('id="open-app-current"', open_app)
        self.assertIn('aria-hidden="true">↗</span><span>Открыть', open_app)
        self.assertIn('id="open-app-next"', open_app)
        self.assertIn('aria-hidden="true">→</span><span>Не открылось', open_app)
        self.assertIn("function setButtonContent", open_app)
        self.assertIn("setButtonContent(currentLink, '↗', 'Открыть ' + item.label)", open_app)
        self.assertIn("setButtonContent(nextButton, '⧉', 'Скопировать ссылку')", open_app)

    def test_auth_edges_use_polished_bot_controls(self):
        login = (REPO_ROOT / "web" / "templates" / "registration" / "login.html").read_text(encoding="utf-8")
        signup = (REPO_ROOT / "web" / "templates" / "cabinet" / "signup.html").read_text(encoding="utf-8")
        reset_form = (REPO_ROOT / "web" / "templates" / "registration" / "password_reset_form.html").read_text(encoding="utf-8")
        reset_confirm = (REPO_ROOT / "web" / "templates" / "registration" / "password_reset_confirm.html").read_text(encoding="utf-8")
        reset_complete = (REPO_ROOT / "web" / "templates" / "registration" / "password_reset_complete.html").read_text(encoding="utf-8")

        self.assertIn(".vx-account-bot.vx-auth-bot .auth-widget-shell", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-widget-copy", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-widget-mark", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-email-panel", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-form p", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .account-message-error", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-code-value", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-divider", self.css)
        self.assertIn("text-transform: uppercase;", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-meta-actions", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-submit .vx-bot-button-icon", self.css)
        auth_meta_actions_rule = self.css[self.css.index(".vx-account-bot.vx-auth-bot .auth-meta-actions {") :]
        auth_meta_actions_rule = auth_meta_actions_rule[: auth_meta_actions_rule.index("}")]
        self.assertIn("grid-template-columns: minmax(0, 1fr);", auth_meta_actions_rule)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-meta-actions .auth-meta-button", self.css)
        self.assertIn(".vx-account-bot.vx-auth-bot .auth-meta-actions .auth-meta-button:only-child", self.css)
        self.assertIn('aria-hidden="true">?</span><span>{{ login_forgot_password }}', login)
        self.assertIn('aria-hidden="true">+</span><span>{{ login_signup_action }}', login)
        self.assertIn('aria-hidden="true">›</span><span>{{ login_submit }}', login)
        self.assertIn('aria-hidden="true">+</span><span>{{ signup_submit }}', signup)
        self.assertIn('aria-hidden="true">‹</span><span>{{ signup_login_action }}', signup)
        self.assertIn('aria-hidden="true">›</span><span>Отправить ссылку', reset_form)
        self.assertIn('aria-hidden="true">✓</span><span>Сохранить пароль', reset_confirm)
        self.assertIn('aria-hidden="true">›</span><span>Войти', reset_complete)


if __name__ == "__main__":
    unittest.main()
