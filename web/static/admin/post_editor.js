(function () {
  const selector = "textarea.js-richtext";

  function init() {
    if (!window.tinymce) return;
    if (!document.querySelector(selector)) return;

    window.tinymce.remove(selector);
    window.tinymce.init({
      selector,
      height: 860,
      min_height: 680,
      menubar: "file edit view insert format tools table help",
      branding: false,
      plugins:
        "autolink link lists table code fullscreen preview searchreplace visualblocks wordcount emoticons charmap quickbars template",
      toolbar:
        "undo redo | blocks styles | bold italic underline strikethrough | " +
        "alignleft aligncenter alignright alignjustify | bullist numlist outdent indent | " +
        "link table template | blockquote hr | removeformat code fullscreen preview",
      quickbars_selection_toolbar: "bold italic | quicklink h2 h3 blockquote",
      block_formats: "Параграф=p; Заголовок 2=h2; Заголовок 3=h3; Заголовок 4=h4",
      style_formats: [
        { title: "Кнопка тёмная", selector: "a", classes: "btn btn-primary" },
        { title: "Кнопка светлая", selector: "a", classes: "btn btn-secondary" },
        { title: "Обычная ссылка", selector: "a", classes: "" },
      ],
      templates: [
        {
          title: "Кнопка: Купить доступ",
          description: "Кнопка оплаты на /account/buy/",
          content: '<a class="btn btn-primary" href="/account/buy/">⭐ Купить доступ · 249 ₽</a>',
        },
        {
          title: "Кнопка: Продлить",
          description: "Кнопка продления на /account/renew/",
          content: '<a class="btn btn-secondary" href="/account/renew/">🔄 Продлить · 249 ₽</a>',
        },
        {
          title: "Кнопка: Личный кабинет",
          description: "Кнопка перехода в кабинет",
          content: '<a class="btn btn-secondary" href="/account/">🌐 Личный кабинет</a>',
        },
        {
          title: "Блок кнопок (Купить + Продлить + Кабинет)",
          description: "Готовый горизонтальный блок кнопок",
          content:
            '<div style="margin-top:16px;display:flex;gap:10px;flex-wrap:wrap;">' +
            '<a class="btn btn-primary" href="/account/buy/">⭐ Купить доступ · 249 ₽</a>' +
            '<a class="btn btn-secondary" href="/account/renew/">🔄 Продлить · 249 ₽</a>' +
            '<a class="btn btn-secondary" href="/account/">🌐 Личный кабинет</a>' +
            "</div>",
        },
      ],
      content_style:
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; font-size: 16px; line-height: 1.65; max-width: 860px; margin: 20px auto; padding: 0 18px; }" +
        ".btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;border-radius:10px;border:1px solid #e5e7eb;padding:9px 14px;font-size:14px;font-weight:600;line-height:1.2;background:#fff;color:#111827;text-decoration:none;}" +
        ".btn-primary{background:#111827;border-color:#111827;color:#fff;}" +
        ".btn-secondary{background:#fff;border-color:#e5e7eb;color:#111827;}",
      convert_urls: false,
      resize: true,
      toolbar_sticky: true,
      browser_spellcheck: true,
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
