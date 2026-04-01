(function () {
  const SOURCE_SELECTOR = "textarea.js-block-editor-source";

  const BLOCK_TYPES = [
    { value: "paragraph", label: "Параграф" },
    { value: "heading", label: "Заголовок" },
    { value: "list", label: "Список" },
    { value: "quote", label: "Цитата" },
    { value: "image", label: "Изображение (URL)" },
    { value: "embed", label: "Встраивание (ссылка)" },
    { value: "button", label: "Кнопка" },
    { value: "buttons", label: "Группа кнопок" },
    { value: "columns", label: "2 колонки" },
    { value: "faq", label: "FAQ пункт" },
    { value: "spacer", label: "Отступ" },
    { value: "html", label: "HTML" },
  ];

  function parseJSON(raw) {
    if (!raw || !raw.trim()) return [];
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  function field(label, inputEl) {
    const row = document.createElement("label");
    row.className = "be-field";
    const title = document.createElement("span");
    title.className = "be-label";
    title.textContent = label;
    row.appendChild(title);
    row.appendChild(inputEl);
    return row;
  }

  function textInput(value = "") {
    const input = document.createElement("input");
    input.type = "text";
    input.className = "vTextField";
    input.value = value || "";
    return input;
  }

  function textArea(value = "", rows = 4) {
    const input = document.createElement("textarea");
    input.rows = rows;
    input.className = "vLargeTextField";
    input.value = value || "";
    return input;
  }

  function numberInput(value = 24, min = 1, max = 180) {
    const input = document.createElement("input");
    input.type = "number";
    input.className = "vIntegerField";
    input.value = String(value ?? "");
    input.min = String(min);
    input.max = String(max);
    return input;
  }

  function selectInput(options, value) {
    const select = document.createElement("select");
    options.forEach((opt) => {
      const o = document.createElement("option");
      o.value = opt.value;
      o.textContent = opt.label;
      if (String(value || "") === String(opt.value)) o.selected = true;
      select.appendChild(o);
    });
    return select;
  }

  function blockTitle(type) {
    const opt = BLOCK_TYPES.find((x) => x.value === type);
    return opt ? opt.label : type;
  }

  function defaultsFor(type) {
    switch (type) {
      case "heading":
        return { type, level: 2, text: "Новый заголовок" };
      case "list":
        return { type, ordered: false, items: ["Пункт 1", "Пункт 2"] };
      case "quote":
        return { type, text: "Цитата", cite: "" };
      case "image":
        return { type, src: "", alt: "", caption: "" };
      case "embed":
        return { type, url: "" };
      case "button":
        return { type, label: "Купить доступ", url: "/account/buy/", style: "primary" };
      case "buttons":
        return {
          type,
          items: [
            { label: "Купить доступ", url: "/account/buy/", style: "primary" },
            { label: "Продлить", url: "/account/renew/", style: "secondary" },
          ],
        };
      case "columns":
        return { type, left: "Левая колонка", right: "Правая колонка" };
      case "faq":
        return { type, question: "Вопрос", answer: "Ответ" };
      case "spacer":
        return { type, height: 24 };
      case "html":
        return { type, html: "<div></div>" };
      default:
        return { type, text: "Новый текст" };
    }
  }

  function mountEditor(source) {
    source.style.display = "none";

    const root = document.createElement("div");
    root.className = "be-root";
    source.parentNode.insertBefore(root, source.nextSibling);

    const header = document.createElement("div");
    header.className = "be-header";
    header.innerHTML = "<strong>Блочный редактор</strong><span>Похоже на Gutenberg: собирайте страницу из блоков.</span>";

    const controls = document.createElement("div");
    controls.className = "be-controls";
    const addSelect = selectInput(BLOCK_TYPES, "paragraph");
    const addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.className = "button";
    addBtn.textContent = "Добавить блок";
    controls.appendChild(addSelect);
    controls.appendChild(addBtn);

    const list = document.createElement("div");
    list.className = "be-list";

    root.appendChild(header);
    root.appendChild(controls);
    root.appendChild(list);

    const state = { blocks: parseJSON(source.value) };

    function sync() {
      source.value = JSON.stringify(state.blocks);
    }

    function rerender() {
      list.innerHTML = "";
      state.blocks.forEach((block, index) => {
        const card = document.createElement("section");
        card.className = "be-block";

        const top = document.createElement("div");
        top.className = "be-block-top";
        const title = document.createElement("strong");
        title.textContent = blockTitle(block.type || "paragraph");
        const actions = document.createElement("div");
        actions.className = "be-actions";
        const up = document.createElement("button");
        up.type = "button";
        up.className = "button";
        up.textContent = "↑";
        up.disabled = index === 0;
        const down = document.createElement("button");
        down.type = "button";
        down.className = "button";
        down.textContent = "↓";
        down.disabled = index === state.blocks.length - 1;
        const del = document.createElement("button");
        del.type = "button";
        del.className = "button deletelink";
        del.textContent = "Удалить";
        actions.appendChild(up);
        actions.appendChild(down);
        actions.appendChild(del);
        top.appendChild(title);
        top.appendChild(actions);
        card.appendChild(top);

        const body = document.createElement("div");
        body.className = "be-block-body";
        const type = String(block.type || "paragraph");

        if (type === "paragraph") {
          const input = textArea(block.text || "", 5);
          input.addEventListener("input", () => (block.text = input.value));
          body.appendChild(field("Текст", input));
        } else if (type === "heading") {
          const level = selectInput(
            [
              { value: 1, label: "H1" },
              { value: 2, label: "H2" },
              { value: 3, label: "H3" },
              { value: 4, label: "H4" },
            ],
            block.level || 2
          );
          const text = textInput(block.text || "");
          level.addEventListener("change", () => (block.level = Number(level.value)));
          text.addEventListener("input", () => (block.text = text.value));
          body.appendChild(field("Уровень", level));
          body.appendChild(field("Текст", text));
        } else if (type === "list") {
          const ordered = document.createElement("input");
          ordered.type = "checkbox";
          ordered.checked = !!block.ordered;
          const items = textArea(Array.isArray(block.items) ? block.items.join("\n") : "", 6);
          ordered.addEventListener("change", () => (block.ordered = ordered.checked));
          items.addEventListener("input", () => {
            block.items = items.value
              .split("\n")
              .map((x) => x.trim())
              .filter(Boolean);
          });
          body.appendChild(field("Нумерованный", ordered));
          body.appendChild(field("Пункты (по одному на строку)", items));
        } else if (type === "quote") {
          const text = textArea(block.text || "", 4);
          const cite = textInput(block.cite || "");
          text.addEventListener("input", () => (block.text = text.value));
          cite.addEventListener("input", () => (block.cite = cite.value));
          body.appendChild(field("Цитата", text));
          body.appendChild(field("Автор/источник", cite));
        } else if (type === "image") {
          const src = textInput(block.src || "");
          const alt = textInput(block.alt || "");
          const caption = textInput(block.caption || "");
          src.addEventListener("input", () => (block.src = src.value));
          alt.addEventListener("input", () => (block.alt = alt.value));
          caption.addEventListener("input", () => (block.caption = caption.value));
          body.appendChild(field("URL картинки", src));
          body.appendChild(field("ALT", alt));
          body.appendChild(field("Подпись", caption));
        } else if (type === "embed") {
          const url = textInput(block.url || "");
          url.addEventListener("input", () => (block.url = url.value));
          body.appendChild(field("Ссылка", url));
        } else if (type === "button") {
          const label = textInput(block.label || "");
          const url = textInput(block.url || "");
          const style = selectInput(
            [
              { value: "primary", label: "Тёмная" },
              { value: "secondary", label: "Светлая" },
            ],
            block.style || "primary"
          );
          label.addEventListener("input", () => (block.label = label.value));
          url.addEventListener("input", () => (block.url = url.value));
          style.addEventListener("change", () => (block.style = style.value));
          body.appendChild(field("Текст кнопки", label));
          body.appendChild(field("Ссылка", url));
          body.appendChild(field("Стиль", style));
        } else if (type === "buttons") {
          const items = textArea(
            (block.items || [])
              .map((x) => `${x.label || ""}|${x.url || ""}|${x.style || "primary"}`)
              .join("\n"),
            6
          );
          items.addEventListener("input", () => {
            block.items = items.value
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean)
              .map((line) => {
                const [label, url, style] = line.split("|").map((x) => (x || "").trim());
                return { label, url, style: style === "secondary" ? "secondary" : "primary" };
              });
          });
          body.appendChild(field("Кнопки (label|url|style) по строкам", items));
        } else if (type === "columns") {
          const left = textArea(block.left || "", 4);
          const right = textArea(block.right || "", 4);
          left.addEventListener("input", () => (block.left = left.value));
          right.addEventListener("input", () => (block.right = right.value));
          body.appendChild(field("Левая колонка", left));
          body.appendChild(field("Правая колонка", right));
        } else if (type === "faq") {
          const q = textInput(block.question || "");
          const a = textArea(block.answer || "", 4);
          q.addEventListener("input", () => (block.question = q.value));
          a.addEventListener("input", () => (block.answer = a.value));
          body.appendChild(field("Вопрос", q));
          body.appendChild(field("Ответ", a));
        } else if (type === "spacer") {
          const h = numberInput(block.height || 24, 8, 180);
          h.addEventListener("input", () => (block.height = Number(h.value || 24)));
          body.appendChild(field("Высота (px)", h));
        } else if (type === "html") {
          const html = textArea(block.html || "", 6);
          html.addEventListener("input", () => (block.html = html.value));
          body.appendChild(field("HTML", html));
        }

        card.appendChild(body);
        list.appendChild(card);

        up.addEventListener("click", () => {
          const t = state.blocks[index - 1];
          state.blocks[index - 1] = state.blocks[index];
          state.blocks[index] = t;
          rerender();
          sync();
        });
        down.addEventListener("click", () => {
          const t = state.blocks[index + 1];
          state.blocks[index + 1] = state.blocks[index];
          state.blocks[index] = t;
          rerender();
          sync();
        });
        del.addEventListener("click", () => {
          state.blocks.splice(index, 1);
          rerender();
          sync();
        });
      });

      if (!state.blocks.length) {
        const empty = document.createElement("p");
        empty.className = "help";
        empty.textContent = "Блоков пока нет. Добавьте первый блок сверху.";
        list.appendChild(empty);
      }
    }

    addBtn.addEventListener("click", () => {
      state.blocks.push(defaultsFor(addSelect.value));
      rerender();
      sync();
    });

    root.addEventListener("input", sync, true);
    root.addEventListener("change", sync, true);
    rerender();
    sync();
  }

  function init() {
    document.querySelectorAll(SOURCE_SELECTOR).forEach((source) => mountEditor(source));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

