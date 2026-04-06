(function () {
  const mount = document.querySelector("[data-vx-account-app]");
  const cfg = window.VXAccountAppConfig || null;
  if (!mount || !cfg || mount.dataset.vxAccountMounted === "1") return;
  mount.dataset.vxAccountMounted = "1";

  const state = {
    authMode: "login",
    authModel: null,
    pending: false,
    toastTimer: null,
    loadingTimer: null,
    loadToken: 0,
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function iconSvg(kind) {
    if (kind === "copy") {
      return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M9 9h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2z"></path><path d="M15 9V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"></path></svg>';
    }
    if (kind === "rename") {
      return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17.25V21h3.75L17.8 9.94l-3.75-3.75L3 17.25z"></path><path d="M14.05 6.2l3.75 3.75"></path></svg>';
    }
    if (kind === "check") {
      return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"></path></svg>';
    }
    return "";
  }

  function readCookie(name) {
    const cookie = document.cookie
      .split(";")
      .map(function (part) {
        return part.trim();
      })
      .find(function (part) {
        return part.startsWith(name + "=");
      });
    return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : "";
  }

  function getCsrfToken() {
    return readCookie("csrftoken");
  }

  function normalizePath(path) {
    let next = String(path || cfg.accountPath || "/account/");
    if (!next.startsWith("/")) next = "/" + next;
    return next.endsWith("/") ? next : next + "/";
  }

  function currentRoute() {
    const path = window.location.pathname;
    const configMatch = path.match(/^\/account\/config\/(\d+)\/?$/);
    if (configMatch) {
      return {
        view: "config",
        subscriptionId: Number(configMatch[1]),
        path: normalizePath("/account/config/" + configMatch[1]),
      };
    }
    return {
      view: "dashboard",
      subscriptionId: null,
      path: normalizePath(cfg.accountPath || "/account/"),
    };
  }

  function subscriptionRenameUrl(subscriptionId) {
    const base = String(cfg.apiSubscriptionBaseUrl || "/account-app/api/subscriptions/");
    return base.replace(/\/?$/, "/") + String(subscriptionId) + "/rename/";
  }

  function apiFetch(url, options) {
    const opts = options || {};
    const headers = Object.assign(
      {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      opts.headers || {}
    );

    if (opts.method && opts.method.toUpperCase() !== "GET") {
      headers["Content-Type"] = "application/json";
      const csrfToken = getCsrfToken();
      if (csrfToken) headers["X-CSRFToken"] = csrfToken;
    }

    return fetch(url, {
      method: opts.method || "GET",
      credentials: "same-origin",
      headers: headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    }).then(async function (response) {
      let data = {};
      try {
        data = await response.json();
      } catch (error) {
        data = {};
      }
      if (!response.ok) {
        const err = new Error((data && data.error) || "Request failed");
        err.status = response.status;
        err.payload = data;
        throw err;
      }
      return data;
    });
  }

  function accessLabel(count) {
    const value = Number(count || 0);
    return value + " доступ" + (value === 1 ? "" : value > 1 && value < 5 ? "а" : "ов");
  }

  function renderLoading() {
    mount.className = "vx-native-account is-loading";
    mount.innerHTML = [
      '<div class="vx-native-account__skeleton" aria-hidden="true">',
      '<div class="vx-native-account__hero">',
      '<div class="vx-native-account__line vx-native-account__line-title"></div>',
      '<div class="vx-native-account__line vx-native-account__line-subtitle"></div>',
      '<div class="vx-native-account__chips"><span class="vx-native-account__chip"></span><span class="vx-native-account__chip"></span><span class="vx-native-account__chip"></span></div>',
      "</div>",
      '<div class="vx-native-account__grid"><div class="vx-native-account__card"></div><div class="vx-native-account__card"></div><div class="vx-native-account__card"></div><div class="vx-native-account__card"></div></div>',
      '<div class="vx-native-account__panel"></div>',
      "</div>",
    ].join("");
  }

  function preserveMountHeight() {
    const height = Math.ceil(mount.getBoundingClientRect().height || 0);
    if (height > 0) {
      mount.style.minHeight = height + "px";
    }
  }

  function releaseMountHeight() {
    window.requestAnimationFrame(function () {
      mount.style.minHeight = "";
    });
  }

  function renderError(message) {
    mount.className = "vx-native-account";
    mount.innerHTML =
      '<section class="vx-account-app__shell"><div class="vx-account-error">' +
      escapeHtml(message || "Не удалось загрузить аккаунт.") +
      "</div></section>";
  }

  function ensureToast() {
    let toast = document.querySelector("[data-vx-account-toast]");
    if (toast) return toast;
    toast = document.createElement("div");
    toast.className = "vx-account-toast";
    toast.setAttribute("data-vx-account-toast", "");
    toast.setAttribute("aria-live", "polite");
    document.body.appendChild(toast);
    return toast;
  }

  function showToast(message) {
    const toast = ensureToast();
    toast.textContent = String(message || "Ссылка скопирована");
    toast.classList.add("is-visible");
    window.clearTimeout(state.toastTimer);
    state.toastTimer = window.setTimeout(function () {
      toast.classList.remove("is-visible");
    }, 1400);
  }

  function markCopySuccess(button) {
    if (!button) return;
    button.classList.add("is-copied");
    if (button.classList.contains("vx-icon-button")) {
      const originalMarkup = button.dataset.originalMarkup || button.innerHTML;
      button.dataset.originalMarkup = originalMarkup;
      button.innerHTML = iconSvg("check");
      window.setTimeout(function () {
        button.innerHTML = button.dataset.originalMarkup || originalMarkup;
        button.classList.remove("is-copied");
      }, 1200);
      return;
    }
    const originalLabel = button.dataset.originalLabel || button.textContent;
    button.dataset.originalLabel = originalLabel;
    button.textContent = "✓ " + originalLabel;
    window.setTimeout(function () {
      button.textContent = button.dataset.originalLabel || originalLabel;
      button.classList.remove("is-copied");
    }, 1200);
  }

  function pillClass(active) {
    return active ? "vx-status-pill is-success" : "vx-status-pill is-muted";
  }

  function renderDashboard(model) {
    const subscriptions = Array.isArray(model.subscriptions) ? model.subscriptions : [];
    const telegramLinked = model.telegram && model.telegram.linked;
    const telegramPill =
      '<span class="' +
      pillClass(telegramLinked) +
      '">' +
      escapeHtml(model.telegram && model.telegram.status_text ? model.telegram.status_text : "Не привязан") +
      "</span>";

    const summaryHtml = [
      {
        label: "Пользователь",
        value: escapeHtml(model.user && model.user.username ? model.user.username : "—"),
      },
      {
        label: "ID клиента",
        value:
          model.user && model.user.client_code
            ? '<code class="vx-stat-code">' + escapeHtml(model.user.client_code) + "</code>"
            : "—",
      },
      {
        label: "Активные",
        value: escapeHtml(String(model.stats && model.stats.active_configs != null ? model.stats.active_configs : 0)),
      },
      {
        label: "Telegram",
        value:
          '<div class="vx-stat-stack">' +
          telegramPill +
          (telegramLinked && model.telegram.telegram_id
            ? '<code class="vx-stat-code">' + escapeHtml(String(model.telegram.telegram_id)) + "</code>"
            : "") +
          (!telegramLinked && model.telegram && model.telegram.link_url
            ? '<a class="vx-inline-link" href="' + escapeHtml(model.telegram.link_url) + '">Привязать</a>'
            : "") +
          "</div>",
      },
    ]
      .map(function (item) {
        return (
          '<div class="vx-account-summary__item"><div class="vx-account-summary__label">' +
          item.label +
          '</div><div class="vx-account-summary__value">' +
          item.value +
          "</div></div>"
        );
      })
      .join("");

    const cardsHtml = subscriptions.length
      ? subscriptions
          .map(function (sub) {
            return [
              '<article class="vx-config-card">',
              '<div class="vx-config-card__head">',
              '<div class="vx-config-card__header-main">',
              '<div class="vx-config-card__title-row"><div class="vx-config-card__name-group"><h3 class="vx-config-card__title"><span>' +
                escapeHtml(sub.display_name) +
                '</span></h3><button type="button" class="vx-title-edit" data-rename-toggle data-target="rename-card-' +
                escapeHtml(String(sub.id)) +
                '" aria-expanded="false" aria-label="Переименовать">' +
                iconSvg("rename") +
                '</button></div><span class="' + pillClass(!!sub.is_active) + '">' + escapeHtml(sub.status_text) + "</span></div>",
              '<div class="vx-config-card__sub">ID: ' + escapeHtml(String(sub.id)) + "</div>",
              '<form id="rename-card-' +
                escapeHtml(String(sub.id)) +
                '" class="vx-rename-panel vx-rename-panel--card" data-rename-form data-subscription-id="' +
                escapeHtml(String(sub.id)) +
                '" hidden><div class="vx-rename-row"><input type="text" class="vx-rename-input" name="display_name" maxlength="80" placeholder="Имя устройства" value="' +
                escapeHtml(sub.display_name || "") +
                '"><button type="submit" class="vx-button vx-button--ghost vx-button--compact">Сохранить</button></div></form>',
              "</div>",
              "</div>",
              '<div class="vx-config-card__meta vx-config-card__meta--single">',
              '<div class="vx-config-meta"><span>До</span><strong>' + escapeHtml(sub.expires_at || "—") + "</strong></div>",
              "</div>",
              '<div class="vx-config-card__field"><label>Ссылка</label><div class="vx-copy-row"><input type="text" readonly value="' +
                escapeHtml(sub.vless_url || "") +
                '"><button type="button" class="vx-icon-button" data-copy-text="' +
                escapeHtml(sub.vless_url || "") +
                '" aria-label="Скопировать ссылку">' +
                iconSvg("copy") +
                "</button></div></div>",
              '<div class="vx-config-card__actions"><button type="button" class="vx-button vx-button--ghost" data-nav="' +
                escapeHtml(sub.config_url) +
                '">QR и конфиг</button></div>',
              "</article>",
            ].join("");
          })
          .join("")
      : '<div class="vx-account-empty">Пока нет активных доступов. Оформите первый доступ, чтобы он появился здесь.</div>';

    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell">',
      '<section class="vx-account-hero">',
      '<div class="vx-account-hero__head">',
      '<div><h1 class="vx-account-title">' +
        escapeHtml(model.title || "Личный кабинет") +
        '</h1><p class="vx-account-subtitle">' +
        escapeHtml(model.subtitle || "") +
        "</p></div>",
      '<span class="vx-status-pill is-muted">' + escapeHtml(accessLabel(model.access_count)) + "</span>",
      "</div>",
      '<div class="vx-account-actions">',
      '<button type="button" class="vx-button vx-button--primary" data-checkout="buy">Купить доступ · ' +
        escapeHtml(model.card_price_label || "") +
        "</button>",
      '<button type="button" class="vx-button vx-button--ghost" data-checkout="renew">Продлить · ' +
        escapeHtml(model.card_price_label || "") +
        "</button>",
      "</div>",
      "</section>",
      '<section class="vx-account-summary"><div class="vx-account-summary__grid">' + summaryHtml + "</div></section>",
      '<section class="vx-section-card"><div class="vx-section-card__head"><h2>Устройства</h2><span>Активных: ' +
        escapeHtml(String(model.stats && model.stats.active_configs != null ? model.stats.active_configs : 0)) +
        " · Неактивных: " +
        escapeHtml(String(model.stats && model.stats.inactive_configs != null ? model.stats.inactive_configs : 0)) +
        '</span></div><div class="vx-config-list">' +
        cardsHtml +
        "</div></section>",
      '<div class="vx-account-actions vx-account-actions--footer"><a class="vx-button vx-button--ghost" href="' +
        escapeHtml((model.urls && model.urls.support) || cfg.supportUrl || "/instructions/") +
        '">Поддержка</a><button type="button" class="vx-button vx-button--ghost" data-logout>\u0412\u044b\u0439\u0442\u0438</button></div>',
      "</section>",
    ].join("");
  }

  function renderConfig(model) {
    const switchHtml = Array.isArray(model.subscriptions)
      ? model.subscriptions
          .map(function (item) {
            return '<option value="' + escapeHtml(item.url) + '"' + (item.selected ? " selected" : "") + ">" + escapeHtml(item.label) + "</option>";
          })
          .join("")
      : "";

    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell">',
      '<section class="vx-config-view">',
      '<div class="vx-config-view__main">',
      '<div class="vx-config-view__head">',
      '<div><h1 class="vx-account-title">Конфиг и QR</h1><p class="vx-account-subtitle vx-account-subtitle--config-name"><span>' +
        escapeHtml(model.display_name || "") +
        "</span></p></div>",
      '<span class="' + pillClass(!!model.is_active) + '">' + escapeHtml(model.status_text || "") + "</span>",
      "</div>",
      '<div class="vx-config-qr"><img src="' + escapeHtml(model.qr_image_data_url || "") + '" alt="QR конфиг"></div>',
      '<div class="vx-config-view__actions">',
      '<button type="button" class="vx-button vx-button--primary" data-copy-text="' +
        escapeHtml(model.copy_text || "") +
        '">Скопировать ссылку</button>',
      '<button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(model.dashboard_url || cfg.accountUrl) +
        '">Назад в кабинет</button>',
      "</div>",
      "</div>",
      '<aside class="vx-config-view__side">',
      '<div class="vx-config-info-grid">',
      '<article class="vx-info-card"><div class="vx-stat-label">Статус</div><div class="vx-stat-value"><span class="' +
        pillClass(!!model.is_active) +
        '">' +
        escapeHtml(model.status_text || "") +
        "</span></div></article>",
      '<article class="vx-info-card"><div class="vx-stat-label">Действует до</div><div class="vx-stat-value">' +
        escapeHtml(model.expires_at || "—") +
        "</div></article>",
      '<article class="vx-info-card vx-info-card--wide"><div class="vx-stat-label">ID клиента</div><div class="vx-stat-value">' +
        (model.client_code ? '<code class="vx-stat-code">' + escapeHtml(model.client_code) + "</code>" : "—") +
        "</div></article>",
      "</div>",
      (switchHtml
        ? '<div class="vx-field-card"><label for="vx-config-switch">Все конфиги</label><select id="vx-config-switch" class="vx-select">' +
          switchHtml +
          "</select></div>"
        : ""),
      '<div class="vx-field-card"><label>Ссылка конфигурации</label><div class="vx-copy-row"><input type="text" readonly value="' +
        escapeHtml(model.copy_text || "") +
        '"><button type="button" class="vx-icon-button" data-copy-text="' +
        escapeHtml(model.copy_text || "") +
        '" aria-label="Скопировать ссылку">' +
        iconSvg("copy") +
        '</button></div><p class="vx-field-hint">Скопируйте ссылку и импортируйте ее в клиент VPN.</p></div>',
      '<div class="vx-field-card"><div class="vx-field-card__head"><label>Имя устройства</label></div><div class="vx-field-value-row"><div class="vx-field-value">' +
        escapeHtml(model.display_name || "") +
        '</div><button type="button" class="vx-title-edit" data-rename-toggle data-target="rename-config-' +
        escapeHtml(String(model.id || "")) +
        '" aria-expanded="false" aria-label="Переименовать">' +
        iconSvg("rename") +
        '</button></div><form id="rename-config-' +
        escapeHtml(String(model.id || "")) +
        '" class="vx-rename-panel" data-rename-form data-subscription-id="' +
        escapeHtml(String(model.id || "")) +
        '" hidden><div class="vx-rename-row"><input type="text" class="vx-rename-input" name="display_name" maxlength="80" placeholder="Имя устройства" value="' +
        escapeHtml(model.display_name || "") +
        '"><button type="submit" class="vx-button vx-button--ghost vx-button--compact">Сохранить</button></div></form><p class="vx-field-hint">Измените название, чтобы проще различать конфиги в кабинете.</p></div>',
      "</aside>",
      "</section>",
      "</section>",
    ].join("");
  }

  function renderAuth(model) {
    const isSignup = state.authMode === "signup";
    const telegram = (model && model.telegram) || {};
    const hasTelegram = !!(telegram && telegram.enabled && telegram.bot_username && telegram.auth_url);
    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell">',
      '<section class="vx-auth-card">',
      '<div class="vx-auth-card__tabs">',
      '<button type="button" class="vx-auth-tab' +
        (!isSignup ? " is-active" : "") +
        '" data-auth-tab="login">Вход</button>',
      '<button type="button" class="vx-auth-tab' +
        (isSignup ? " is-active" : "") +
        '" data-auth-tab="signup">Регистрация</button>',
      "</div>",
      '<div class="vx-auth-card__body">',
      '<h1 class="vx-account-title">' + escapeHtml((model && model.title) || "Вход") + "</h1>",
      '<p class="vx-account-subtitle">' +
        escapeHtml((model && model.subtitle) || "Войдите в аккаунт, чтобы управлять доступами и конфигами.") +
        "</p>",
      hasTelegram
        ? [
            '<section class="vx-auth-telegram">',
            '<div class="vx-auth-telegram__eyebrow">\u0412\u0445\u043e\u0434 \u0447\u0435\u0440\u0435\u0437 Telegram</div>',
            '<p class="vx-auth-telegram__copy">\u0412\u043e\u0439\u0434\u0438\u0442\u0435 \u0438\u043b\u0438 \u0441\u043e\u0437\u0434\u0430\u0439\u0442\u0435 \u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u0432 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u043a \u0447\u0435\u0440\u0435\u0437 Telegram.</p>',
            '<div class="vx-auth-telegram__widget" data-telegram-login-widget data-bot-username="' +
              escapeHtml(telegram.bot_username || "") +
              '" data-auth-url="' +
              escapeHtml(telegram.auth_url || "") +
              '"></div>',
            '<div class="vx-auth-divider"><span>\u0438\u043b\u0438 \u0447\u0435\u0440\u0435\u0437 email</span></div>',
            "</section>",
          ].join("")
        : "",
      '<div class="vx-auth-errors" data-auth-errors></div>',
      !isSignup
        ? [
            '<form class="vx-auth-form" data-auth-form="login">',
            '<label>Логин или email<input type="text" name="username" autocomplete="username" required></label>',
            '<label>Пароль<input type="password" name="password" autocomplete="current-password" required></label>',
            '<button type="submit" class="vx-button vx-button--primary vx-button--block">Войти</button>',
            "</form>",
          ].join("")
        : [
            '<form class="vx-auth-form" data-auth-form="signup">',
            '<label>Логин<input type="text" name="username" autocomplete="username" required></label>',
            '<label>Email<input type="email" name="email" autocomplete="email" required></label>',
            '<label>Пароль<input type="password" name="password" autocomplete="new-password" required></label>',
            '<label>Повторите пароль<input type="password" name="password_confirm" autocomplete="new-password" required></label>',
            '<button type="submit" class="vx-button vx-button--primary vx-button--block">Создать аккаунт</button>',
            "</form>",
          ].join(""),
      '<div class="vx-auth-links"><a href="' +
        escapeHtml(cfg.supportUrl || "/instructions/") +
        '">Нужна помощь?</a><a href="' +
        escapeHtml((model && model.password_reset_url) || "/accounts/password_reset/") +
        '">Забыли пароль?</a></div>',
      "</div>",
      "</section>",
      "</section>",
    ].join("");
  }

  function initTelegramLoginWidget() {
    mount.querySelectorAll("[data-telegram-login-widget]").forEach(function (node) {
      if (!node || node.dataset.widgetReady === "1") return;

      const botUsername = node.getAttribute("data-bot-username") || "";
      const authUrl = node.getAttribute("data-auth-url") || "";
      if (!botUsername || !authUrl) return;

      node.dataset.widgetReady = "1";
      node.innerHTML = "";

      const script = document.createElement("script");
      script.async = true;
      script.src = "https://telegram.org/js/telegram-widget.js?22";
      script.setAttribute("data-telegram-login", botUsername);
      script.setAttribute("data-size", "large");
      script.setAttribute("data-lang", "ru");
      script.setAttribute("data-radius", "10");
      script.setAttribute("data-userpic", "false");
      script.setAttribute("data-request-access", "write");
      script.setAttribute("data-auth-url", authUrl);
      node.appendChild(script);
    });
  }

  function bindSharedInteractions() {
    mount.querySelectorAll("[data-copy-text]").forEach(function (button) {
      button.addEventListener("click", async function () {
        const text = button.getAttribute("data-copy-text") || "";
        if (!text) return;
        try {
          await navigator.clipboard.writeText(text);
          markCopySuccess(button);
          showToast("Ссылка скопирована");
        } catch (error) {
          console.debug("copy failed", error);
        }
      });
    });

    mount.querySelectorAll("[data-nav]").forEach(function (button) {
      button.addEventListener("click", function () {
        const nextPath = button.getAttribute("data-nav") || cfg.accountUrl;
        window.history.pushState({}, "", nextPath);
        loadCurrentView();
      });
    });

    mount.querySelectorAll("[data-checkout]").forEach(function (button) {
      button.addEventListener("click", async function () {
        const mode = button.getAttribute("data-checkout");
        if (!mode || state.pending) return;
        state.pending = true;
        button.setAttribute("disabled", "disabled");
        try {
          const endpoint = mode === "buy" ? cfg.apiBuyUrl : cfg.apiRenewUrl;
          const result = await apiFetch(endpoint, { method: "POST", body: {} });
          if (result && result.redirect_url) {
            window.location.assign(result.redirect_url);
            return;
          }
        } catch (error) {
          if (error.status === 401) {
            state.authMode = "login";
            await loadCurrentView();
            return;
          }
          renderError((error.payload && error.payload.error) || "Не удалось открыть оплату.");
          return;
        } finally {
          state.pending = false;
          button.removeAttribute("disabled");
        }
      });
    });

    mount.querySelectorAll("[data-logout]").forEach(function (button) {
      button.addEventListener("click", async function () {
        if (state.pending || !cfg.apiLogoutUrl) return;
        state.pending = true;
        button.setAttribute("disabled", "disabled");
        try {
          await apiFetch(cfg.apiLogoutUrl, { method: "POST", body: {} });
          window.history.pushState({}, "", normalizePath(cfg.accountPath || "/account/"));
          state.authMode = "login";
          await loadCurrentView();
        } catch (error) {
          showToast((error.payload && error.payload.error) || "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0432\u044b\u0439\u0442\u0438 \u0438\u0437 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430");
        } finally {
          state.pending = false;
          button.removeAttribute("disabled");
        }
      });
    });

    const select = mount.querySelector("#vx-config-switch");
    if (select) {
      select.addEventListener("change", function () {
        if (!select.value) return;
        window.history.pushState({}, "", select.value);
        loadCurrentView();
      });
    }

    mount.querySelectorAll("[data-rename-toggle]").forEach(function (button) {
      button.addEventListener("click", function () {
        const targetId = button.getAttribute("data-target") || "";
        const panel = targetId ? mount.querySelector("#" + targetId) : null;
        if (!panel) return;
        const willOpen = panel.hasAttribute("hidden");
        panel.toggleAttribute("hidden", !willOpen);
        button.setAttribute("aria-expanded", willOpen ? "true" : "false");
        if (willOpen) {
          const input = panel.querySelector("input[name='display_name']");
          if (input) {
            input.focus();
            input.select();
          }
        }
      });
    });

    mount.querySelectorAll("[data-rename-form]").forEach(function (form) {
      form.addEventListener("submit", async function (event) {
        event.preventDefault();
        if (state.pending) return;

        const input = form.querySelector("input[name='display_name']");
        const submitButton = form.querySelector("button[type='submit']");
        const subscriptionId = form.getAttribute("data-subscription-id") || "";
        const displayName = input ? String(input.value || "").trim() : "";
        if (!subscriptionId) return;
        if (!displayName) {
          if (input) input.focus();
          showToast("Введите имя устройства");
          return;
        }

        state.pending = true;
        if (submitButton) submitButton.setAttribute("disabled", "disabled");
        try {
          await apiFetch(subscriptionRenameUrl(subscriptionId), {
            method: "POST",
            body: { display_name: displayName },
          });
          showToast("Имя устройства обновлено");
          await loadCurrentView();
        } catch (error) {
          if (input) input.focus();
          showToast((error.payload && error.payload.error) || "Не удалось обновить имя");
        } finally {
          state.pending = false;
          if (submitButton) submitButton.removeAttribute("disabled");
        }
      });
    });

    mount.querySelectorAll("[data-auth-tab]").forEach(function (button) {
      button.addEventListener("click", function () {
        state.authMode = button.getAttribute("data-auth-tab") === "signup" ? "signup" : "login";
        renderAuth(
          state.authModel || {
          title: "Вход",
          subtitle: "Войдите в аккаунт, чтобы управлять доступами и конфигами.",
          password_reset_url: "/accounts/password_reset/",
          }
        );
        bindSharedInteractions();
        bindAuthInteractions();
        initTelegramLoginWidget();
      });
    });
  }

  function setAuthErrors(errors) {
    const box = mount.querySelector("[data-auth-errors]");
    if (!box) return;
    const values = Object.values(errors || {}).filter(Boolean);
    if (!values.length) {
      box.innerHTML = "";
      box.style.display = "none";
      return;
    }
    box.style.display = "block";
    box.innerHTML = values
      .map(function (value) {
        return '<div class="vx-auth-error">' + escapeHtml(value) + "</div>";
      })
      .join("");
  }

  function bindAuthInteractions() {
    mount.querySelectorAll("[data-auth-form]").forEach(function (form) {
      form.addEventListener("submit", async function (event) {
        event.preventDefault();
        if (state.pending) return;
        state.pending = true;
        const submitButton = form.querySelector("button[type='submit']");
        if (submitButton) submitButton.setAttribute("disabled", "disabled");
        setAuthErrors({});

        const formData = new FormData(form);
        const body = Object.fromEntries(formData.entries());
        const endpoint = form.getAttribute("data-auth-form") === "signup" ? cfg.apiSignupUrl : cfg.apiLoginUrl;

        try {
          await apiFetch(endpoint, { method: "POST", body: body });
          await loadCurrentView();
        } catch (error) {
          setAuthErrors(
            (error.payload && error.payload.errors) || {
              form: (error.payload && error.payload.error) || "Не удалось выполнить запрос.",
            }
          );
        } finally {
          state.pending = false;
          if (submitButton) submitButton.removeAttribute("disabled");
        }
      });
    });
  }

  async function loadCurrentView() {
    const loadToken = ++state.loadToken;
    const route = currentRoute();
    preserveMountHeight();
    window.clearTimeout(state.loadingTimer);
    state.loadingTimer = window.setTimeout(function () {
      if (loadToken === state.loadToken) {
        renderLoading();
      }
    }, 140);

    const params = new URLSearchParams();
    params.set("view", route.view);
    if (route.subscriptionId) params.set("subscription_id", String(route.subscriptionId));

    try {
      const payload = await apiFetch(cfg.apiStateUrl + "?" + params.toString());
      if (loadToken !== state.loadToken) return;
      window.clearTimeout(state.loadingTimer);

      if (!payload.authenticated) {
        state.authModel = payload.auth || {};
        renderAuth(state.authModel);
        bindSharedInteractions();
        bindAuthInteractions();
        initTelegramLoginWidget();
        releaseMountHeight();
        return;
      }

      if (payload.view === "config" && payload.config) {
        renderConfig(payload.config);
      } else {
        renderDashboard(payload.dashboard || {});
      }
      bindSharedInteractions();
      releaseMountHeight();
    } catch (error) {
      if (loadToken !== state.loadToken) return;
      window.clearTimeout(state.loadingTimer);
      renderError((error.payload && error.payload.error) || "Не удалось загрузить страницу аккаунта.");
      releaseMountHeight();
    }
  }

  window.addEventListener("popstate", function () {
    loadCurrentView();
  });

  loadCurrentView();
})();
