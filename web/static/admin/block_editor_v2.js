(function () {
  const SOURCE_SELECTOR = "textarea.js-block-editor-source";

  const BLOCK_TYPES = [
    { value: "paragraph", label: "Paragraph", icon: "P", group: "Text" },
    { value: "heading", label: "Heading", icon: "H", group: "Text" },
    { value: "list", label: "List", icon: "L", group: "Text" },
    { value: "quote", label: "Quote", icon: "Q", group: "Text" },
    { value: "image", label: "Image", icon: "I", group: "Media" },
    { value: "embed", label: "Embed", icon: "E", group: "Media" },
    { value: "button", label: "Button", icon: "B", group: "Design" },
    { value: "buttons", label: "Buttons Group", icon: "BG", group: "Design" },
    { value: "columns", label: "Columns", icon: "C", group: "Layout" },
    { value: "faq", label: "FAQ Item", icon: "?", group: "Design" },
    { value: "spacer", label: "Spacer", icon: "S", group: "Layout" },
    { value: "html", label: "Custom HTML", icon: "<>", group: "Advanced" },
  ];

  const GROUPS = ["Text", "Media", "Design", "Layout", "Advanced"];

  function parseJSON(raw) {
    if (!raw || !raw.trim()) return [];
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (_error) {
      return [];
    }
  }

  function defaultsFor(type) {
    switch (type) {
      case "heading":
        return { type, level: 2, text: "New heading" };
      case "list":
        return { type, ordered: false, items: ["Item 1", "Item 2"] };
      case "quote":
        return { type, text: "Quote text", cite: "" };
      case "image":
        return { type, src: "", alt: "", caption: "" };
      case "embed":
        return { type, url: "" };
      case "button":
        return { type, label: "Buy access", url: "/account/buy/", style: "primary" };
      case "buttons":
        return {
          type,
          items: [
            { label: "Buy access", url: "/account/buy/", style: "primary" },
            { label: "Renew", url: "/account/renew/", style: "secondary" },
          ],
        };
      case "columns":
        return { type, left: "Left column", right: "Right column" };
      case "faq":
        return { type, question: "Question", answer: "Answer" };
      case "spacer":
        return { type, height: 24 };
      case "html":
        return { type, html: "<div></div>" };
      default:
        return { type, text: "New paragraph" };
    }
  }

  function blockMeta(type) {
    return BLOCK_TYPES.find((item) => item.value === type) || BLOCK_TYPES[0];
  }

  function textInput(value) {
    const input = document.createElement("input");
    input.type = "text";
    input.className = "vTextField";
    input.value = value || "";
    return input;
  }

  function textArea(value, rows) {
    const input = document.createElement("textarea");
    input.className = "vLargeTextField";
    input.rows = rows || 4;
    input.value = value || "";
    return input;
  }

  function numberInput(value, min, max) {
    const input = document.createElement("input");
    input.type = "number";
    input.className = "vIntegerField";
    input.value = String(value || 0);
    input.min = String(min || 1);
    input.max = String(max || 9999);
    return input;
  }

  function selectInput(options, value) {
    const select = document.createElement("select");
    options.forEach((opt) => {
      const option = document.createElement("option");
      option.value = opt.value;
      option.textContent = opt.label;
      if (String(value) === String(opt.value)) option.selected = true;
      select.appendChild(option);
    });
    return select;
  }

  function field(label, control, hint) {
    const wrapper = document.createElement("label");
    wrapper.className = "be-field";

    const text = document.createElement("span");
    text.className = "be-label";
    text.textContent = label;
    wrapper.appendChild(text);

    wrapper.appendChild(control);

    if (hint) {
      const help = document.createElement("small");
      help.className = "be-hint";
      help.textContent = hint;
      wrapper.appendChild(help);
    }
    return wrapper;
  }

  function blockPreview(block) {
    const type = String(block.type || "paragraph");
    if (type === "heading") return String(block.text || "Heading");
    if (type === "paragraph") return String(block.text || "Paragraph");
    if (type === "list") return Array.isArray(block.items) ? block.items.join(" - ") : "List";
    if (type === "quote") return String(block.text || "Quote");
    if (type === "image") return String(block.src || "Image without URL");
    if (type === "embed") return String(block.url || "Embed without URL");
    if (type === "button") return `${block.label || "Button"} -> ${block.url || ""}`;
    if (type === "buttons") return "Buttons group";
    if (type === "columns") return "Two-column content";
    if (type === "faq") return String(block.question || "FAQ item");
    if (type === "spacer") return `Spacer ${block.height || 24}px`;
    if (type === "html") return "Custom HTML";
    return type;
  }

  function mountEditor(source) {
    source.style.display = "none";
    const formRow = source.closest(".form-row");
    if (formRow) formRow.classList.add("be-source-hidden");

    const root = document.createElement("section");
    root.className = "be-shell";
    source.parentNode.insertBefore(root, source.nextSibling);

    const left = document.createElement("aside");
    left.className = "be-left";
    const center = document.createElement("section");
    center.className = "be-canvas";
    const right = document.createElement("aside");
    right.className = "be-right";
    root.appendChild(left);
    root.appendChild(center);
    root.appendChild(right);

    function applyResponsiveMode() {
      const width = root.getBoundingClientRect().width || 0;
      root.classList.toggle("be-mode-compact", width > 0 && width < 1160);
      root.classList.toggle("be-mode-stack", width > 0 && width < 860);
    }

    applyResponsiveMode();
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(() => applyResponsiveMode());
      observer.observe(root);
    } else {
      window.addEventListener("resize", applyResponsiveMode);
    }

    const state = {
      blocks: parseJSON(source.value),
      selectedIndex: -1,
      search: "",
    };
    if (state.blocks.length) state.selectedIndex = 0;

    function sync() {
      source.value = JSON.stringify(state.blocks);
    }

    function selectBlock(index) {
      state.selectedIndex = index;
      renderCanvas();
      renderInspector();
      sync();
    }

    function addBlock(type) {
      state.blocks.push(defaultsFor(type));
      state.selectedIndex = state.blocks.length - 1;
      renderCanvas();
      renderInspector();
      sync();
    }

    function removeSelected() {
      if (state.selectedIndex < 0 || state.selectedIndex >= state.blocks.length) return;
      state.blocks.splice(state.selectedIndex, 1);
      if (!state.blocks.length) state.selectedIndex = -1;
      else if (state.selectedIndex >= state.blocks.length) state.selectedIndex = state.blocks.length - 1;
      renderCanvas();
      renderInspector();
      sync();
    }

    function moveSelected(step) {
      const current = state.selectedIndex;
      const target = current + step;
      if (current < 0 || current >= state.blocks.length) return;
      if (target < 0 || target >= state.blocks.length) return;
      const tmp = state.blocks[target];
      state.blocks[target] = state.blocks[current];
      state.blocks[current] = tmp;
      state.selectedIndex = target;
      renderCanvas();
      renderInspector();
      sync();
    }

    function duplicateSelected() {
      const index = state.selectedIndex;
      if (index < 0 || index >= state.blocks.length) return;
      const clone = JSON.parse(JSON.stringify(state.blocks[index]));
      state.blocks.splice(index + 1, 0, clone);
      state.selectedIndex = index + 1;
      renderCanvas();
      renderInspector();
      sync();
    }

    function renderLeft() {
      left.innerHTML = "";

      const head = document.createElement("header");
      head.className = "be-left-head";
      head.innerHTML = "<strong>Blocks</strong><span>Insert blocks</span>";

      const search = textInput(state.search || "");
      search.classList.add("be-search");
      search.placeholder = "Search blocks...";
      search.addEventListener("input", () => {
        state.search = search.value.toLowerCase();
        renderLeft();
      });

      const tabs = document.createElement("div");
      tabs.className = "be-left-tabs";
      tabs.innerHTML = "<span class='is-active'>Blocks</span><span>Patterns</span><span>Media</span>";

      const list = document.createElement("div");
      list.className = "be-left-list";

      GROUPS.forEach((group) => {
        const filtered = BLOCK_TYPES.filter((block) => {
          if (block.group !== group) return false;
          if (!state.search) return true;
          return (
            block.label.toLowerCase().includes(state.search) ||
            block.value.toLowerCase().includes(state.search) ||
            block.group.toLowerCase().includes(state.search)
          );
        });
        if (!filtered.length) return;

        const groupBlock = document.createElement("section");
        groupBlock.className = "be-library-group";

        const title = document.createElement("h4");
        title.textContent = group;
        groupBlock.appendChild(title);

        const grid = document.createElement("div");
        grid.className = "be-library-grid";

        filtered.forEach((meta) => {
          const item = document.createElement("button");
          item.type = "button";
          item.className = "be-library-item";
          item.innerHTML = `<span class="be-lib-icon">${meta.icon}</span><span class="be-lib-label">${meta.label}</span>`;
          item.addEventListener("click", () => addBlock(meta.value));
          grid.appendChild(item);
        });

        groupBlock.appendChild(grid);
        list.appendChild(groupBlock);
      });

      left.appendChild(head);
      left.appendChild(search);
      left.appendChild(tabs);
      left.appendChild(list);
    }

    function renderCanvas() {
      center.innerHTML = "";

      const top = document.createElement("header");
      top.className = "be-canvas-head";
      top.innerHTML =
        "<div class='be-doc-meta'><strong>Document</strong><small>Type / to choose a block</small></div>" +
        "<div class='be-doc-count'></div>";
      top.querySelector(".be-doc-count").textContent = `${state.blocks.length} blocks`;

      const stage = document.createElement("div");
      stage.className = "be-canvas-stage";

      if (!state.blocks.length) {
        const empty = document.createElement("article");
        empty.className = "be-empty";
        empty.innerHTML =
          "<h3>Add title</h3>" +
          "<p>Choose a block from the left panel, or click the button below.</p>";
        const quickAdd = document.createElement("button");
        quickAdd.type = "button";
        quickAdd.className = "button default";
        quickAdd.textContent = "+ Paragraph";
        quickAdd.addEventListener("click", () => addBlock("paragraph"));
        empty.appendChild(quickAdd);
        stage.appendChild(empty);
      } else {
        state.blocks.forEach((block, index) => {
          const meta = blockMeta(block.type || "paragraph");
          const card = document.createElement("article");
          card.className = "be-canvas-block";
          if (state.selectedIndex === index) card.classList.add("is-selected");
          card.innerHTML =
            "<div class='be-canvas-block-top'>" +
            `<span class='be-canvas-type'>${meta.icon} ${meta.label}</span>` +
            `<span class='be-canvas-index'>#${index + 1}</span>` +
            "</div>" +
            "<div class='be-canvas-preview'></div>";
          card.querySelector(".be-canvas-preview").textContent = blockPreview(block);
          card.addEventListener("click", () => selectBlock(index));
          stage.appendChild(card);
        });

        const addMore = document.createElement("button");
        addMore.type = "button";
        addMore.className = "button default be-add-more";
        addMore.textContent = "+ Add block";
        addMore.addEventListener("click", () => addBlock("paragraph"));
        stage.appendChild(addMore);
      }

      center.appendChild(top);
      center.appendChild(stage);
    }

    function renderInspector() {
      right.innerHTML = "";

      const head = document.createElement("header");
      head.className = "be-right-head";
      head.innerHTML = "<div class='be-right-tabs'><span>Post</span><span class='is-active'>Block</span></div>";
      right.appendChild(head);

      if (state.selectedIndex < 0 || state.selectedIndex >= state.blocks.length) {
        const empty = document.createElement("p");
        empty.className = "be-right-empty";
        empty.textContent = "Select a block to edit settings.";
        right.appendChild(empty);
        return;
      }

      const selected = state.blocks[state.selectedIndex];
      const meta = blockMeta(selected.type || "paragraph");

      const title = document.createElement("div");
      title.className = "be-selected-title";
      title.textContent = `${meta.icon} ${meta.label}`;
      right.appendChild(title);

      const actions = document.createElement("div");
      actions.className = "be-inspector-actions";
      actions.innerHTML = "<span>Actions</span>";
      const up = document.createElement("button");
      up.type = "button";
      up.className = "button";
      up.textContent = "Up";
      up.disabled = state.selectedIndex === 0;
      up.addEventListener("click", () => moveSelected(-1));
      const down = document.createElement("button");
      down.type = "button";
      down.className = "button";
      down.textContent = "Down";
      down.disabled = state.selectedIndex === state.blocks.length - 1;
      down.addEventListener("click", () => moveSelected(1));
      const duplicate = document.createElement("button");
      duplicate.type = "button";
      duplicate.className = "button";
      duplicate.textContent = "Duplicate";
      duplicate.addEventListener("click", duplicateSelected);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "button deletelink";
      remove.textContent = "Delete";
      remove.addEventListener("click", removeSelected);
      actions.appendChild(up);
      actions.appendChild(down);
      actions.appendChild(duplicate);
      actions.appendChild(remove);
      right.appendChild(actions);

      const form = document.createElement("div");
      form.className = "be-inspector-form";
      right.appendChild(form);

      function changed() {
        renderCanvas();
        sync();
      }

      const type = String(selected.type || "paragraph");
      if (type === "paragraph") {
        const input = textArea(selected.text || "", 8);
        input.addEventListener("input", () => {
          selected.text = input.value;
          changed();
        });
        form.appendChild(field("Text", input));
      } else if (type === "heading") {
        const level = selectInput(
          [
            { value: 1, label: "H1" },
            { value: 2, label: "H2" },
            { value: 3, label: "H3" },
            { value: 4, label: "H4" },
          ],
          selected.level || 2
        );
        const text = textInput(selected.text || "");
        level.addEventListener("change", () => {
          selected.level = Number(level.value);
          changed();
        });
        text.addEventListener("input", () => {
          selected.text = text.value;
          changed();
        });
        form.appendChild(field("Level", level));
        form.appendChild(field("Text", text));
      } else if (type === "list") {
        const ordered = document.createElement("input");
        ordered.type = "checkbox";
        ordered.checked = !!selected.ordered;
        ordered.addEventListener("change", () => {
          selected.ordered = ordered.checked;
          changed();
        });
        const items = textArea(Array.isArray(selected.items) ? selected.items.join("\n") : "", 8);
        items.addEventListener("input", () => {
          selected.items = items.value
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean);
          changed();
        });
        form.appendChild(field("Ordered list", ordered));
        form.appendChild(field("Items (one line = one item)", items));
      } else if (type === "quote") {
        const text = textArea(selected.text || "", 6);
        const cite = textInput(selected.cite || "");
        text.addEventListener("input", () => {
          selected.text = text.value;
          changed();
        });
        cite.addEventListener("input", () => {
          selected.cite = cite.value;
          changed();
        });
        form.appendChild(field("Quote", text));
        form.appendChild(field("Author", cite));
      } else if (type === "image") {
        const src = textInput(selected.src || "");
        const alt = textInput(selected.alt || "");
        const caption = textInput(selected.caption || "");
        src.addEventListener("input", () => {
          selected.src = src.value;
          changed();
        });
        alt.addEventListener("input", () => {
          selected.alt = alt.value;
          changed();
        });
        caption.addEventListener("input", () => {
          selected.caption = caption.value;
          changed();
        });
        form.appendChild(field("Image URL", src));
        form.appendChild(field("Alt text", alt, "Leave empty for decorative images."));
        form.appendChild(field("Caption", caption));
      } else if (type === "embed") {
        const url = textInput(selected.url || "");
        url.addEventListener("input", () => {
          selected.url = url.value;
          changed();
        });
        form.appendChild(field("Embed URL", url));
      } else if (type === "button") {
        const label = textInput(selected.label || "");
        const url = textInput(selected.url || "");
        const style = selectInput(
          [
            { value: "primary", label: "Primary" },
            { value: "secondary", label: "Secondary" },
          ],
          selected.style || "primary"
        );
        label.addEventListener("input", () => {
          selected.label = label.value;
          changed();
        });
        url.addEventListener("input", () => {
          selected.url = url.value;
          changed();
        });
        style.addEventListener("change", () => {
          selected.style = style.value;
          changed();
        });
        form.appendChild(field("Button text", label));
        form.appendChild(field("URL", url));
        form.appendChild(field("Style", style));
      } else if (type === "buttons") {
        const items = textArea(
          (selected.items || []).map((item) => `${item.label || ""}|${item.url || ""}|${item.style || "primary"}`).join("\n"),
          8
        );
        items.addEventListener("input", () => {
          selected.items = items.value
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean)
            .map((line) => {
              const parts = line.split("|").map((part) => (part || "").trim());
              return {
                label: parts[0] || "",
                url: parts[1] || "",
                style: parts[2] === "secondary" ? "secondary" : "primary",
              };
            });
          changed();
        });
        form.appendChild(field("Buttons (label|url|style)", items));
      } else if (type === "columns") {
        const leftText = textArea(selected.left || "", 6);
        const rightText = textArea(selected.right || "", 6);
        leftText.addEventListener("input", () => {
          selected.left = leftText.value;
          changed();
        });
        rightText.addEventListener("input", () => {
          selected.right = rightText.value;
          changed();
        });
        form.appendChild(field("Left column", leftText));
        form.appendChild(field("Right column", rightText));
      } else if (type === "faq") {
        const question = textInput(selected.question || "");
        const answer = textArea(selected.answer || "", 6);
        question.addEventListener("input", () => {
          selected.question = question.value;
          changed();
        });
        answer.addEventListener("input", () => {
          selected.answer = answer.value;
          changed();
        });
        form.appendChild(field("Question", question));
        form.appendChild(field("Answer", answer));
      } else if (type === "spacer") {
        const height = numberInput(selected.height || 24, 8, 180);
        height.addEventListener("input", () => {
          selected.height = Number(height.value || 24);
          changed();
        });
        form.appendChild(field("Height (px)", height));
      } else if (type === "html") {
        const html = textArea(selected.html || "", 10);
        html.addEventListener("input", () => {
          selected.html = html.value;
          changed();
        });
        form.appendChild(field("HTML", html));
      }
    }

    function renderAll() {
      renderLeft();
      renderCanvas();
      renderInspector();
      sync();
    }

    renderAll();

    const form = source.closest("form");
    if (form) form.addEventListener("submit", sync);
  }

  function init() {
    document.querySelectorAll(SOURCE_SELECTOR).forEach((source) => {
      mountEditor(source);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
