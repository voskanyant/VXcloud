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
        "autolink link lists table code fullscreen preview searchreplace visualblocks wordcount emoticons charmap quickbars",
      toolbar:
        "undo redo | blocks | bold italic underline strikethrough | " +
        "alignleft aligncenter alignright alignjustify | bullist numlist outdent indent | " +
        "link table | blockquote hr | removeformat code fullscreen preview",
      quickbars_selection_toolbar: "bold italic | quicklink h2 h3 blockquote",
      block_formats: "Параграф=p; Заголовок 2=h2; Заголовок 3=h3; Заголовок 4=h4",
      content_style:
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; font-size: 16px; line-height: 1.65; max-width: 860px; margin: 20px auto; padding: 0 18px; }",
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
