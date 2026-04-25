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
    const search = new URLSearchParams(window.location.search || "");
    if (/^\/account\/settings\/?$/i.test(path)) {
      return {
        view: "settings",
        subscriptionId: null,
        path: normalizePath("/account/settings/"),
      };
    }
    if (/^\/account\/link\/?$/i.test(path)) {
      return {
        view: "link",
        subscriptionId: null,
        path: normalizePath("/account/link/"),
      };
    }
    if (/^\/account\/buy\/?$/i.test(path)) {
      return {
        view: "checkout-buy",
        subscriptionId: null,
        path: normalizePath("/account/buy/"),
      };
    }
    if (/^\/account\/renew\/?$/i.test(path)) {
      const subscriptionIdRaw = search.get("subscription_id") || "";
      return {
        view: "checkout-renew",
        subscriptionId: /^\d+$/.test(subscriptionIdRaw) ? Number(subscriptionIdRaw) : null,
        path: normalizePath("/account/renew/"),
      };
    }
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

  function subscriptionDeleteUrl(subscriptionId) {
    const base = String(cfg.apiSubscriptionBaseUrl || "/account-app/api/subscriptions/");
    return base.replace(/\/?$/, "/") + String(subscriptionId) + "/delete/";
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
      escapeHtml(model.telegram && model.telegram.status_text ? model.telegram.status_text : "\u041d\u0435 \u043f\u0440\u0438\u0432\u044f\u0437\u0430\u043d") +
      "</span>";

    const summaryHtml = [
      {
        label: "\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c",
        value: escapeHtml(model.user && model.user.username ? model.user.username : "\u2014"),
      },
      {
        label: "ID \u043a\u043b\u0438\u0435\u043d\u0442\u0430",
        value:
          model.user && model.user.client_code
            ? '<code class="vx-stat-code">' + escapeHtml(model.user.client_code) + "</code>"
            : "\u2014",
      },
      {
        label: "\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0435",
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
            ? '<button type="button" class="vx-inline-link vx-inline-link--button" data-nav="' + escapeHtml(model.telegram.link_url) + '">\u041f\u0440\u0438\u0432\u044f\u0437\u0430\u0442\u044c</button>'
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
            const primaryLink = sub.feed_url || sub.subscription_url || sub.vless_url || "";
            return [
              '<article class="vx-config-card">',
              '<div class="vx-config-card__head">',
              '<div class="vx-config-card__header-main">',
              '<div class="vx-config-card__title-row"><div class="vx-config-card__name-group"><h3 class="vx-config-card__title"><span>' +
                escapeHtml(sub.display_name) +
                '</span></h3><button type="button" class="vx-title-edit" data-rename-toggle data-target="rename-card-' +
                escapeHtml(String(sub.id)) +
                '" aria-expanded="false" aria-label="\u041f\u0435\u0440\u0435\u0438\u043c\u0435\u043d\u043e\u0432\u0430\u0442\u044c">' +
                iconSvg("rename") +
                '</button></div><span class="' + pillClass(!!sub.is_active) + '">' + escapeHtml(sub.status_text) + "</span></div>",
              '<div class="vx-config-card__sub">ID: ' + escapeHtml(String(sub.id)) + "</div>",
              '<form id="rename-card-' +
                escapeHtml(String(sub.id)) +
                '" class="vx-rename-panel vx-rename-panel--card" data-rename-form data-subscription-id="' +
                escapeHtml(String(sub.id)) +
                '" hidden><div class="vx-rename-row"><input type="text" class="vx-rename-input" name="display_name" maxlength="80" placeholder="\u0418\u043c\u044f \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u0430" value="' +
                escapeHtml(sub.display_name || "") +
                '"><button type="submit" class="vx-button vx-button--ghost vx-button--compact">\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c</button></div></form>',
              "</div>",
              "</div>",
              '<div class="vx-config-card__meta vx-config-card__meta--single">',
              '<div class="vx-config-meta"><span>\u0414\u043e</span><strong>' + escapeHtml(sub.expires_at || "\u2014") + "</strong></div>",
              "</div>",
              '<div class="vx-config-card__field"><label>Subscription URL</label><div class="vx-copy-row"><input type="text" readonly value="' +
                escapeHtml(primaryLink) +
                '"><button type="button" class="vx-icon-button" data-copy-text="' +
                escapeHtml(primaryLink) +
                '" aria-label="\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443">' +
                iconSvg("copy") +
                "</button></div></div>",
              '<div class="vx-config-card__actions"><button type="button" class="vx-button vx-button--ghost" data-nav="' +
                escapeHtml(sub.config_url) +
                '">QR \u0438 \u043a\u043e\u043d\u0444\u0438\u0433</button>' +
                (sub.can_delete
                  ? '<button type="button" class="vx-button vx-button--danger" data-delete-subscription="' +
                    escapeHtml(String(sub.id)) +
                    '">\u0423\u0434\u0430\u043b\u0438\u0442\u044c</button>'
                  : "") +
                "</div>",
              "</article>",
            ].join("");
          })
          .join("")
      : '<div class="vx-account-empty">\u041f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445 \u0434\u043e\u0441\u0442\u0443\u043f\u043e\u0432. \u041e\u0444\u043e\u0440\u043c\u0438\u0442\u0435 \u043f\u0435\u0440\u0432\u044b\u0439 \u0434\u043e\u0441\u0442\u0443\u043f, \u0447\u0442\u043e\u0431\u044b \u043e\u043d \u043f\u043e\u044f\u0432\u0438\u043b\u0441\u044f \u0437\u0434\u0435\u0441\u044c.</div>';

    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell">',
      '<section class="vx-account-hero">',
      '<div class="vx-account-hero__head">',
      '<div><h1 class="vx-account-title">' +
        escapeHtml(model.title || "\u041b\u0438\u0447\u043d\u044b\u0439 \u043a\u0430\u0431\u0438\u043d\u0435\u0442") +
        '</h1><p class="vx-account-subtitle">' +
        escapeHtml(model.subtitle || "") +
        "</p></div>",
      '<span class="vx-status-pill is-muted">' + escapeHtml(accessLabel(model.access_count)) + "</span>",
      "</div>",
      '<div class="vx-account-actions">',
      '<button type="button" class="vx-button vx-button--primary" data-checkout="buy">\u041a\u0443\u043f\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f \u00b7 ' +
        escapeHtml(model.card_price_label || "") +
        "</button>",
      '<button type="button" class="vx-button vx-button--ghost" data-checkout="renew">\u041f\u0440\u043e\u0434\u043b\u0438\u0442\u044c \u00b7 ' +
        escapeHtml(model.card_price_label || "") +
        "</button>",
      "</div>",
      "</section>",
      '<section class="vx-account-summary"><div class="vx-account-summary__grid">' + summaryHtml + "</div></section>",
      '<section class="vx-section-card"><div class="vx-section-card__head"><h2>\u0423\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u0430</h2><span>\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0445: ' +
        escapeHtml(String(model.stats && model.stats.active_configs != null ? model.stats.active_configs : 0)) +
        ' \u00b7 \u041d\u0435\u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445: ' +
        escapeHtml(String(model.stats && model.stats.inactive_configs != null ? model.stats.inactive_configs : 0)) +
        '</span></div><div class="vx-config-list">' +
        cardsHtml +
        "</div></section>",
      '<div class="vx-account-actions vx-account-actions--footer"><a class="vx-button vx-button--ghost" href="' +
        escapeHtml((model.urls && model.urls.support) || cfg.supportUrl || "/instructions/") +
        '">\u041f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430</a><button type="button" class="vx-button vx-button--ghost" data-nav="/account/settings/">\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438</button><button type="button" class="vx-button vx-button--ghost" data-logout>\u0412\u044b\u0439\u0442\u0438</button></div>',
      "</section>",
    ].join("");
  }

  function renderSettings(model) {
    const profile = (model && model.user) || {};

    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell">',
      '<section class="vx-section-card"><div class="vx-section-card__head"><h2>\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438</h2><span>\u0418\u0437\u043c\u0435\u043d\u044f\u0439\u0442\u0435 \u0434\u0430\u043d\u043d\u044b\u0435 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430 \u043d\u0430 \u043e\u0442\u0434\u0435\u043b\u044c\u043d\u043e\u0439 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0435.</span></div>',
      '<form class="vx-profile-form" data-profile-form>',
      '<div class="vx-profile-grid">',
      '<label class="vx-profile-field"><span>\u041b\u043e\u0433\u0438\u043d</span><input type="text" name="username" maxlength="150" required value="' + escapeHtml(profile.username || "") + '"></label>',
      '<label class="vx-profile-field"><span>Email</span><input type="email" name="email" maxlength="254" required value="' + escapeHtml(profile.email || "") + '"></label>',
      '<label class="vx-profile-field"><span>\u0418\u043c\u044f</span><input type="text" name="first_name" maxlength="150" value="' + escapeHtml(profile.first_name || "") + '"></label>',
      '<label class="vx-profile-field"><span>\u0424\u0430\u043c\u0438\u043b\u0438\u044f</span><input type="text" name="last_name" maxlength="150" value="' + escapeHtml(profile.last_name || "") + '"></label>',
      "</div>",
      '<div class="vx-profile-actions"><button type="submit" class="vx-button vx-button--primary">\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u0434\u0430\u043d\u043d\u044b\u0435</button></div>',
      '<div class="vx-auth-errors vx-profile-errors" data-profile-errors style="display:none"></div>',
      "</form>",
      '<div class="vx-account-actions vx-account-actions--footer"><button type="button" class="vx-button vx-button--ghost" data-nav="' + escapeHtml((model.urls && model.urls.dashboard) || (cfg.accountUrl || "/account/")) + '">\u041d\u0430\u0437\u0430\u0434 \u0432 \u043a\u0430\u0431\u0438\u043d\u0435\u0442</button><button type="button" class="vx-button vx-button--ghost" data-logout>\u0412\u044b\u0439\u0442\u0438</button></div>',
      "</section>",
      "</section>",
    ].join("");
  }

  function renderLink(model) {
    const hasBotLink = !!(model && model.deep_link);
    const linkedBlock =
      model && model.linked && model.linked_telegram_id
        ? '<div class="vx-status-banner is-success">Сейчас привязан Telegram ID: <code>' + escapeHtml(String(model.linked_telegram_id)) + "</code></div>"
        : "";
    const primaryAction = hasBotLink
      ? '<a class="vx-button vx-button--primary vx-button--block" href="' + escapeHtml(model.deep_link || "") + '" target="_blank" rel="noopener">Открыть бота и привязать</a>'
      : '<div class="vx-account-empty">Не задан TELEGRAM_BOT_USERNAME. Временно отправьте боту команду <code>/start link_' + escapeHtml(model.link_code || "") + "</code>.</div>";
    const helperText = hasBotLink
      ? '<p class="vx-field-hint">Если кнопка не сработала, отправьте боту команду: <code>/start link_' + escapeHtml(model.link_code || "") + "</code></p>"
      : "";

    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell">',
      '<section class="vx-section-card">',
      '<div class="vx-section-card__head"><h1>' + escapeHtml((model && model.title) || "Привязка Telegram") + '</h1><span>' + escapeHtml((model && model.subtitle) || "") + "</span></div>",
      '<div class="vx-link-body">',
      linkedBlock,
      '<div class="vx-field-card"><label>Код привязки</label><div class="vx-link-code"><code>' + escapeHtml((model && model.link_code) || "") + '</code></div><p class="vx-field-hint">Код действует до: ' + escapeHtml((model && model.expires_at) || "—") + "</p></div>",
      primaryAction,
      helperText,
      '<div class="vx-account-actions vx-account-actions--footer"><button type="button" class="vx-button vx-button--ghost" data-link-regenerate>Новый код</button><button type="button" class="vx-button vx-button--ghost" data-nav="' + escapeHtml((model && model.dashboard_url) || (cfg.accountUrl || "/account/")) + '">Назад в кабинет</button></div>',
      "</div>",
      "</section>",
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
      (model.can_delete
        ? '<button type="button" class="vx-button vx-button--danger" data-delete-subscription="' +
          escapeHtml(String(model.id || "")) +
          '">Удалить</button>'
        : "") +
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

    mount.querySelectorAll("[data-delete-subscription]").forEach(function (button) {
      button.addEventListener("click", async function () {
        const subscriptionId = button.getAttribute("data-delete-subscription") || "";
        if (!subscriptionId || state.pending) return;
        if (!window.confirm("Удалить этот неактивный конфиг?")) return;

        state.pending = true;
        button.setAttribute("disabled", "disabled");
        try {
          await apiFetch(subscriptionDeleteUrl(subscriptionId), {
            method: "POST",
            body: {},
          });
          showToast("Конфиг удален");
          if (/^\/account\/config\/\d+\/?$/i.test(window.location.pathname)) {
            window.history.pushState({}, "", normalizePath(cfg.accountPath || "/account/"));
          }
          await loadCurrentView();
        } catch (error) {
          showToast((error.payload && error.payload.error) || "Не удалось удалить конфиг");
        } finally {
          state.pending = false;
          button.removeAttribute("disabled");
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

    mount.querySelectorAll("[data-profile-form]").forEach(function (form) {
      form.addEventListener("submit", async function (event) {
        event.preventDefault();
        if (state.pending || !cfg.apiProfileUrl) return;
        state.pending = true;
        const submitButton = form.querySelector("button[type='submit']");
        const errorBox = form.querySelector("[data-profile-errors]");
        if (submitButton) submitButton.setAttribute("disabled", "disabled");
        if (errorBox) {
          errorBox.innerHTML = "";
          errorBox.style.display = "none";
        }

        const formData = new FormData(form);
        const body = Object.fromEntries(formData.entries());

        try {
          await apiFetch(cfg.apiProfileUrl, { method: "POST", body: body });
          showToast("Данные аккаунта обновлены");
          await loadCurrentView();
        } catch (error) {
          const errors = (error.payload && error.payload.errors) || {};
          const values = Object.values(errors).filter(Boolean);
          if (errorBox && values.length) {
            errorBox.style.display = "block";
            errorBox.innerHTML = values
              .map(function (value) {
                return '<div class="vx-auth-error">' + escapeHtml(value) + "</div>";
              })
              .join("");
          } else {
            showToast((error.payload && error.payload.error) || "Не удалось обновить профиль");
          }
        } finally {
          state.pending = false;
          if (submitButton) submitButton.removeAttribute("disabled");
        }
      });
    });

    mount.querySelectorAll("[data-link-regenerate]").forEach(function (button) {
      button.addEventListener("click", async function () {
        if (state.pending || !cfg.apiLinkUrl) return;
        state.pending = true;
        button.setAttribute("disabled", "disabled");
        try {
          const result = await apiFetch(cfg.apiLinkUrl, { method: "POST", body: {} });
          if (result && result.link) {
            renderLink(result.link);
            bindSharedInteractions();
            showToast("Новый код привязки создан");
          }
        } catch (error) {
          showToast((error.payload && error.payload.error) || "Не удалось создать новый код");
        } finally {
          state.pending = false;
          button.removeAttribute("disabled");
        }
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

      if (route.view === "checkout-buy" || route.view === "checkout-renew") {
        try {
          const endpoint = route.view === "checkout-buy" ? cfg.apiBuyUrl : cfg.apiRenewUrl;
          const body = route.view === "checkout-renew" && route.subscriptionId ? { subscription_id: route.subscriptionId } : {};
          const result = await apiFetch(endpoint, { method: "POST", body: body });
          if (result && result.redirect_url) {
            window.location.assign(result.redirect_url);
            return;
          }
          renderError("Не удалось открыть оплату.");
          releaseMountHeight();
          return;
        } catch (error) {
          renderError((error.payload && error.payload.error) || "Не удалось открыть оплату.");
          releaseMountHeight();
          return;
        }
      }

      if (payload.view === "config" && payload.config) {
        renderConfig(payload.config);
      } else if (route.view === "settings") {
        renderSettings(payload.dashboard || {});
      } else if (payload.view === "link" && payload.link) {
        renderLink(payload.link);
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
