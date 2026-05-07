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
    paymentPollTimer: null,
    loadToken: 0,
    telegramSessionSynced: false,
    telegramSessionSyncing: null,
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

  function currentReturnTo() {
    return window.location.pathname + window.location.search + window.location.hash;
  }

  function telegramWebApp() {
    return window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  }

  function openTelegramLink(url) {
    const targetUrl = String(url || "").trim();
    if (!targetUrl) return;

    const tg = telegramWebApp();
    try {
      if (tg && typeof tg.openTelegramLink === "function" && /^https:\/\/t\.me\//i.test(targetUrl)) {
        tg.openTelegramLink(targetUrl);
        return;
      }
    } catch (_error) {}

    window.location.assign(targetUrl);
  }

  function syncTelegramWebAppSession() {
    if (state.telegramSessionSynced) return Promise.resolve(false);
    if (state.telegramSessionSyncing) return state.telegramSessionSyncing;

    const tg = telegramWebApp();
    const initData = tg && tg.initData ? String(tg.initData) : "";
    const endpoint = String(cfg.apiTelegramWebAppAuthUrl || "/api/auth/telegram/webapp");
    if (!initData || !endpoint) {
      return Promise.resolve(false);
    }

    try {
      if (tg.ready) tg.ready();
      if (tg.expand) tg.expand();
    } catch (_error) {}

    const dedupeKey = "vx_account_app_tg_auth_done:" + initData;
    if (window.sessionStorage && sessionStorage.getItem(dedupeKey) === "1") {
      state.telegramSessionSynced = true;
      return Promise.resolve(false);
    }

    state.telegramSessionSyncing = fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({
        initData: initData,
        returnTo: currentReturnTo(),
      }),
    })
      .then(async function (response) {
        if (!response.ok) {
          state.telegramSessionSynced = false;
          return false;
        }
        let payload = {};
        try {
          payload = await response.json();
        } catch (_error) {
          payload = {};
        }
        if (window.sessionStorage) sessionStorage.setItem(dedupeKey, "1");
        state.telegramSessionSynced = true;
        if (payload && payload.redirect) {
          const target = new URL(payload.redirect, window.location.origin);
          const current = new URL(window.location.href);
          if (target.pathname + target.search !== current.pathname + current.search) {
            window.history.replaceState({}, "", target.pathname + target.search + target.hash);
          }
        }
        return true;
      })
      .catch(function () {
        state.telegramSessionSynced = false;
        return false;
      })
      .finally(function () {
        state.telegramSessionSyncing = null;
      });

    return state.telegramSessionSyncing;
  }

  function normalizePath(path) {
    const raw = String(path || cfg.accountPath || "/account/");
    const parts = raw.match(/^([^?#]*)([?#].*)?$/) || ["", raw, ""];
    let pathname = parts[1] || "/";
    const suffix = parts[2] || "";
    if (!pathname.startsWith("/")) pathname = "/" + pathname;
    if (!pathname.endsWith("/")) pathname += "/";
    return pathname + suffix;
  }

  function accountRouteUrl(params) {
    const query = new URLSearchParams(params || {});
    return normalizePath(cfg.accountPath || "/account/") + (query.toString() ? "?" + query.toString() : "");
  }

  function currentRoute() {
    const path = window.location.pathname;
    const search = new URLSearchParams(window.location.search || "");
    const queryView = String(search.get("view") || "").trim().toLowerCase();
    if (queryView === "instructions") {
      const device = String(search.get("device") || "").trim().toLowerCase();
      return {
        view: "instructions",
        subscriptionId: null,
        device: /^(iphone|ios|android|desktop|windows|macos|mac)$/.test(device) ? device : "",
        path: accountRouteUrl({ view: "instructions", device: device }),
      };
    }
    if (queryView === "support") {
      return {
        view: "support",
        subscriptionId: null,
        path: accountRouteUrl({ view: "support" }),
      };
    }
    if (queryView === "config") {
      const subscriptionIdRaw = search.get("subscription_id") || search.get("id") || "";
      return {
        view: "config",
        subscriptionId: /^\d+$/.test(subscriptionIdRaw) ? Number(subscriptionIdRaw) : null,
        device: "",
        path: accountRouteUrl({ view: "config", subscription_id: subscriptionIdRaw }),
      };
    }
    if (/^\/account\/settings\/?$/i.test(path)) {
      return {
        view: "settings",
        subscriptionId: null,
        device: "",
        path: normalizePath("/account/settings/"),
      };
    }
    if (/^\/account\/link\/?$/i.test(path)) {
      return {
        view: "link",
        subscriptionId: null,
        device: "",
        path: normalizePath("/account/link/"),
      };
    }
    if (/^\/account\/buy\/?$/i.test(path)) {
      return {
        view: "checkout-buy",
        subscriptionId: null,
        device: "",
        path: normalizePath("/account/buy/"),
      };
    }
    if (/^\/account\/renew\/?$/i.test(path)) {
      const subscriptionIdRaw = search.get("subscription_id") || "";
      return {
        view: "checkout-renew",
        subscriptionId: /^\d+$/.test(subscriptionIdRaw) ? Number(subscriptionIdRaw) : null,
        device: "",
        path: normalizePath("/account/renew/"),
      };
    }
    const configMatch = path.match(/^\/account\/config\/(\d+)\/?$/);
    if (configMatch) {
      return {
        view: "config",
        subscriptionId: Number(configMatch[1]),
        device: "",
        path: normalizePath("/account/config/" + configMatch[1]),
      };
    }
    return {
      view: "dashboard",
      subscriptionId: null,
      device: "",
      path: normalizePath(cfg.accountPath || "/account/"),
    };
  }

  function updateTelegramBackButton(route) {
    const tg = telegramWebApp();
    const backButton = tg && tg.BackButton ? tg.BackButton : null;
    if (!backButton) return;

    const view = route && route.view ? route.view : "dashboard";
    const isRootView = view === "dashboard" || view === "auth";
    try {
      if (isRootView) {
        backButton.hide();
      } else {
        backButton.show();
      }
    } catch (_error) {}
  }

  function goBackInAccountApp() {
    const route = currentRoute();
    if (route.view !== "dashboard" && window.history.length > 1) {
      window.history.back();
      return;
    }

    window.history.pushState({}, "", normalizePath(cfg.accountPath || "/account/"));
    loadCurrentView();
  }

  function bindTelegramBackButton() {
    const tg = telegramWebApp();
    const backButton = tg && tg.BackButton ? tg.BackButton : null;
    if (!backButton || !backButton.onClick) return;

    try {
      backButton.onClick(goBackInAccountApp);
    } catch (_error) {}
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

  function legacyAccessLabel(count) {
    const value = Number(count || 0);
    return value + " доступ" + (value === 1 ? "" : value > 1 && value < 5 ? "а" : "ов");
  }

  function accessLabel(count) {
    const value = Number(count || 0);
    const mod10 = Math.abs(value) % 10;
    const mod100 = Math.abs(value) % 100;
    const suffix = mod10 === 1 && mod100 !== 11 ? "" : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14) ? "\u0430" : "\u043e\u0432";
    return value + " \u0434\u043e\u0441\u0442\u0443\u043f" + suffix;
  }

  function renderLoading() {
    mount.className = "vx-native-account is-loading";
    mount.innerHTML = [
      '<section class="vx-account-app__shell vx-account-app__shell--loading" aria-live="polite">',
      '<section class="vx-section-card vx-loading-card">',
      '<div class="vx-loading-body">',
      '<div class="vx-loading-status"><span class="vx-loading-spinner" aria-hidden="true"></span><strong>\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u043c \u043a\u0430\u0431\u0438\u043d\u0435\u0442</strong><small>\u041f\u0440\u043e\u0432\u0435\u0440\u044f\u0435\u043c \u0430\u043a\u043a\u0430\u0443\u043d\u0442, \u0434\u043e\u0441\u0442\u0443\u043f\u044b \u0438 QR.</small></div>',
      '<div class="vx-loading-rows" aria-hidden="true"><span></span><span></span><span></span></div>',
      "</div>",
      "</section>",
      "</section>",
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

  function renderLegacyError(message) {
    const safeMessage = message || "Не удалось загрузить аккаунт.";
    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell vx-account-app__shell--error">',
      '<section class="vx-section-card vx-error-card">',
      '<div class="vx-section-card__head"><h1>Нужно повторить</h1><span>Мы не смогли открыть этот экран.</span></div>',
      '<div class="vx-error-body">',
      '<div class="vx-account-error">' + escapeHtml(safeMessage) + "</div>",
      '<div class="vx-account-actions vx-account-actions--error"><button type="button" class="vx-button vx-button--primary" data-retry-load>Повторить</button><button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(normalizePath(cfg.accountPath || "/account/")) +
        '">Мой VPN</button><button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(accountRouteUrl({ view: "support" })) +
        '">Поддержка</button></div>',
      "</div>",
      "</section>",
      "</section>",
    ].join("");
  }

  function renderError(message) {
    const safeMessage = message || "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0430\u043a\u043a\u0430\u0443\u043d\u0442.";
    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell vx-account-app__shell--error">',
      '<section class="vx-section-card vx-error-card">',
      '<div class="vx-section-card__head"><h1>\u041d\u0443\u0436\u043d\u043e \u043f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u044c</h1><span>\u041c\u044b \u043d\u0435 \u0441\u043c\u043e\u0433\u043b\u0438 \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u044d\u0442\u043e\u0442 \u044d\u043a\u0440\u0430\u043d.</span></div>',
      '<div class="vx-error-body">',
      '<div class="vx-account-error">' + escapeHtml(safeMessage) + "</div>",
      '<div class="vx-account-actions vx-account-actions--error"><button type="button" class="vx-button vx-button--primary" data-retry-load>\u041f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u044c</button><button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(normalizePath(cfg.accountPath || "/account/")) +
        '">\u041c\u043e\u0439 VPN</button><button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(accountRouteUrl({ view: "support" })) +
        '">\u041f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430</button></div>',
      "</div>",
      "</section>",
      "</section>",
    ].join("");
  }

  function renderCheckoutProgress(route) {
    const isRenew = route && route.view === "checkout-renew";
    const title = isRenew ? "\u041f\u0435\u0440\u0435\u0445\u043e\u0434\u0438\u043c \u043a \u043f\u0440\u043e\u0434\u043b\u0435\u043d\u0438\u044e" : "\u041f\u0435\u0440\u0435\u0445\u043e\u0434\u0438\u043c \u043a \u043e\u043f\u043b\u0430\u0442\u0435";
    const subtitle = isRenew
      ? "\u041e\u0442\u043a\u0440\u043e\u0435\u0442\u0441\u044f \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0430 \u043e\u043f\u043b\u0430\u0442\u044b \u0434\u043b\u044f \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u043e\u0433\u043e \u0434\u043e\u0441\u0442\u0443\u043f\u0430."
      : "\u041e\u0442\u043a\u0440\u043e\u0435\u0442\u0441\u044f \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0430 \u0431\u0430\u043d\u043a\u0430. \u041f\u043e\u0441\u043b\u0435 \u043e\u043f\u043b\u0430\u0442\u044b \u0432\u0435\u0440\u043d\u0438\u0442\u0435\u0441\u044c \u0432 \u041c\u043e\u0439 VPN.";
    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell vx-account-app__shell--checkout">',
      '<section class="vx-section-card vx-checkout-card">',
      '<div class="vx-section-card__head"><h1>' + escapeHtml(title) + '</h1><span>' + escapeHtml(subtitle) + "</span></div>",
      '<div class="vx-checkout-body">',
      '<div class="vx-checkout-status"><span class="vx-checkout-spinner" aria-hidden="true"></span><strong>\u041e\u0442\u043a\u0440\u044b\u0432\u0430\u0435\u043c \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0443 \u0431\u0430\u043d\u043a\u0430</strong><small>\u041e\u043f\u043b\u0430\u0442\u0430 \u043e\u0442\u043a\u0440\u043e\u0435\u0442\u0441\u044f \u0432\u043e \u0432\u043d\u0435\u0448\u043d\u0435\u043c \u043e\u043a\u043d\u0435. \u041d\u0435 \u0437\u0430\u043a\u0440\u044b\u0432\u0430\u0439\u0442\u0435 Telegram.</small></div>',
      '<ol class="vx-checkout-steps"><li class="is-active"><span></span><strong>\u0421\u043e\u0437\u0434\u0430\u0435\u043c \u0437\u0430\u043a\u0430\u0437</strong></li><li><span></span><strong>\u041e\u0442\u043a\u0440\u044b\u0432\u0430\u0435\u043c \u043e\u043f\u043b\u0430\u0442\u0443 \u0432 \u0431\u0430\u043d\u043a\u0435</strong></li><li><span></span><strong>' +
        escapeHtml(isRenew ? "\u041f\u0440\u043e\u0434\u043b\u0435\u043d\u0438\u0435 \u043f\u043e\u044f\u0432\u0438\u0442\u0441\u044f \u0432 \u041c\u043e\u0439 VPN" : "\u0414\u043e\u0441\u0442\u0443\u043f \u043f\u043e\u044f\u0432\u0438\u0442\u0441\u044f \u0432 \u041c\u043e\u0439 VPN") +
        "</strong></li></ol>",
      '<div class="vx-checkout-note"><strong>\u0415\u0441\u043b\u0438 \u043e\u043f\u043b\u0430\u0442\u0430 \u043d\u0435 \u043e\u0442\u043a\u0440\u044b\u043b\u0430\u0441\u044c</strong><span>\u0412\u0435\u0440\u043d\u0438\u0442\u0435\u0441\u044c \u0432 \u041c\u043e\u0439 VPN \u0438 \u043f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u0435. \u041f\u043e\u0441\u043b\u0435 \u0443\u0441\u043f\u0435\u0448\u043d\u043e\u0439 \u043e\u043f\u043b\u0430\u0442\u044b \u0434\u043e\u0441\u0442\u0443\u043f \u043e\u0431\u043d\u043e\u0432\u0438\u0442\u0441\u044f \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438.</span></div>',
      '<div class="vx-account-actions vx-account-actions--checkout"><button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(normalizePath(cfg.accountPath || "/account/")) +
        '">\u041c\u043e\u0439 VPN</button><button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(accountRouteUrl({ view: "support" })) +
        '">\u041f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430</button></div>',
      "</div>",
      "</section>",
      "</section>",
    ].join("");
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

  function legacyShowToast(message) {
    const toast = ensureToast();
    toast.textContent = String(message || "Ссылка скопирована");
    toast.classList.add("is-visible");
    window.clearTimeout(state.toastTimer);
    state.toastTimer = window.setTimeout(function () {
      toast.classList.remove("is-visible");
    }, 1400);
  }

  function showToast(message) {
    const toast = ensureToast();
    toast.textContent = String(message || "\u0421\u0441\u044b\u043b\u043a\u0430 \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u0430");
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
    window.clearTimeout(state.paymentPollTimer);
    const subscriptions = Array.isArray(model.subscriptions) ? model.subscriptions : [];
    const renewableSubscriptions = subscriptions.filter(function (sub) {
      return !!(sub && sub.can_renew);
    });
    const activeCount =
      model.stats && model.stats.active_configs != null
        ? Number(model.stats.active_configs)
        : subscriptions.filter(function (sub) {
            return !!(sub && sub.is_active);
          }).length;
    const inactiveCount =
      model.stats && model.stats.inactive_configs != null
        ? Number(model.stats.inactive_configs)
        : Math.max(0, subscriptions.length - activeCount);
    const activeSubscription = subscriptions.find(function (sub) {
      return !!(sub && sub.is_active);
    });
    const activeImportUrl = activeSubscription && activeSubscription.auto_import_url ? String(activeSubscription.auto_import_url) : "";
    const trialUrl = String(cfg.telegramTrialUrl || cfg.telegramBotUrl || cfg.supportTelegramUrl || "").trim();
    const trialButtonHtml = trialUrl
      ? '<a class="vx-button vx-button--primary" href="' +
        escapeHtml(trialUrl) +
        '" data-telegram-link="' +
        escapeHtml(trialUrl) +
        '" target="_blank" rel="noopener">\ud83c\udf81 7 \u0434\u043d\u0435\u0439 \u0431\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e</a>'
      : "";
    const dashboardTitle = "\u041c\u043e\u0439 VPN";
    const dashboardSubtitle =
      activeCount > 0
        ? "QR, \u043f\u0440\u043e\u0434\u043b\u0435\u043d\u0438\u0435 \u0438 \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u0438 \u0440\u044f\u0434\u043e\u043c."
        : "\u041d\u0430\u0447\u043d\u0438\u0442\u0435 \u0441 7 \u0434\u043d\u0435\u0439 \u0431\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e \u0438\u043b\u0438 \u043a\u0443\u043f\u0438\u0442\u0435 \u0434\u043e\u0441\u0442\u0443\u043f.";
    const heroMetricsHtml =
      '<div class="vx-hero-metrics"><div><span>\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0445</span><strong>' +
      escapeHtml(String(activeCount)) +
      '</strong></div><div><span>\u0414\u043e</span><strong>' +
      escapeHtml(activeSubscription && activeSubscription.expires_at ? activeSubscription.expires_at : "\u2014") +
      "</strong></div></div>";
    const telegramLinked = model.telegram && model.telegram.linked;
    const telegramPill =
      '<span class="' +
      pillClass(telegramLinked) +
      '">' +
      escapeHtml(model.telegram && model.telegram.status_text ? model.telegram.status_text : "\u041d\u0435 \u043f\u0440\u0438\u0432\u044f\u0437\u0430\u043d") +
      "</span>";
    const username = model.user && model.user.username ? model.user.username : "\u2014";
    const clientCode = model.user && model.user.client_code ? String(model.user.client_code) : "";
    const clientCodeHtml = clientCode
      ? '<div class="vx-account-identity__value"><code class="vx-stat-code">' +
        escapeHtml(clientCode) +
        '</code><button type="button" class="vx-icon-button" data-copy-text="' +
        escapeHtml(clientCode) +
        '" data-copy-toast="ID \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d" aria-label="\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c ID \u043a\u043b\u0438\u0435\u043d\u0442\u0430">' +
        iconSvg("copy") +
        "</button></div>"
      : '<div class="vx-account-identity__value">\u2014</div>';
    const telegramDetailHtml =
      telegramLinked && model.telegram.telegram_id
        ? '<code class="vx-stat-code">' + escapeHtml(String(model.telegram.telegram_id)) + "</code>"
        : !telegramLinked && model.telegram && model.telegram.link_url
          ? '<button type="button" class="vx-inline-link vx-inline-link--button" data-nav="' +
            escapeHtml(model.telegram.link_url) +
            '">\u041f\u0440\u0438\u0432\u044f\u0437\u0430\u0442\u044c Telegram</button>'
          : "";
    const accountIdentityHtml = [
      '<section class="vx-account-identity">',
      '<div class="vx-account-identity__main">',
      '<div class="vx-account-identity__item"><span>\u0410\u043a\u043a\u0430\u0443\u043d\u0442</span><strong>' +
        escapeHtml(username) +
        "</strong></div>",
      '<div class="vx-account-identity__item"><span>ID \u043a\u043b\u0438\u0435\u043d\u0442\u0430</span>' + clientCodeHtml + "</div>",
      "</div>",
      '<div class="vx-account-identity__telegram"><span>Telegram</span><div>' + telegramPill + telegramDetailHtml + "</div></div>",
      '<div class="vx-account-secondary"><button type="button" class="vx-inline-link vx-inline-link--button" data-nav="/account/settings/">\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438</button><button type="button" class="vx-inline-link vx-inline-link--button" data-logout>\u0412\u044b\u0439\u0442\u0438</button></div>',
      "</section>",
    ].join("");

    const renewActionHtml =
      renewableSubscriptions.length === 1
        ? '<button type="button" class="vx-button vx-button--ghost" data-checkout="renew" data-subscription-id="' +
          escapeHtml(String(renewableSubscriptions[0].id || "")) +
          '">\u041f\u0440\u043e\u0434\u043b\u0438\u0442\u044c \u00b7 ' +
          escapeHtml(model.card_price_label || "") +
          "</button>"
        : renewableSubscriptions.length > 1
          ? '<button type="button" class="vx-button vx-button--ghost" data-scroll-renew>\u0412\u044b\u0431\u0440\u0430\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f</button>'
          : "";
    const primaryDashboardActionHtml =
      activeImportUrl
        ? '<a class="vx-button vx-button--primary" href="' +
          escapeHtml(activeImportUrl) +
          '" target="_top" rel="noopener">\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0438\u0442\u044c</a>'
        : activeSubscription && activeSubscription.config_url
          ? '<button type="button" class="vx-button vx-button--primary" data-nav="' +
            escapeHtml(activeSubscription.config_url) +
            '">QR \u0438 \u0434\u043e\u0441\u0442\u0443\u043f</button>'
        : subscriptions.length === 0 && trialButtonHtml
          ? trialButtonHtml
        : '<button type="button" class="vx-button vx-button--primary" data-checkout="buy">\u041a\u0443\u043f\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f \u00b7 ' +
          escapeHtml(model.card_price_label || "") +
          "</button>";
    const buyMoreActionHtml =
      activeSubscription && activeSubscription.config_url
        ? '<button type="button" class="vx-button vx-button--ghost" data-checkout="buy">\u041a\u0443\u043f\u0438\u0442\u044c \u0435\u0449\u0435 \u00b7 ' +
          escapeHtml(model.card_price_label || "") +
          "</button>"
        : "";
    const emptyPrimaryActionHtml =
      trialButtonHtml ||
      '<button type="button" class="vx-button vx-button--primary" data-checkout="buy">\u041a\u0443\u043f\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f</button>';
    const emptySecondaryBuyHtml = trialButtonHtml
      ? '<button type="button" class="vx-button vx-button--ghost" data-checkout="buy">\u041a\u0443\u043f\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f</button>'
      : "";
    const paymentState = model && model.payment && model.payment.pending ? model.payment : null;
    const paymentRecoveryHtml = paymentState
      ? '<section class="vx-section-card vx-payment-recovery"><div class="vx-dashboard-help__copy"><strong>\u041e\u043f\u043b\u0430\u0442\u0430 \u043f\u0440\u043e\u0448\u043b\u0430</strong><span>' +
        escapeHtml(paymentState.message || "\u0413\u043e\u0442\u043e\u0432\u0438\u043c \u0434\u043e\u0441\u0442\u0443\u043f, \u0441\u043f\u0438\u0441\u043e\u043a \u043e\u0431\u043d\u043e\u0432\u0438\u0442\u0441\u044f \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438.") +
        "</span></div></section>"
      : "";
    if (paymentState) {
      state.paymentPollTimer = window.setTimeout(function () {
        loadCurrentView();
      }, Number(paymentState.poll_ms || 2500));
    }

    const cardsHtml = subscriptions.length
      ? subscriptions
          .map(function (sub) {
            const autoImportUrl = sub && sub.auto_import_url ? String(sub.auto_import_url) : "";
            return [
              '<article class="vx-config-card">',
              '<div class="vx-config-card__head">',
              '<div class="vx-config-card__header-main">',
              '<div class="vx-config-card__title-row"><div class="vx-config-card__name-group"><h3 class="vx-config-card__title"><span>' +
                escapeHtml(sub.display_name) +
                '</span></h3></div><span class="' + pillClass(!!sub.is_active) + '">' + escapeHtml(sub.status_text) + "</span></div>",
              "</div>",
              "</div>",
              '<div class="vx-config-card__meta vx-config-card__meta--single">',
              '<div class="vx-config-meta"><span>\u0414\u043e</span><strong>' + escapeHtml(sub.expires_at || "\u2014") + "</strong></div>",
              "</div>",
              '<div class="vx-config-card__actions">' +
                (autoImportUrl
                  ? '<a class="vx-button vx-button--primary" href="' +
                    escapeHtml(autoImportUrl) +
                    '" target="_top" rel="noopener">\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0438\u0442\u044c</a><button type="button" class="vx-button vx-button--ghost" data-nav="' +
                    escapeHtml(sub.config_url) +
                    '">QR \u0438 \u0434\u043e\u0441\u0442\u0443\u043f</button>'
                  : '<button type="button" class="vx-button vx-button--primary" data-nav="' +
                    escapeHtml(sub.config_url) +
                    '">QR \u0438 \u0434\u043e\u0441\u0442\u0443\u043f</button>') +
                (sub.can_renew
                  ? '<button type="button" class="vx-button vx-button--ghost" data-checkout="renew" data-subscription-id="' +
                    escapeHtml(String(sub.id)) +
                    '">\u041f\u0440\u043e\u0434\u043b\u0438\u0442\u044c</button>'
                  : "") +
                "</div>",
              "</article>",
            ].join("");
          })
          .join("")
      : '<div class="vx-account-empty vx-account-empty--dashboard"><div class="vx-account-empty__badge">\u0411\u0435\u0437 \u043a\u0430\u0440\u0442\u044b \u00b7 7 \u0434\u043d\u0435\u0439</div><strong>\u041d\u0430\u0447\u043d\u0438\u0442\u0435 \u0441 \u043f\u0440\u043e\u0431\u043d\u043e\u0433\u043e \u0434\u043e\u0441\u0442\u0443\u043f\u0430</strong><span>\u041e\u0442\u043a\u0440\u043e\u0435\u0442\u0441\u044f \u0431\u043e\u0442 VXcloud. \u041f\u043e\u0441\u043b\u0435 \u0430\u043a\u0442\u0438\u0432\u0430\u0446\u0438\u0438 \u0432\u0435\u0440\u043d\u0438\u0442\u0435\u0441\u044c \u0441\u044e\u0434\u0430 \u0437\u0430 QR \u0438 \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u0435\u0439.</span><div class="vx-account-empty__actions">' +
        emptyPrimaryActionHtml +
        emptySecondaryBuyHtml +
        '<button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(accountRouteUrl({ view: "instructions" })) +
        '">\u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f</button></div></div>';

    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell">',
      '<section class="vx-account-hero">',
      '<div class="vx-account-hero__head">',
      '<div><h1 class="vx-account-title">' +
        escapeHtml(dashboardTitle) +
        '</h1><p class="vx-account-subtitle">' +
        escapeHtml(dashboardSubtitle) +
        "</p></div>",
      heroMetricsHtml,
      "</div>",
      '<div class="vx-account-actions">',
      primaryDashboardActionHtml,
      renewActionHtml,
      buyMoreActionHtml,
      "</div>",
      "</section>",
      paymentRecoveryHtml,
      '<section class="vx-section-card"><div class="vx-section-card__head"><h2>\u0412\u0430\u0448\u0438 \u0434\u043e\u0441\u0442\u0443\u043f\u044b</h2><span>\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0445: ' +
        escapeHtml(String(activeCount)) +
        ' \u00b7 \u041d\u0435\u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445: ' +
        escapeHtml(String(inactiveCount)) +
        '</span></div><div class="vx-config-list">' +
        cardsHtml +
        "</div></section>",
      '<section class="vx-dashboard-help"><div class="vx-dashboard-help__copy"><strong>\u041d\u0443\u0436\u043d\u0430 \u043f\u043e\u043c\u043e\u0449\u044c?</strong><span>\u041a\u043e\u0440\u043e\u0442\u043a\u0430\u044f \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f \u0438 \u0447\u0430\u0442 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0438 \u0432\u043d\u0443\u0442\u0440\u0438 \u043a\u0430\u0431\u0438\u043d\u0435\u0442\u0430.</span></div><div class="vx-dashboard-help__actions"><button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(accountRouteUrl({ view: "instructions" })) +
        '">\u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f</button><button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(accountRouteUrl({ view: "support" })) +
        '">\u041f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430</button></div></section>',
      accountIdentityHtml,
      "</section>",
    ].join("");
  }

  function renderSettings(model) {
    const profile = (model && model.user) || {};

    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell vx-account-app__shell--settings">',
      '<section class="vx-section-card vx-settings-card"><div class="vx-section-card__head"><h1>\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430</h1><span>\u041b\u043e\u0433\u0438\u043d \u0438 email \u0434\u043b\u044f \u0432\u0445\u043e\u0434\u0430 \u0432 \u043a\u0430\u0431\u0438\u043d\u0435\u0442.</span></div>',
      '<div class="vx-settings-body">',
      '<div class="vx-settings-note"><strong>\u0427\u0442\u043e \u043c\u0435\u043d\u044f\u0435\u0442\u0441\u044f</strong><span>\u042d\u0442\u0438 \u0434\u0430\u043d\u043d\u044b\u0435 \u043d\u0443\u0436\u043d\u044b \u0434\u043b\u044f \u0432\u0445\u043e\u0434\u0430. \u0414\u043e\u0441\u0442\u0443\u043f\u044b, QR \u0438 \u0441\u0441\u044b\u043b\u043a\u0438 \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0438 \u043e\u0442 \u044d\u0442\u043e\u0433\u043e \u043d\u0435 \u043c\u0435\u043d\u044f\u044e\u0442\u0441\u044f.</span></div>',
      '<form class="vx-profile-form" data-profile-form>',
      '<section class="vx-profile-group"><div class="vx-profile-group__head"><strong>\u0412\u0445\u043e\u0434</strong><span>\u041b\u043e\u0433\u0438\u043d \u0438 email \u0434\u043b\u044f \u0432\u0445\u043e\u0434\u0430 \u0432 \u043a\u0430\u0431\u0438\u043d\u0435\u0442.</span></div>',
      '<div class="vx-profile-grid">',
      '<label class="vx-profile-field"><span>\u041b\u043e\u0433\u0438\u043d</span><input type="text" name="username" maxlength="150" required value="' + escapeHtml(profile.username || "") + '"></label>',
      '<label class="vx-profile-field"><span>Email</span><input type="email" name="email" maxlength="254" required value="' + escapeHtml(profile.email || "") + '"></label>',
      "</div></section>",
      '<section class="vx-profile-group"><div class="vx-profile-group__head"><strong>\u0418\u043c\u044f \u0432 \u043a\u0430\u0431\u0438\u043d\u0435\u0442\u0435</strong><span>\u041e\u043f\u0446\u0438\u043e\u043d\u0430\u043b\u044c\u043d\u043e. \u041d\u0430 VPN \u0434\u043e\u0441\u0442\u0443\u043f\u044b \u044d\u0442\u043e \u043d\u0435 \u0432\u043b\u0438\u044f\u0435\u0442.</span></div>',
      '<div class="vx-profile-grid">',
      '<label class="vx-profile-field"><span>\u0418\u043c\u044f</span><input type="text" name="first_name" maxlength="150" value="' + escapeHtml(profile.first_name || "") + '"></label>',
      '<label class="vx-profile-field"><span>\u0424\u0430\u043c\u0438\u043b\u0438\u044f</span><input type="text" name="last_name" maxlength="150" value="' + escapeHtml(profile.last_name || "") + '"></label>',
      "</div></section>",
      '<div class="vx-profile-actions"><button type="submit" class="vx-button vx-button--primary">\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u0434\u0430\u043d\u043d\u044b\u0435</button></div>',
      '<div class="vx-auth-errors vx-profile-errors" data-profile-errors style="display:none"></div>',
      "</form>",
      '<div class="vx-account-actions vx-account-actions--settings"><button type="button" class="vx-button vx-button--ghost" data-nav="' + escapeHtml((model.urls && model.urls.dashboard) || (cfg.accountUrl || "/account/")) + '">\u041c\u043e\u0439 VPN</button><button type="button" class="vx-button vx-button--ghost" data-logout>\u0412\u044b\u0439\u0442\u0438</button></div>',
      "</div>",
      "</section>",
      "</section>",
    ].join("");
  }

  function renderLegacyLink(model) {
    const hasBotLink = !!(model && model.deep_link);
    const linkedBlock =
      model && model.linked && model.linked_telegram_id
        ? '<div class="vx-status-banner is-success">Сейчас привязан Telegram ID: <code>' + escapeHtml(String(model.linked_telegram_id)) + "</code></div>"
        : "";
    const primaryAction = hasBotLink
      ? '<a class="vx-button vx-button--primary vx-button--block" href="' +
        escapeHtml(model.deep_link || "") +
        '" data-telegram-link="' +
        escapeHtml(model.deep_link || "") +
        '" target="_blank" rel="noopener">Открыть бота и привязать</a>'
      : '<div class="vx-account-empty">Не удалось открыть кнопку Telegram. Скопируйте код привязки и отправьте его боту VXcloud.</div>';
    const helperText = hasBotLink
      ? '<p class="vx-field-hint">Если кнопка не открылась, скопируйте код ниже и отправьте его боту VXcloud.</p>'
      : "";

    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell vx-account-app__shell--link">',
      '<section class="vx-section-card vx-link-card">',
      '<div class="vx-section-card__head"><h1>' + escapeHtml((model && model.title) || "Привязка Telegram") + '</h1><span>' + escapeHtml((model && model.subtitle) || "") + "</span></div>",
      '<div class="vx-link-body">',
      linkedBlock,
      '<div class="vx-field-card"><label>Код привязки</label><div class="vx-link-code"><code>' +
        escapeHtml((model && model.link_code) || "") +
        '</code><button type="button" class="vx-icon-button" data-copy-text="link_' +
        escapeHtml((model && model.link_code) || "") +
        '" data-copy-toast="Код скопирован" aria-label="Скопировать код привязки">' +
        iconSvg("copy") +
        '</button></div><p class="vx-field-hint">Код действует до: ' +
        escapeHtml((model && model.expires_at) || "—") +
        "</p></div>",
      primaryAction,
      helperText,
      '<div class="vx-account-actions vx-account-actions--footer"><button type="button" class="vx-button vx-button--ghost" data-link-regenerate>Новый код</button><button type="button" class="vx-button vx-button--ghost" data-nav="' + escapeHtml((model && model.dashboard_url) || (cfg.accountUrl || "/account/")) + '">Мой VPN</button></div>',
      "</div>",
      "</section>",
      "</section>",
    ].join("");
  }

  function renderLink(model) {
    const linkCode = (model && model.link_code) || "";
    const expiresAt = (model && model.expires_at) || "\u2014";
    const hasBotLink = !!(model && model.deep_link);
    const linkedBlock =
      model && model.linked && model.linked_telegram_id
        ? '<div class="vx-status-banner is-success">\u0421\u0435\u0439\u0447\u0430\u0441 \u043f\u0440\u0438\u0432\u044f\u0437\u0430\u043d Telegram ID: <code>' +
          escapeHtml(String(model.linked_telegram_id)) +
          "</code></div>"
        : "";
    const primaryAction = hasBotLink
      ? '<a class="vx-button vx-button--primary vx-button--block" href="' +
        escapeHtml(model.deep_link || "") +
        '" data-telegram-link="' +
        escapeHtml(model.deep_link || "") +
        '" target="_blank" rel="noopener">\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0431\u043e\u0442\u0430 \u0438 \u043f\u0440\u0438\u0432\u044f\u0437\u0430\u0442\u044c</a>'
      : '<div class="vx-account-empty">\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u043a\u043d\u043e\u043f\u043a\u0443 Telegram. \u0421\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u043a\u043e\u0434 \u043f\u0440\u0438\u0432\u044f\u0437\u043a\u0438 \u0438 \u043e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0435\u0433\u043e \u0431\u043e\u0442\u0443 VXcloud.</div>';
    const helperText = hasBotLink
      ? '<p class="vx-field-hint">\u0415\u0441\u043b\u0438 \u043a\u043d\u043e\u043f\u043a\u0430 \u043d\u0435 \u043e\u0442\u043a\u0440\u044b\u043b\u0430\u0441\u044c, \u0441\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u043a\u043e\u0434 \u043d\u0438\u0436\u0435 \u0438 \u043e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0435\u0433\u043e \u0431\u043e\u0442\u0443 VXcloud.</p>'
      : "";

    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell vx-account-app__shell--link">',
      '<section class="vx-section-card vx-link-card">',
      '<div class="vx-section-card__head"><h1>' +
        escapeHtml((model && model.title) || "\u041f\u0440\u0438\u0432\u044f\u0437\u043a\u0430 Telegram") +
        '</h1><span>' +
        escapeHtml(
          (model && model.subtitle) ||
            "\u041f\u0440\u0438\u0432\u044f\u0436\u0438\u0442\u0435 Telegram, \u0447\u0442\u043e\u0431\u044b \u0431\u043e\u0442 \u0432\u0438\u0434\u0435\u043b \u0432\u0430\u0448\u0438 \u0434\u043e\u0441\u0442\u0443\u043f\u044b \u0438 \u043e\u043f\u043b\u0430\u0442\u044b."
        ) +
        "</span></div>",
      '<div class="vx-link-body">',
      linkedBlock,
      '<div class="vx-field-card"><label>\u041a\u043e\u0434 \u043f\u0440\u0438\u0432\u044f\u0437\u043a\u0438</label><div class="vx-link-code"><code>' +
        escapeHtml(linkCode) +
        '</code><button type="button" class="vx-icon-button" data-copy-text="link_' +
        escapeHtml(linkCode) +
        '" data-copy-toast="\u041a\u043e\u0434 \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d" aria-label="\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u043a\u043e\u0434 \u043f\u0440\u0438\u0432\u044f\u0437\u043a\u0438">' +
        iconSvg("copy") +
        '</button></div><p class="vx-field-hint">\u041a\u043e\u0434 \u0434\u0435\u0439\u0441\u0442\u0432\u0443\u0435\u0442 \u0434\u043e: ' +
        escapeHtml(expiresAt) +
        "</p></div>",
      primaryAction,
      helperText,
      '<div class="vx-account-actions vx-account-actions--footer"><button type="button" class="vx-button vx-button--ghost" data-link-regenerate>\u041d\u043e\u0432\u044b\u0439 \u043a\u043e\u0434</button><button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml((model && model.dashboard_url) || (cfg.accountUrl || "/account/")) +
        '">\u041c\u043e\u0439 VPN</button></div>',
      "</div>",
      "</section>",
      "</section>",
    ].join("");
  }

  function renderLegacyConfig(model) {
    const switchHtml = Array.isArray(model.subscriptions)
      ? model.subscriptions
          .map(function (item) {
            return '<option value="' + escapeHtml(item.url) + '"' + (item.selected ? " selected" : "") + ">" + escapeHtml(item.label) + "</option>";
          })
          .join("")
      : "";
    const dashboardUrl = model.dashboard_url || cfg.accountUrl || "/account/";
    const copyText = model.copy_text || "";
    const autoImportUrl = model.auto_import_url || "";
    const guideUrl = accountRouteUrl({ view: "instructions" });
    const renewButtonHtml = model.can_renew
      ? '<button type="button" class="vx-button vx-button--ghost" data-checkout="renew" data-subscription-id="' +
        escapeHtml(String(model.id || "")) +
        '">Продлить</button>'
      : "";
    const deleteButtonHtml = model.can_delete
      ? '<div class="vx-field-card vx-field-card--danger"><label>Удаление</label><p class="vx-field-hint">Удалить можно только неактивный доступ. Действующие QR и ссылки пропадут.</p><button type="button" class="vx-button vx-button--danger" data-delete-subscription="' +
        escapeHtml(String(model.id || "")) +
        '">Удалить доступ</button></div>'
      : "";

    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell vx-account-app__shell--config">',
      '<section class="vx-config-view">',
      '<div class="vx-config-view__main">',
      '<div class="vx-config-view__head">',
      '<div><h1 class="vx-account-title">QR и доступ</h1><p class="vx-account-subtitle vx-account-subtitle--config-name"><span>' +
        escapeHtml(model.display_name || "") +
        "</span></p></div>",
      '<span class="' + pillClass(!!model.is_active) + '">' + escapeHtml(model.status_text || "") + "</span>",
      "</div>",
      '<div class="vx-config-qr"><img src="' +
        escapeHtml(model.qr_image_data_url || "") +
        '" alt="QR доступа"><span class="vx-config-qr__hint">Сканируйте QR в VPN клиенте</span></div>',
      '<div class="vx-config-view__actions">',
      autoImportUrl
        ? '<a class="vx-button vx-button--primary" href="' +
          escapeHtml(autoImportUrl) +
          '" target="_top" rel="noopener">Подключить</a><button type="button" class="vx-button vx-button--ghost" data-copy-text="' +
          escapeHtml(copyText) +
          '">Скопировать ссылку</button>'
        : '<button type="button" class="vx-button vx-button--primary" data-copy-text="' +
          escapeHtml(copyText) +
          '">Скопировать ссылку</button>',
      renewButtonHtml,
      '<button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(dashboardUrl) +
        '">Мой VPN</button>',
      "</div>",
      '<div class="vx-config-quick-guide"><strong>Подключение</strong><div class="vx-config-quick-guide__steps"><span>Откройте VPN клиент</span><span>Сканируйте QR или скопируйте ссылку</span><span>Нужны шаги? Откройте инструкцию</span></div><button type="button" class="vx-inline-link vx-inline-link--button" data-nav="' +
        escapeHtml(guideUrl) +
        '">Открыть инструкцию</button></div>',
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
        ? '<div class="vx-field-card"><label for="vx-config-switch">Все доступы</label><select id="vx-config-switch" class="vx-select">' +
          switchHtml +
          "</select></div>"
        : ""),
      '<div class="vx-field-card"><label>Ссылка подписки</label><div class="vx-copy-row"><input type="text" readonly value="' +
        escapeHtml(copyText) +
        '"><button type="button" class="vx-icon-button" data-copy-text="' +
        escapeHtml(copyText) +
        '" aria-label="Скопировать ссылку">' +
        iconSvg("copy") +
        '</button></div><p class="vx-field-hint">Скопируйте ссылку и импортируйте ее в клиент VPN.</p></div>',
      '<div class="vx-field-card"><div class="vx-field-card__head"><label>Название доступа</label></div><div class="vx-field-value-row"><div class="vx-field-value">' +
        escapeHtml(model.display_name || "") +
        '</div><button type="button" class="vx-title-edit" data-rename-toggle data-target="rename-config-' +
        escapeHtml(String(model.id || "")) +
        '" aria-expanded="false" aria-label="Переименовать">' +
        iconSvg("rename") +
        '</button></div><form id="rename-config-' +
        escapeHtml(String(model.id || "")) +
        '" class="vx-rename-panel" data-rename-form data-subscription-id="' +
        escapeHtml(String(model.id || "")) +
        '" hidden><div class="vx-rename-row"><input type="text" class="vx-rename-input" name="display_name" maxlength="80" placeholder="Название доступа" value="' +
        escapeHtml(model.display_name || "") +
        '"><button type="submit" class="vx-button vx-button--ghost vx-button--compact">Сохранить</button></div></form><p class="vx-field-hint">Измените название, чтобы проще различать доступы в кабинете.</p></div>',
      deleteButtonHtml,
      "</aside>",
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
    const dashboardUrl = model.dashboard_url || cfg.accountUrl || "/account/";
    const copyText = model.copy_text || "";
    const autoImportUrl = model.auto_import_url || "";
    const guideUrl = accountRouteUrl({ view: "instructions" });
    const renewButtonHtml = model.can_renew
      ? '<button type="button" class="vx-button vx-button--ghost" data-checkout="renew" data-subscription-id="' +
        escapeHtml(String(model.id || "")) +
        '">\u041f\u0440\u043e\u0434\u043b\u0438\u0442\u044c</button>'
      : "";
    const deleteButtonHtml = model.can_delete
      ? '<div class="vx-field-card vx-field-card--danger"><label>\u0423\u0434\u0430\u043b\u0435\u043d\u0438\u0435</label><p class="vx-field-hint">\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u043c\u043e\u0436\u043d\u043e \u0442\u043e\u043b\u044c\u043a\u043e \u043d\u0435\u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0439 \u0434\u043e\u0441\u0442\u0443\u043f. \u0414\u0435\u0439\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0435 QR \u0438 \u0441\u0441\u044b\u043b\u043a\u0438 \u043f\u0440\u043e\u043f\u0430\u0434\u0443\u0442.</p><button type="button" class="vx-button vx-button--danger" data-delete-subscription="' +
        escapeHtml(String(model.id || "")) +
        '">\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f</button></div>'
      : "";

    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell vx-account-app__shell--config">',
      '<section class="vx-config-view">',
      '<div class="vx-config-view__main">',
      '<div class="vx-config-view__head">',
      '<div><h1 class="vx-account-title">\u0414\u043e\u0441\u0442\u0443\u043f</h1><p class="vx-account-subtitle vx-account-subtitle--config-name"><span>' +
        escapeHtml(model.display_name || "") +
        "</span></p></div>",
      '<span class="' + pillClass(!!model.is_active) + '">' + escapeHtml(model.status_text || "") + "</span>",
      "</div>",
      '<div class="vx-config-qr"><img src="' +
        escapeHtml(model.qr_image_data_url || "") +
        '" alt="QR \u0434\u043e\u0441\u0442\u0443\u043f\u0430"><span class="vx-config-qr__hint">QR \u2014 \u0437\u0430\u043f\u0430\u0441\u043d\u043e\u0439 \u0441\u043f\u043e\u0441\u043e\u0431, \u0435\u0441\u043b\u0438 \u0443\u0434\u043e\u0431\u043d\u0435\u0435 \u0441\u043a\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u0442\u044c.</span></div>',
      '<div class="vx-config-view__actions">',
      autoImportUrl
        ? '<a class="vx-button vx-button--primary" href="' +
          escapeHtml(autoImportUrl) +
          '" target="_top" rel="noopener">\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0438\u0442\u044c</a><button type="button" class="vx-button vx-button--ghost" data-copy-text="' +
          escapeHtml(copyText) +
          '">\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443</button>'
        : '<button type="button" class="vx-button vx-button--primary" data-copy-text="' +
          escapeHtml(copyText) +
          '">\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443</button>',
      renewButtonHtml,
      '<button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(dashboardUrl) +
        '">\u041c\u043e\u0439 VPN</button>',
      "</div>",
      '<div class="vx-config-quick-guide"><strong>\u0411\u044b\u0441\u0442\u0440\u043e\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435</strong><div class="vx-config-quick-guide__steps"><span>\u0421\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443 \u043a\u043d\u043e\u043f\u043a\u043e\u0439 \u0432\u044b\u0448\u0435</span><span>\u041e\u0442\u043a\u0440\u043e\u0439\u0442\u0435 Streisand, V2Box \u0438\u043b\u0438 v2rayNG</span><span>\u041d\u0430\u0436\u043c\u0438\u0442\u0435 «+» \u0438 \u0438\u043c\u043f\u043e\u0440\u0442 \u0438\u0437 \u0431\u0443\u0444\u0435\u0440\u0430</span></div><button type="button" class="vx-inline-link vx-inline-link--button" data-nav="' +
        escapeHtml(guideUrl) +
        '">\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044e</button></div>',
      "</div>",
      '<aside class="vx-config-view__side">',
      '<div class="vx-config-info-grid">',
      '<article class="vx-info-card"><div class="vx-stat-label">\u0421\u0442\u0430\u0442\u0443\u0441</div><div class="vx-stat-value"><span class="' +
        pillClass(!!model.is_active) +
        '">' +
        escapeHtml(model.status_text || "") +
        "</span></div></article>",
      '<article class="vx-info-card"><div class="vx-stat-label">\u0414\u0435\u0439\u0441\u0442\u0432\u0443\u0435\u0442 \u0434\u043e</div><div class="vx-stat-value">' +
        escapeHtml(model.expires_at || "\u2014") +
        "</div></article>",
      '<article class="vx-info-card vx-info-card--wide"><div class="vx-stat-label">ID \u043a\u043b\u0438\u0435\u043d\u0442\u0430</div><div class="vx-stat-value">' +
        (model.client_code ? '<code class="vx-stat-code">' + escapeHtml(model.client_code) + "</code>" : "\u2014") +
        "</div></article>",
      "</div>",
      switchHtml
        ? '<div class="vx-field-card"><label for="vx-config-switch">\u0412\u0441\u0435 \u0434\u043e\u0441\u0442\u0443\u043f\u044b</label><select id="vx-config-switch" class="vx-select">' +
          switchHtml +
          "</select></div>"
        : "",
      '<div class="vx-field-card"><label>\u0421\u0441\u044b\u043b\u043a\u0430 \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0438</label><div class="vx-copy-row"><input type="text" readonly value="' +
        escapeHtml(copyText) +
        '"><button type="button" class="vx-icon-button" data-copy-text="' +
        escapeHtml(copyText) +
        '" aria-label="\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443">' +
        iconSvg("copy") +
        '</button></div><p class="vx-field-hint">\u0421\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443 \u0438 \u0438\u043c\u043f\u043e\u0440\u0442\u0438\u0440\u0443\u0439\u0442\u0435 \u0435\u0435 \u0432 \u043a\u043b\u0438\u0435\u043d\u0442 VPN.</p></div>',
      '<div class="vx-field-card"><div class="vx-field-card__head"><label>\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u0434\u043e\u0441\u0442\u0443\u043f\u0430</label></div><div class="vx-field-value-row"><div class="vx-field-value">' +
        escapeHtml(model.display_name || "") +
        '</div><button type="button" class="vx-title-edit" data-rename-toggle data-target="rename-config-' +
        escapeHtml(String(model.id || "")) +
        '" aria-expanded="false" aria-label="\u041f\u0435\u0440\u0435\u0438\u043c\u0435\u043d\u043e\u0432\u0430\u0442\u044c">' +
        iconSvg("rename") +
        '</button></div><form id="rename-config-' +
        escapeHtml(String(model.id || "")) +
        '" class="vx-rename-panel" data-rename-form data-subscription-id="' +
        escapeHtml(String(model.id || "")) +
        '" hidden><div class="vx-rename-row"><input type="text" class="vx-rename-input" name="display_name" maxlength="80" placeholder="\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u0434\u043e\u0441\u0442\u0443\u043f\u0430" value="' +
        escapeHtml(model.display_name || "") +
        '"><button type="submit" class="vx-button vx-button--ghost vx-button--compact">\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c</button></div></form><p class="vx-field-hint">\u0418\u0437\u043c\u0435\u043d\u0438\u0442\u0435 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435, \u0447\u0442\u043e\u0431\u044b \u043f\u0440\u043e\u0449\u0435 \u0440\u0430\u0437\u043b\u0438\u0447\u0430\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f\u044b \u0432 \u043a\u0430\u0431\u0438\u043d\u0435\u0442\u0435.</p></div>',
      deleteButtonHtml,
      "</aside>",
      "</section>",
      "</section>",
    ].join("");
  }

  function renderLegacyInstructions(model) {
    const selected = String((model && model.device) || "");
    const deviceCopy = {
      iphone: {
        title: "iPhone",
        app: "V2Box \u0438\u043b\u0438 Streisand",
        text: "\u0412 Streisand \u0438\u043b\u0438 V2Box \u043d\u0430\u0436\u043c\u0438\u0442\u0435 «+» \u0438 \u0432\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0438\u043c\u043f\u043e\u0440\u0442 \u0438\u0437 \u0431\u0443\u0444\u0435\u0440\u0430.",
      },
      android: {
        title: "Android",
        app: "v2rayNG",
        text: "\u0412 v2rayNG \u043d\u0430\u0436\u043c\u0438\u0442\u0435 «+», \u0437\u0430\u0442\u0435\u043c \u0438\u043c\u043f\u043e\u0440\u0442 \u0438\u0437 \u0431\u0443\u0444\u0435\u0440\u0430 \u0438\u043b\u0438 QR.",
      },
      desktop: {
        title: "Windows/macOS",
        app: "Hiddify \u0438\u043b\u0438 Nekoray",
        text: "\u0412 Hiddify \u0438\u043b\u0438 Nekoray \u0434\u043e\u0431\u0430\u0432\u044c\u0442\u0435 \u043f\u0440\u043e\u0444\u0438\u043b\u044c \u0438\u0437 \u0431\u0443\u0444\u0435\u0440\u0430, \u043f\u043e\u0442\u043e\u043c \u0432\u043a\u043b\u044e\u0447\u0438\u0442\u0435 VPN.",
      },
    };
    const current = deviceCopy[selected] || {
      title: "\u0411\u044b\u0441\u0442\u0440\u043e",
      app: "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u043e",
      text: "\u0421\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443, \u043e\u0442\u043a\u0440\u043e\u0439\u0442\u0435 VPN-\u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u0438 \u0438\u043c\u043f\u043e\u0440\u0442\u0438\u0440\u0443\u0439\u0442\u0435 \u0435\u0435 \u0438\u0437 \u0431\u0443\u0444\u0435\u0440\u0430.",
    };
    const deviceButtons = [
      { key: "iphone", label: "iPhone" },
      { key: "android", label: "Android" },
      { key: "desktop", label: "Windows/macOS" },
    ]
      .map(function (device) {
        const classes = "vx-device-tab" + (device.key === selected ? " is-active" : "");
        return (
          '<button type="button" class="' +
          classes +
          '" data-nav="' +
          escapeHtml(accountRouteUrl({ view: "instructions", device: device.key })) +
          '">' +
          escapeHtml(device.label) +
          "</button>"
        );
      })
      .join("");
    const primarySub = (model && model.primary_subscription) || null;
    const hasAccess = !!(primarySub && primarySub.config_url);
    const trialUrl = String(cfg.telegramTrialUrl || cfg.telegramBotUrl || cfg.supportTelegramUrl || "").trim();
    const accessHintHtml = hasAccess
      ? '<div class="vx-guide-access"><span>Ваш доступ</span><strong>' +
        escapeHtml(primarySub.display_name || "Мой VPN") +
        '</strong><small>' +
        escapeHtml(primarySub.expires_at ? "действует до " + primarySub.expires_at : "откройте QR или ссылку подписки") +
        "</small></div>"
      : '<div class="vx-guide-access is-empty"><span>Доступ</span><strong>Пока нет активного доступа</strong><small>Сначала активируйте пробный период или купите доступ.</small></div>';
    const primaryAccessButton = hasAccess
      ? '<button type="button" class="vx-button vx-button--primary" data-nav="' +
        escapeHtml(primarySub.config_url) +
        '">Открыть QR и доступ</button>'
      : trialUrl
        ? '<a class="vx-button vx-button--primary" href="' +
          escapeHtml(trialUrl) +
          '" data-telegram-link="' +
          escapeHtml(trialUrl) +
          '" target="_blank" rel="noopener">🎁 7 дней бесплатно</a>'
        : '<button type="button" class="vx-button vx-button--primary" data-nav="' +
        escapeHtml(normalizePath(cfg.accountPath || "/account/")) +
        '">Мой VPN</button>';

    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell vx-account-app__shell--instructions">',
      '<section class="vx-section-card vx-instructions-card">',
      '<div class="vx-section-card__head"><h1>' +
        escapeHtml((model && model.title) || "\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435") +
        '</h1><span>' +
        escapeHtml((model && model.subtitle) || "\u0421\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443 \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0438 \u0438 \u0438\u043c\u043f\u043e\u0440\u0442\u0438\u0440\u0443\u0439\u0442\u0435 \u0435\u0435 \u0432 VPN-\u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435.") +
        "</span></div>",
      '<div class="vx-instructions-body">',
      accessHintHtml,
      '<div class="vx-device-tabs">' + deviceButtons + "</div>",
      '<article class="vx-guide-panel"><div class="vx-guide-panel__head"><div><h2>' +
        escapeHtml(current.title) +
        '</h2><p>' +
        escapeHtml(current.app) +
        "</p></div></div>",
      '<ol class="vx-guide-steps vx-guide-steps--cards"><li><strong>\u0421\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443</strong><span>\u041d\u0430\u0436\u043c\u0438\u0442\u0435 \u043a\u043d\u043e\u043f\u043a\u0443 \u0432\u044b\u0448\u0435. QR \u043d\u0443\u0436\u0435\u043d \u0442\u043e\u043b\u044c\u043a\u043e, \u0435\u0441\u043b\u0438 \u0443\u0434\u043e\u0431\u043d\u0435\u0435 \u0441\u043a\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u0442\u044c.</span></li><li><strong>\u041e\u0442\u043a\u0440\u043e\u0439\u0442\u0435 VPN-\u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435</strong><span>' +
        escapeHtml(current.app) +
        '</span></li><li><strong>\u0418\u043c\u043f\u043e\u0440\u0442</strong><span>' +
        escapeHtml(current.text) +
        "</span></li></ol>",
      '<div class="vx-account-actions vx-account-actions--instructions">' +
        primaryAccessButton +
        '<button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(accountRouteUrl({ view: "support" })) +
        '">Помощь</button><button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(normalizePath(cfg.accountPath || "/account/")) +
        '">Мой VPN</button></div>',
      "</article>",
      "</div>",
      "</section>",
      "</section>",
    ].join("");
  }

  function renderInstructions(model) {
    const selected = String((model && model.device) || "");
    const deviceCopy = {
      iphone: {
        title: "iPhone",
        app: "V2Box \u0438\u043b\u0438 Streisand",
        text: "\u0412 Streisand \u0438\u043b\u0438 V2Box \u043d\u0430\u0436\u043c\u0438\u0442\u0435 «+» \u0438 \u0432\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0438\u043c\u043f\u043e\u0440\u0442 \u0438\u0437 \u0431\u0443\u0444\u0435\u0440\u0430.",
      },
      android: {
        title: "Android",
        app: "v2rayNG",
        text: "\u0412 v2rayNG \u043d\u0430\u0436\u043c\u0438\u0442\u0435 «+», \u0437\u0430\u0442\u0435\u043c \u0438\u043c\u043f\u043e\u0440\u0442 \u0438\u0437 \u0431\u0443\u0444\u0435\u0440\u0430 \u0438\u043b\u0438 QR.",
      },
      desktop: {
        title: "Windows/macOS",
        app: "Hiddify \u0438\u043b\u0438 Nekoray",
        text: "\u0412 Hiddify \u0438\u043b\u0438 Nekoray \u0434\u043e\u0431\u0430\u0432\u044c\u0442\u0435 \u043f\u0440\u043e\u0444\u0438\u043b\u044c \u0438\u0437 \u0431\u0443\u0444\u0435\u0440\u0430, \u043f\u043e\u0442\u043e\u043c \u0432\u043a\u043b\u044e\u0447\u0438\u0442\u0435 VPN.",
      },
    };
    const current = deviceCopy[selected] || {
      title: "\u0411\u044b\u0441\u0442\u0440\u043e",
      app: "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u043e",
      text: "\u0421\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443, \u043e\u0442\u043a\u0440\u043e\u0439\u0442\u0435 VPN-\u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u0438 \u0438\u043c\u043f\u043e\u0440\u0442\u0438\u0440\u0443\u0439\u0442\u0435 \u0435\u0435 \u0438\u0437 \u0431\u0443\u0444\u0435\u0440\u0430.",
    };
    const deviceButtons = [
      { key: "iphone", label: "iPhone" },
      { key: "android", label: "Android" },
      { key: "desktop", label: "Windows/macOS" },
    ]
      .map(function (device) {
        const classes = "vx-device-tab" + (device.key === selected ? " is-active" : "");
        return (
          '<button type="button" class="' +
          classes +
          '" data-nav="' +
          escapeHtml(accountRouteUrl({ view: "instructions", device: device.key })) +
          '">' +
          escapeHtml(device.label) +
          "</button>"
        );
      })
      .join("");
    const primarySub = (model && model.primary_subscription) || null;
    const hasAccess = !!(primarySub && primarySub.config_url);
    const accessCopyText = primarySub ? String(primarySub.feed_url || primarySub.vless_url || "") : "";
    const trialUrl = String(cfg.telegramTrialUrl || cfg.telegramBotUrl || cfg.supportTelegramUrl || "").trim();
    const accessHintHtml = hasAccess
      ? '<div class="vx-guide-access"><span>\u0412\u0430\u0448 \u0434\u043e\u0441\u0442\u0443\u043f</span><strong>' +
        escapeHtml(primarySub.display_name || "\u041c\u043e\u0439 VPN") +
        '</strong><small>' +
        escapeHtml(
          primarySub.expires_at
            ? "\u0434\u0435\u0439\u0441\u0442\u0432\u0443\u0435\u0442 \u0434\u043e " + primarySub.expires_at
            : "\u043e\u0442\u043a\u0440\u043e\u0439\u0442\u0435 QR \u0438\u043b\u0438 \u0441\u0441\u044b\u043b\u043a\u0443 \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0438"
        ) +
        "</small></div>"
      : '<div class="vx-guide-access is-empty"><span>\u0414\u043e\u0441\u0442\u0443\u043f</span><strong>\u041f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0430\u043a\u0442\u0438\u0432\u043d\u043e\u0433\u043e \u0434\u043e\u0441\u0442\u0443\u043f\u0430</strong><small>\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0430\u043a\u0442\u0438\u0432\u0438\u0440\u0443\u0439\u0442\u0435 \u043f\u0440\u043e\u0431\u043d\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434 \u0438\u043b\u0438 \u043a\u0443\u043f\u0438\u0442\u0435 \u0434\u043e\u0441\u0442\u0443\u043f.</small></div>';
    const primaryAccessButton = hasAccess
      ? accessCopyText
        ? '<button type="button" class="vx-button vx-button--primary" data-copy-text="' +
          escapeHtml(accessCopyText) +
          '">\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443</button><button type="button" class="vx-button vx-button--ghost" data-nav="' +
          escapeHtml(primarySub.config_url) +
          '">QR \u0438 \u0434\u043e\u0441\u0442\u0443\u043f</button>'
        : '<button type="button" class="vx-button vx-button--primary" data-nav="' +
        escapeHtml(primarySub.config_url) +
        '">QR \u0438 \u0434\u043e\u0441\u0442\u0443\u043f</button>'
      : trialUrl
        ? '<a class="vx-button vx-button--primary" href="' +
          escapeHtml(trialUrl) +
          '" data-telegram-link="' +
          escapeHtml(trialUrl) +
          '" target="_blank" rel="noopener">\ud83c\udf81 7 \u0434\u043d\u0435\u0439 \u0431\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e</a>'
      : '<button type="button" class="vx-button vx-button--primary" data-nav="' +
        escapeHtml(normalizePath(cfg.accountPath || "/account/")) +
        '">\u041c\u043e\u0439 VPN</button>';

    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell vx-account-app__shell--instructions">',
      '<section class="vx-section-card vx-instructions-card">',
      '<div class="vx-section-card__head"><h1>' +
        escapeHtml((model && model.title) || "\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435") +
        '</h1><span>' +
        escapeHtml((model && model.subtitle) || "\u0421\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443 \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0438 \u0438 \u0438\u043c\u043f\u043e\u0440\u0442\u0438\u0440\u0443\u0439\u0442\u0435 \u0435\u0435 \u0432 VPN-\u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435.") +
        "</span></div>",
      '<div class="vx-instructions-body">',
      accessHintHtml,
      '<div class="vx-device-tabs">' + deviceButtons + "</div>",
      '<article class="vx-guide-panel"><div class="vx-guide-panel__head"><div><h2>' +
        escapeHtml(current.title) +
        '</h2><p>' +
        escapeHtml(current.app) +
        "</p></div></div>",
      '<ol class="vx-guide-steps vx-guide-steps--cards"><li><strong>\u0421\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443</strong><span>\u041d\u0430\u0436\u043c\u0438\u0442\u0435 \u043a\u043d\u043e\u043f\u043a\u0443 \u0432\u044b\u0448\u0435. QR \u043d\u0443\u0436\u0435\u043d \u0442\u043e\u043b\u044c\u043a\u043e, \u0435\u0441\u043b\u0438 \u0443\u0434\u043e\u0431\u043d\u0435\u0435 \u0441\u043a\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u0442\u044c.</span></li><li><strong>\u041e\u0442\u043a\u0440\u043e\u0439\u0442\u0435 VPN-\u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435</strong><span>' +
        escapeHtml(current.app) +
        '</span></li><li><strong>\u0418\u043c\u043f\u043e\u0440\u0442</strong><span>' +
        escapeHtml(current.text) +
        "</span></li></ol>",
      '<div class="vx-account-actions vx-account-actions--instructions">' +
        primaryAccessButton +
        '<button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(accountRouteUrl({ view: "support" })) +
        '">\u041f\u043e\u043c\u043e\u0449\u044c</button><button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(normalizePath(cfg.accountPath || "/account/")) +
        '">\u041c\u043e\u0439 VPN</button></div>',
      "</article>",
      "</div>",
      "</section>",
      "</section>",
    ].join("");
  }

  function renderLegacySupport(model) {
    const telegramUrl = (model && model.telegram_url) || "";
    const clientCode = (model && model.client_code) || "";
    const clientCodeHtml = clientCode
      ? '<div class="vx-support-id"><span>ID клиента</span><div class="vx-support-id__row"><code>' +
        escapeHtml(clientCode) +
        '</code><button type="button" class="vx-icon-button" data-copy-text="' +
        escapeHtml(clientCode) +
        '" data-copy-toast="ID скопирован" aria-label="Скопировать ID клиента">' +
        iconSvg("copy") +
        "</button></div></div>"
      : "";
    const supportContactHtml = telegramUrl
      ? '<div class="vx-support-contact"><div class="vx-support-contact__copy"><strong>Написать оператору</strong><span>Откроется Telegram. Скопируйте ID ниже и коротко опишите проблему.</span></div><a class="vx-button vx-button--primary" href="' +
        escapeHtml(telegramUrl) +
        '" data-telegram-link="' +
        escapeHtml(telegramUrl) +
        '" target="_blank" rel="noopener">Написать в поддержку</a></div>'
      : '<div class="vx-support-contact"><div class="vx-support-contact__copy"><strong>Telegram не указан</strong><span>Скопируйте ID и шаблон, затем напишите в поддержку из бота.</span></div></div>';
    const supportIdPrefix = clientCode ? "ID " + clientCode + ". " : "";
    const supportTemplatesHtml = [
      {
        label: "Не подключается",
        text: supportIdPrefix + "Не подключается VPN. Устройство: . Когда началось: .",
      },
      {
        label: "Не открываются сайты",
        text: supportIdPrefix + "Подключение есть, но сайты не открываются. Устройство: . Какой сайт: .",
      },
      {
        label: "Оплата или продление",
        text: supportIdPrefix + "Проблема с оплатой или продлением. Что произошло: .",
      },
    ]
      .map(function (item) {
        return (
          '<button type="button" class="vx-support-template" data-copy-text="' +
          escapeHtml(item.text) +
          '" data-copy-toast="Шаблон скопирован">' +
          escapeHtml(item.label) +
          "</button>"
        );
      })
      .join("");
    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell vx-account-app__shell--support">',
      '<section class="vx-section-card vx-support-card">',
      '<div class="vx-section-card__head"><h1>' +
        escapeHtml((model && model.title) || "\u041f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430") +
        '</h1><span>' +
        escapeHtml((model && model.subtitle) || "\u0415\u0441\u043b\u0438 \u043d\u0443\u0436\u043d\u0430 \u043f\u043e\u043c\u043e\u0449\u044c, \u043d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u0432 Telegram.") +
        "</span></div>",
      '<div class="vx-support-body">',
      supportContactHtml,
      clientCodeHtml,
      '<div class="vx-support-templates"><strong>Быстрый шаблон</strong><span>Скопируйте подходящий текст и отправьте его в Telegram.</span><div class="vx-support-template-list">' +
        supportTemplatesHtml +
        "</div></div>",
      '<div class="vx-support-note"><strong>\u0427\u0442\u043e \u043d\u0430\u043f\u0438\u0441\u0430\u0442\u044c</strong><span>\u041e\u0434\u043d\u0438\u043c \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435\u043c: \u0447\u0442\u043e \u043d\u0435 \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442, \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u043e, \u0438 \u043a\u043e\u0433\u0434\u0430 \u043d\u0430\u0447\u0430\u043b\u0430\u0441\u044c \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u0430.</span></div>',
      '<div class="vx-account-actions vx-account-actions--support">',
      '<button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(accountRouteUrl({ view: "instructions" })) +
        '">Инструкция</button><button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(normalizePath(cfg.accountPath || "/account/")) +
        '">\u041c\u043e\u0439 VPN</button></div>',
      "</div>",
      "</section>",
      "</section>",
    ].join("");
  }

  function renderSupport(model) {
    const telegramUrl = (model && model.telegram_url) || "";
    const clientCode = (model && model.client_code) || "";
    const clientCodeHtml = clientCode
      ? '<div class="vx-support-id"><span>ID \u043a\u043b\u0438\u0435\u043d\u0442\u0430</span><div class="vx-support-id__row"><code>' +
        escapeHtml(clientCode) +
        '</code><button type="button" class="vx-icon-button" data-copy-text="' +
        escapeHtml(clientCode) +
        '" data-copy-toast="ID \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d" aria-label="\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c ID \u043a\u043b\u0438\u0435\u043d\u0442\u0430">' +
        iconSvg("copy") +
        "</button></div></div>"
      : "";
    const supportContactHtml = telegramUrl
      ? '<div class="vx-support-contact"><div class="vx-support-contact__copy"><strong>\u041d\u0430\u043f\u0438\u0441\u0430\u0442\u044c \u043e\u043f\u0435\u0440\u0430\u0442\u043e\u0440\u0443</strong><span>\u041e\u0442\u043a\u0440\u043e\u0435\u0442\u0441\u044f Telegram. \u0421\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 ID \u043d\u0438\u0436\u0435 \u0438 \u043a\u043e\u0440\u043e\u0442\u043a\u043e \u043e\u043f\u0438\u0448\u0438\u0442\u0435 \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u0443.</span></div><a class="vx-button vx-button--primary" href="' +
        escapeHtml(telegramUrl) +
        '" data-telegram-link="' +
        escapeHtml(telegramUrl) +
        '" target="_blank" rel="noopener">\u041d\u0430\u043f\u0438\u0441\u0430\u0442\u044c \u0432 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0443</a></div>'
      : '<div class="vx-support-contact"><div class="vx-support-contact__copy"><strong>Telegram \u043d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d</strong><span>\u0421\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 ID \u0438 \u0448\u0430\u0431\u043b\u043e\u043d, \u0437\u0430\u0442\u0435\u043c \u043d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u0432 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0443 \u0438\u0437 \u0431\u043e\u0442\u0430.</span></div></div>';
    const supportIdPrefix = clientCode ? "ID " + clientCode + ". " : "";
    const supportTemplatesHtml = [
      {
        label: "\u041d\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0430\u0435\u0442\u0441\u044f",
        text: supportIdPrefix + "\u041d\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0430\u0435\u0442\u0441\u044f VPN. \u0423\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u043e: . \u041a\u043e\u0433\u0434\u0430 \u043d\u0430\u0447\u0430\u043b\u043e\u0441\u044c: .",
      },
      {
        label: "\u041d\u0435 \u043e\u0442\u043a\u0440\u044b\u0432\u0430\u044e\u0442\u0441\u044f \u0441\u0430\u0439\u0442\u044b",
        text: supportIdPrefix + "\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 \u0435\u0441\u0442\u044c, \u043d\u043e \u0441\u0430\u0439\u0442\u044b \u043d\u0435 \u043e\u0442\u043a\u0440\u044b\u0432\u0430\u044e\u0442\u0441\u044f. \u0423\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u043e: . \u041a\u0430\u043a\u043e\u0439 \u0441\u0430\u0439\u0442: .",
      },
      {
        label: "\u041e\u043f\u043b\u0430\u0442\u0430 \u0438\u043b\u0438 \u043f\u0440\u043e\u0434\u043b\u0435\u043d\u0438\u0435",
        text: supportIdPrefix + "\u041f\u0440\u043e\u0431\u043b\u0435\u043c\u0430 \u0441 \u043e\u043f\u043b\u0430\u0442\u043e\u0439 \u0438\u043b\u0438 \u043f\u0440\u043e\u0434\u043b\u0435\u043d\u0438\u0435\u043c. \u0427\u0442\u043e \u043f\u0440\u043e\u0438\u0437\u043e\u0448\u043b\u043e: .",
      },
    ]
      .map(function (item) {
        return (
          '<button type="button" class="vx-support-template" data-copy-text="' +
          escapeHtml(item.text) +
          '" data-copy-toast="\u0428\u0430\u0431\u043b\u043e\u043d \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d">' +
          escapeHtml(item.label) +
          "</button>"
        );
      })
      .join("");
    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell vx-account-app__shell--support">',
      '<section class="vx-section-card vx-support-card">',
      '<div class="vx-section-card__head"><h1>' +
        escapeHtml((model && model.title) || "\u041f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430") +
        '</h1><span>' +
        escapeHtml((model && model.subtitle) || "\u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u043e\u0434\u043d\u043e \u043a\u043e\u0440\u043e\u0442\u043a\u043e\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435. ID \u043a\u043b\u0438\u0435\u043d\u0442\u0430 \u0443\u0436\u0435 \u043d\u0438\u0436\u0435.") +
      "</span></div>",
      '<div class="vx-support-body">',
      supportContactHtml,
      clientCodeHtml,
      '<div class="vx-support-templates"><strong>\u0411\u044b\u0441\u0442\u0440\u044b\u0439 \u0448\u0430\u0431\u043b\u043e\u043d</strong><span>\u0421\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u043f\u043e\u0434\u0445\u043e\u0434\u044f\u0449\u0438\u0439 \u0442\u0435\u043a\u0441\u0442 \u0438 \u043e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0435\u0433\u043e \u0432 Telegram.</span><div class="vx-support-template-list">' +
        supportTemplatesHtml +
        "</div></div>",
      '<div class="vx-support-note"><strong>\u0427\u0442\u043e \u043d\u0430\u043f\u0438\u0441\u0430\u0442\u044c</strong><span>\u041e\u0434\u043d\u0438\u043c \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435\u043c: \u0447\u0442\u043e \u043d\u0435 \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442, \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u043e, \u0438 \u043a\u043e\u0433\u0434\u0430 \u043d\u0430\u0447\u0430\u043b\u0430\u0441\u044c \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u0430.</span></div>',
      '<div class="vx-account-actions vx-account-actions--support">',
      '<button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(accountRouteUrl({ view: "instructions" })) +
        '">\u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f</button><button type="button" class="vx-button vx-button--ghost" data-nav="' +
        escapeHtml(normalizePath(cfg.accountPath || "/account/")) +
        '">\u041c\u043e\u0439 VPN</button></div>',
      "</div>",
      "</section>",
      "</section>",
    ].join("");
  }

  function renderAuth(model) {
    const isSignup = state.authMode === "signup";
    const telegram = (model && model.telegram) || {};
    const hasTelegram = !!(telegram && telegram.enabled && telegram.bot_username && telegram.auth_url);
    const helpUrl = cfg.supportTelegramUrl || cfg.supportUrl || "/instructions/";
    const fallbackTitle = isSignup
      ? "\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u043f\u043e email"
      : hasTelegram
        ? "\u0417\u0430\u043f\u0430\u0441\u043d\u044b\u0439 \u0432\u0445\u043e\u0434 \u043f\u043e email"
        : "\u0412\u043e\u0439\u0442\u0438 \u043f\u043e email";
    const fallbackText = hasTelegram
      ? "\u041d\u0443\u0436\u0435\u043d, \u0435\u0441\u043b\u0438 Telegram \u043d\u0435 \u043e\u0442\u043a\u0440\u044b\u043b \u043a\u0430\u0431\u0438\u043d\u0435\u0442 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438."
      : "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u0434\u0430\u043d\u043d\u044b\u0435 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430 VXcloud.";
    mount.className = "vx-native-account";
    mount.innerHTML = [
      '<section class="vx-account-app__shell vx-account-app__shell--auth">',
      '<section class="vx-auth-card vx-auth-card--telegram-first">',
      '<div class="vx-auth-card__tabs">',
      '<button type="button" class="vx-auth-tab' +
        (!isSignup ? " is-active" : "") +
        '" data-auth-tab="login">\u0412\u0445\u043e\u0434</button>',
      '<button type="button" class="vx-auth-tab' +
        (isSignup ? " is-active" : "") +
        '" data-auth-tab="signup">\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u044f</button>',
      "</div>",
      '<div class="vx-auth-card__body">',
      '<h1 class="vx-account-title">' + escapeHtml((model && model.title) || "\u0412\u0445\u043e\u0434 \u0432 VXcloud") + "</h1>",
      '<p class="vx-account-subtitle">' +
        escapeHtml((model && model.subtitle) || "\u041e\u0442\u043a\u0440\u043e\u0439\u0442\u0435 \u043a\u0430\u0431\u0438\u043d\u0435\u0442 \u0438\u0437 \u0431\u043e\u0442\u0430 \u0438\u043b\u0438 \u0432\u043e\u0439\u0434\u0438\u0442\u0435 \u043f\u043e email.") +
        "</p>",
      hasTelegram
        ? [
            '<section class="vx-auth-telegram">',
            '<div class="vx-auth-telegram__eyebrow">\u0412\u0445\u043e\u0434 \u0447\u0435\u0440\u0435\u0437 Telegram</div>',
            '<p class="vx-auth-telegram__copy">\u041e\u0431\u044b\u0447\u043d\u043e \u0432\u0445\u043e\u0434 \u043f\u0440\u043e\u0445\u043e\u0434\u0438\u0442 \u0441\u0430\u043c \u043f\u0440\u0438 \u043e\u0442\u043a\u0440\u044b\u0442\u0438\u0438 \u0438\u0437 \u0431\u043e\u0442\u0430.</p>',
            '<div class="vx-auth-telegram__status"><strong>\u041d\u0435 \u0432\u043e\u0448\u043b\u0438 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438?</strong><span>\u041d\u0430\u0436\u043c\u0438\u0442\u0435 \u043a\u043d\u043e\u043f\u043a\u0443 Telegram \u043d\u0438\u0436\u0435. \u0415\u0441\u043b\u0438 \u043d\u0435 \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u0441\u044f, \u0432\u043e\u0439\u0434\u0438\u0442\u0435 \u043f\u043e email \u0438\u043b\u0438 \u043d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u0432 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0443.</span></div>',
            '<div class="vx-auth-telegram__widget" data-telegram-login-widget data-bot-username="' +
              escapeHtml(telegram.bot_username || "") +
              '" data-auth-url="' +
              escapeHtml(telegram.auth_url || "") +
              '"></div>',
            '<div class="vx-auth-divider"><span>email, \u0435\u0441\u043b\u0438 \u043d\u0443\u0436\u043d\u043e</span></div>',
            "</section>",
          ].join("")
        : "",
      '<section class="vx-auth-fallback">',
      '<div class="vx-auth-fallback__head"><strong>' +
        fallbackTitle +
        "</strong><span>" +
        fallbackText +
        "</span></div>",
      '<div class="vx-auth-errors" data-auth-errors></div>',
      !isSignup
        ? [
            '<form class="vx-auth-form" data-auth-form="login">',
            '<label>\u041b\u043e\u0433\u0438\u043d \u0438\u043b\u0438 email<input type="text" name="username" autocomplete="username" required></label>',
            '<label>\u041f\u0430\u0440\u043e\u043b\u044c<input type="password" name="password" autocomplete="current-password" required></label>',
            '<button type="submit" class="vx-button vx-button--primary vx-button--block">\u0412\u043e\u0439\u0442\u0438</button>',
            "</form>",
          ].join("")
        : [
            '<form class="vx-auth-form" data-auth-form="signup">',
            '<label>\u041b\u043e\u0433\u0438\u043d<input type="text" name="username" autocomplete="username" required></label>',
            '<label>Email<input type="email" name="email" autocomplete="email" required></label>',
            '<label>\u041f\u0430\u0440\u043e\u043b\u044c<input type="password" name="password" autocomplete="new-password" required></label>',
            '<label>\u041f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u0435 \u043f\u0430\u0440\u043e\u043b\u044c<input type="password" name="password_confirm" autocomplete="new-password" required></label>',
            '<button type="submit" class="vx-button vx-button--primary vx-button--block">\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u0430\u043a\u043a\u0430\u0443\u043d\u0442</button>',
            "</form>",
          ].join(""),
      '<div class="vx-auth-links"><a href="' +
        escapeHtml(helpUrl) +
        '" data-telegram-link="' +
        escapeHtml(helpUrl) +
        '">\u041d\u0430\u043f\u0438\u0441\u0430\u0442\u044c \u0432 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0443</a><a href="' +
        escapeHtml((model && model.password_reset_url) || "/accounts/password_reset/") +
        '">\u0417\u0430\u0431\u044b\u043b\u0438 \u043f\u0430\u0440\u043e\u043b\u044c?</a></div>',
      "</section>",
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
          showToast(button.getAttribute("data-copy-toast") || "Ссылка скопирована");
        } catch (error) {
          console.debug("copy failed", error);
        }
      });
    });

    mount.querySelectorAll("[data-delete-subscription]").forEach(function (button) {
      button.addEventListener("click", async function () {
        const subscriptionId = button.getAttribute("data-delete-subscription") || "";
        if (!subscriptionId || state.pending) return;
        if (!window.confirm("Удалить этот неактивный доступ?")) return;

        state.pending = true;
        button.setAttribute("disabled", "disabled");
        try {
          await apiFetch(subscriptionDeleteUrl(subscriptionId), {
            method: "POST",
            body: {},
          });
          showToast("Доступ удален");
          if (/^\/account\/config\/\d+\/?$/i.test(window.location.pathname)) {
            window.history.pushState({}, "", normalizePath(cfg.accountPath || "/account/"));
          }
          await loadCurrentView();
        } catch (error) {
          showToast((error.payload && error.payload.error) || "Не удалось удалить доступ");
        } finally {
          state.pending = false;
          button.removeAttribute("disabled");
        }
      });
    });

    mount.querySelectorAll("[data-telegram-link]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        const url = button.getAttribute("data-telegram-link") || button.getAttribute("href") || "";
        if (!url) return;
        event.preventDefault();
        openTelegramLink(url);
      });
    });

    mount.querySelectorAll("[data-nav]").forEach(function (button) {
      button.addEventListener("click", function () {
        const nextPath = button.getAttribute("data-nav") || cfg.accountUrl;
        window.history.pushState({}, "", nextPath);
        loadCurrentView();
      });
    });

    mount.querySelectorAll("[data-retry-load]").forEach(function (button) {
      button.addEventListener("click", function () {
        loadCurrentView();
      });
    });

    mount.querySelectorAll("[data-checkout]").forEach(function (button) {
      button.addEventListener("click", async function () {
        const mode = button.getAttribute("data-checkout");
        if (!mode || state.pending) return;
        const subscriptionId = button.getAttribute("data-subscription-id") || "";
        state.pending = true;
        button.setAttribute("disabled", "disabled");
        try {
          const endpoint = mode === "buy" ? cfg.apiBuyUrl : cfg.apiRenewUrl;
          const body = mode === "renew" && /^\d+$/.test(subscriptionId) ? { subscription_id: Number(subscriptionId) } : {};
          const result = await apiFetch(endpoint, { method: "POST", body: body });
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
          bindSharedInteractions();
          return;
        } finally {
          state.pending = false;
          button.removeAttribute("disabled");
        }
      });
    });

    mount.querySelectorAll("[data-scroll-renew]").forEach(function (button) {
      button.addEventListener("click", function () {
        const list = mount.querySelector(".vx-config-list");
        if (list && typeof list.scrollIntoView === "function") {
          list.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        showToast("\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0434\u043e\u0441\u0442\u0443\u043f \u0434\u043b\u044f \u043f\u0440\u043e\u0434\u043b\u0435\u043d\u0438\u044f");
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
          showToast("Введите название доступа");
          return;
        }

        state.pending = true;
        if (submitButton) submitButton.setAttribute("disabled", "disabled");
        try {
          await apiFetch(subscriptionRenameUrl(subscriptionId), {
            method: "POST",
            body: { display_name: displayName },
          });
          showToast("Название доступа обновлено");
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
          subtitle: "Войдите в аккаунт, чтобы управлять доступами и подписками.",
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
    window.clearTimeout(state.paymentPollTimer);
    const loadToken = ++state.loadToken;
    await syncTelegramWebAppSession();
    if (loadToken !== state.loadToken) return;
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
    if (route.device) params.set("device", String(route.device));

    try {
      const payload = await apiFetch(cfg.apiStateUrl + "?" + params.toString());
      if (loadToken !== state.loadToken) return;
      window.clearTimeout(state.loadingTimer);
      updateTelegramBackButton(route);

      if (!payload.authenticated) {
        updateTelegramBackButton({ view: "auth" });
        state.authModel = payload.auth || {};
        renderAuth(state.authModel);
        bindSharedInteractions();
        bindAuthInteractions();
        initTelegramLoginWidget();
        releaseMountHeight();
        return;
      }

      if (route.view === "checkout-buy" || route.view === "checkout-renew") {
        renderCheckoutProgress(route);
        bindSharedInteractions();
        try {
          const endpoint = route.view === "checkout-buy" ? cfg.apiBuyUrl : cfg.apiRenewUrl;
          const body = route.view === "checkout-renew" && route.subscriptionId ? { subscription_id: route.subscriptionId } : {};
          const result = await apiFetch(endpoint, { method: "POST", body: body });
          if (result && result.redirect_url) {
            window.location.assign(result.redirect_url);
            return;
          }
          renderError("\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u043e\u043f\u043b\u0430\u0442\u0443.");
          bindSharedInteractions();
          releaseMountHeight();
          return;
        } catch (error) {
          renderError((error.payload && error.payload.error) || "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u043e\u043f\u043b\u0430\u0442\u0443.");
          bindSharedInteractions();
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
      } else if (payload.view === "instructions" && payload.instructions) {
        renderInstructions(payload.instructions);
      } else if (payload.view === "support" && payload.support) {
        renderSupport(payload.support);
      } else {
        renderDashboard(payload.dashboard || {});
      }
      updateTelegramBackButton(route);
      bindSharedInteractions();
      releaseMountHeight();
    } catch (error) {
      if (loadToken !== state.loadToken) return;
      window.clearTimeout(state.loadingTimer);
      updateTelegramBackButton(route);
      renderError((error.payload && error.payload.error) || "Не удалось загрузить страницу аккаунта.");
      bindSharedInteractions();
      releaseMountHeight();
    }
  }

  window.addEventListener("popstate", function () {
    loadCurrentView();
  });

  bindTelegramBackButton();
  loadCurrentView();
})();
