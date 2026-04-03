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
    { value: "cards_slider", label: "Cards Slider", icon: "CS", group: "Design" },
    { value: "columns", label: "Columns", icon: "C", group: "Layout" },
    { value: "rows", label: "Rows", icon: "R", group: "Layout" },
    { value: "faq", label: "FAQ Item", icon: "?", group: "Design" },
    { value: "spacer", label: "Spacer", icon: "S", group: "Layout" },
    { value: "html", label: "Custom HTML", icon: "<>", group: "Advanced" },
  ];

  const GROUPS = ["Text", "Media", "Design", "Layout", "Advanced"];
  const COLUMN_CHILD_TYPES = [
    "paragraph",
    "heading",
    "list",
    "quote",
    "button",
    "buttons",
    "image",
    "embed",
    "cards_slider",
    "faq",
    "spacer",
    "html",
  ];

  function parseJSON(raw) {
    if (!raw || !raw.trim()) return [];
    try {
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed.map(normalizeLegacyBlock);
    } catch (_error) {
      return [];
    }
  }

  function parseCardsLines(raw) {
    if (!raw) return [];
    const text = String(raw).replace(/\r/g, "\n");
    let lines = text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    if (lines.length === 1 && text.split("|").length > 3) {
      const chunks = text
        .split("|")
        .map((chunk) => chunk.trim())
        .filter(Boolean);
      lines = [];
      for (let i = 0; i < chunks.length; i += 2) {
        lines.push(`${chunks[i] || ""}|${chunks[i + 1] || ""}`);
      }
    }

    return lines
      .map((line) => {
        const parts = line.split("|");
        const title = (parts.shift() || "").trim();
        const body = parts.join("|").trim();
        return { title, text: body };
      })
      .filter((item) => item.title || item.text);
  }

  function normalizeNestedBlocks(value) {
    if (Array.isArray(value)) {
      return value
        .filter((item) => item && typeof item === "object")
        .map((item) => normalizeLegacyBlock(item));
    }
    if (typeof value === "string" && value.trim()) {
      return [{ type: "paragraph", text: value.trim() }];
    }
    return [];
  }

  function normalizeRowsLayout(value) {
    if (!Array.isArray(value)) {
      if (typeof value === "string" && value.trim()) {
        return [{ columns: [{ blocks: [{ type: "paragraph", text: value.trim() }] }] }];
      }
      return [];
    }

    return value
      .map((row) => {
        if (typeof row === "string" && row.trim()) {
          return { columns: [{ blocks: [{ type: "paragraph", text: row.trim() }] }] };
        }
        if (!row || typeof row !== "object") return null;

        let columns = [];
        if (Array.isArray(row.columns)) {
          columns = row.columns
            .map((col) => {
              if (!col || typeof col !== "object") return null;
              const blocks = normalizeNestedBlocks(col.blocks ?? col.items ?? col.text ?? "");
              return { blocks: blocks.length ? blocks : [{ type: "paragraph", text: "Column text" }] };
            })
            .filter(Boolean);
        }

        if (!columns.length) {
          const leftBlocks = normalizeNestedBlocks(row.left_blocks ?? row.left ?? "");
          const rightBlocks = normalizeNestedBlocks(row.right_blocks ?? row.right ?? "");
          if (leftBlocks.length) columns.push({ blocks: leftBlocks });
          if (rightBlocks.length) columns.push({ blocks: rightBlocks });
        }

        return columns.length ? { columns } : null;
      })
      .filter(Boolean);
  }

  function normalizeLegacyBlock(block) {
    if (!block || typeof block !== "object") return defaultsFor("paragraph");
    const originalType = String(block.type || "paragraph").trim().toLowerCase();
    if (originalType === "raws" || originalType === "row") {
      block.type = "rows";
    }
    if (originalType === "cards-slider" || originalType === "cards slider" || originalType === "cs_cards_slider") {
      block.type = "cards_slider";
    }

    if (String(block.type || "") === "cards_slider") {
      const source = Array.isArray(block.items) ? block.items : block.items || block.lines || block.line || block.text || "";
      if (!Array.isArray(block.items)) {
        block.items = parseCardsLines(source);
      }
      if (!("title" in block)) block.title = "";
      if (!("subtitle" in block)) block.subtitle = "";
    }

    if (String(block.type || "") === "columns") {
      if (!Array.isArray(block.left_blocks)) {
        block.left_blocks = normalizeNestedBlocks(block.left_blocks ?? block.left);
      }
      if (!Array.isArray(block.right_blocks)) {
        block.right_blocks = normalizeNestedBlocks(block.right_blocks ?? block.right);
      }
      delete block.left;
      delete block.right;
    }

    if (String(block.type || "") === "rows") {
      block.rows = normalizeRowsLayout(block.rows ?? block.items);
      delete block.items;
    }
    return block;
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
        return {
          type,
          left_blocks: [{ type: "paragraph", text: "Left column text" }],
          right_blocks: [{ type: "paragraph", text: "Right column text" }],
        };
      case "rows":
        return {
          type,
          rows: [
            {
              columns: [
                { blocks: [{ type: "heading", level: 3, text: "Column title" }] },
                { blocks: [{ type: "paragraph", text: "Column text" }] },
              ],
            },
          ],
        };
      case "cards_slider":
        return {
          type,
          title: "Why VXcloud",
          subtitle: "Quick reasons clients choose the service.",
          items: [
            { title: "Simple start", text: "Connect in minutes without complex setup." },
            { title: "Clear format", text: "After purchase you immediately get all required access data." },
            { title: "Convenient control", text: "Main actions are available through site and Telegram." },
          ],
        };
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
    if (type === "cards_slider") {
      const count = Array.isArray(block.items) ? block.items.length : 0;
      return `Cards slider (${count})`;
    }
    if (type === "columns") {
      const leftCount = Array.isArray(block.left_blocks) ? block.left_blocks.length : 0;
      const rightCount = Array.isArray(block.right_blocks) ? block.right_blocks.length : 0;
      return `Columns (${leftCount}|${rightCount})`;
    }
    if (type === "rows" || type === "raws") {
      const rows = Array.isArray(block.rows) ? block.rows : [];
      const rowCount = rows.length;
      const colCount = rows.reduce((acc, row) => acc + (Array.isArray(row.columns) ? row.columns.length : 0), 0);
      return `Rows (${rowCount} rows, ${colCount} cols)`;
    }
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
      dragIndex: -1,
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

        const storageKey = `be.group.${group}`;
        const stored = window.localStorage.getItem(storageKey);
        const defaultOpen = group === "Text" || group === "Design";
        const isOpen = stored === null ? defaultOpen : stored === "1";
        if (!isOpen) groupBlock.classList.add("is-collapsed");

        const title = document.createElement("button");
        title.type = "button";
        title.className = "be-library-toggle";
        title.innerHTML = `<span>${group}</span><i>${isOpen ? "-" : "+"}</i>`;

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

        title.addEventListener("click", () => {
          groupBlock.classList.toggle("is-collapsed");
          const open = !groupBlock.classList.contains("is-collapsed");
          title.querySelector("i").textContent = open ? "-" : "+";
          window.localStorage.setItem(storageKey, open ? "1" : "0");
        });

        groupBlock.appendChild(title);
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
        const clearDropMarkers = () => {
          stage.querySelectorAll(".be-canvas-block.is-drop-before, .be-canvas-block.is-drop-after").forEach((el) => {
            el.classList.remove("is-drop-before", "is-drop-after");
          });
        };

        const moveBlockByDrag = (fromIndex, targetIndexRaw) => {
          if (fromIndex < 0 || fromIndex >= state.blocks.length) return;
          let targetIndex = Math.max(0, Math.min(targetIndexRaw, state.blocks.length));
          if (targetIndex === fromIndex || targetIndex === fromIndex + 1) {
            state.dragIndex = -1;
            clearDropMarkers();
            return;
          }
          const moved = state.blocks.splice(fromIndex, 1)[0];
          if (targetIndex > fromIndex) targetIndex -= 1;
          state.blocks.splice(targetIndex, 0, moved);
          state.selectedIndex = targetIndex;
          state.dragIndex = -1;
          renderCanvas();
          renderInspector();
          sync();
        };

        state.blocks.forEach((block, index) => {
          const meta = blockMeta(block.type || "paragraph");
          const card = document.createElement("article");
          card.className = "be-canvas-block";
          if (state.selectedIndex === index) card.classList.add("is-selected");
          card.draggable = true;
          card.innerHTML =
            "<div class='be-canvas-block-top'>" +
            `<span class='be-canvas-type'>${meta.icon} ${meta.label}</span>` +
            `<span class='be-canvas-index'>#${index + 1}</span>` +
            "</div>" +
            "<div class='be-canvas-preview'></div>";
          card.querySelector(".be-canvas-preview").textContent = blockPreview(block);
          card.addEventListener("click", () => selectBlock(index));
          card.addEventListener("dragstart", (event) => {
            state.dragIndex = index;
            card.classList.add("is-dragging");
            if (event.dataTransfer) {
              event.dataTransfer.effectAllowed = "move";
              event.dataTransfer.setData("text/plain", String(index));
            }
          });
          card.addEventListener("dragover", (event) => {
            if (state.dragIndex < 0 || state.dragIndex === index) return;
            event.preventDefault();
            clearDropMarkers();
            const rect = card.getBoundingClientRect();
            const before = event.clientY < rect.top + rect.height / 2;
            card.classList.add(before ? "is-drop-before" : "is-drop-after");
          });
          card.addEventListener("drop", (event) => {
            if (state.dragIndex < 0 || state.dragIndex === index) return;
            event.preventDefault();
            const rect = card.getBoundingClientRect();
            const before = event.clientY < rect.top + rect.height / 2;
            const target = before ? index : index + 1;
            moveBlockByDrag(state.dragIndex, target);
          });
          card.addEventListener("dragend", () => {
            card.classList.remove("is-dragging");
            state.dragIndex = -1;
            clearDropMarkers();
          });
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

      function normalizeColumnItems(value) {
        return normalizeNestedBlocks(value);
      }

      function renderColumnChildFields(item, holder) {
        const type = String(item.type || "paragraph");
        if (type === "paragraph") {
          const text = textArea(item.text || "", 4);
          text.addEventListener("input", () => {
            item.text = text.value;
            changed();
          });
          holder.appendChild(field("Text", text));
          return;
        }
        if (type === "heading") {
          const level = selectInput(
            [
              { value: 1, label: "H1" },
              { value: 2, label: "H2" },
              { value: 3, label: "H3" },
              { value: 4, label: "H4" },
            ],
            item.level || 2
          );
          const text = textInput(item.text || "");
          level.addEventListener("change", () => {
            item.level = Number(level.value);
            changed();
          });
          text.addEventListener("input", () => {
            item.text = text.value;
            changed();
          });
          holder.appendChild(field("Level", level));
          holder.appendChild(field("Text", text));
          return;
        }
        if (type === "list") {
          const ordered = document.createElement("input");
          ordered.type = "checkbox";
          ordered.checked = !!item.ordered;
          ordered.addEventListener("change", () => {
            item.ordered = ordered.checked;
            changed();
          });
          const items = textArea(Array.isArray(item.items) ? item.items.join("\n") : "", 5);
          items.addEventListener("input", () => {
            item.items = items.value
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean);
            changed();
          });
          holder.appendChild(field("Ordered list", ordered));
          holder.appendChild(field("Items (one line = one item)", items));
          return;
        }
        if (type === "quote") {
          const text = textArea(item.text || "", 4);
          const cite = textInput(item.cite || "");
          text.addEventListener("input", () => {
            item.text = text.value;
            changed();
          });
          cite.addEventListener("input", () => {
            item.cite = cite.value;
            changed();
          });
          holder.appendChild(field("Quote", text));
          holder.appendChild(field("Author", cite));
          return;
        }
        if (type === "button") {
          const label = textInput(item.label || "");
          const url = textInput(item.url || "");
          const style = selectInput(
            [
              { value: "primary", label: "Primary" },
              { value: "secondary", label: "Secondary" },
            ],
            item.style || "primary"
          );
          label.addEventListener("input", () => {
            item.label = label.value;
            changed();
          });
          url.addEventListener("input", () => {
            item.url = url.value;
            changed();
          });
          style.addEventListener("change", () => {
            item.style = style.value;
            changed();
          });
          holder.appendChild(field("Button text", label));
          holder.appendChild(field("URL", url));
          holder.appendChild(field("Style", style));
          return;
        }
        if (type === "buttons") {
          const items = textArea(
            (item.items || []).map((btn) => `${btn.label || ""}|${btn.url || ""}|${btn.style || "primary"}`).join("\n"),
            6
          );
          items.addEventListener("input", () => {
            item.items = items.value
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
          holder.appendChild(field("Buttons (label|url|style)", items));
          return;
        }
        if (type === "image") {
          const src = textInput(item.src || "");
          const alt = textInput(item.alt || "");
          const caption = textInput(item.caption || "");
          src.addEventListener("input", () => {
            item.src = src.value;
            changed();
          });
          alt.addEventListener("input", () => {
            item.alt = alt.value;
            changed();
          });
          caption.addEventListener("input", () => {
            item.caption = caption.value;
            changed();
          });
          holder.appendChild(field("Image URL", src));
          holder.appendChild(field("Alt text", alt));
          holder.appendChild(field("Caption", caption));
          return;
        }
        if (type === "embed") {
          const url = textInput(item.url || "");
          url.addEventListener("input", () => {
            item.url = url.value;
            changed();
          });
          holder.appendChild(field("Embed URL", url));
          return;
        }
        if (type === "cards_slider") {
          const title = textInput(item.title || "");
          const subtitle = textArea(item.subtitle || "", 3);
          const initialItems = Array.isArray(item.items)
            ? item.items
            : parseCardsLines(item.items || item.lines || item.line || item.text || "");
          const cards = textArea(initialItems.map((card) => `${card.title || ""}|${card.text || ""}`).join("\n"), 8);
          if (!Array.isArray(item.items)) {
            item.items = initialItems;
          }
          title.addEventListener("input", () => {
            item.title = title.value;
            changed();
          });
          subtitle.addEventListener("input", () => {
            item.subtitle = subtitle.value;
            changed();
          });
          cards.addEventListener("input", () => {
            item.items = parseCardsLines(cards.value);
            changed();
          });
          holder.appendChild(field("Section title", title));
          holder.appendChild(field("Section subtitle", subtitle));
          holder.appendChild(field("Cards (title|text, one per line)", cards));
          return;
        }
        if (type === "faq") {
          const question = textInput(item.question || "");
          const answer = textArea(item.answer || "", 4);
          question.addEventListener("input", () => {
            item.question = question.value;
            changed();
          });
          answer.addEventListener("input", () => {
            item.answer = answer.value;
            changed();
          });
          holder.appendChild(field("Question", question));
          holder.appendChild(field("Answer", answer));
          return;
        }
        if (type === "spacer") {
          const height = numberInput(item.height || 24, 8, 180);
          height.addEventListener("input", () => {
            item.height = Number(height.value || 24);
            changed();
          });
          holder.appendChild(field("Height (px)", height));
          return;
        }
        if (type === "html") {
          const html = textArea(item.html || "", 6);
          html.addEventListener("input", () => {
            item.html = html.value;
            changed();
          });
          holder.appendChild(field("HTML", html));
        }
      }

      function renderColumnEditor(columnBlock, key, labelText) {
        if (!Array.isArray(columnBlock[key])) columnBlock[key] = normalizeColumnItems(columnBlock[key]);
        const list = columnBlock[key];

        const section = document.createElement("section");
        section.className = "be-columns-editor";

        const head = document.createElement("div");
        head.className = "be-columns-editor-head";
        const title = document.createElement("strong");
        title.textContent = labelText;
        const addWrap = document.createElement("div");
        addWrap.className = "be-columns-add";
        const addType = selectInput(
          COLUMN_CHILD_TYPES.map((childType) => {
            const meta = blockMeta(childType);
            return { value: childType, label: meta.label };
          }),
          "paragraph"
        );
        const addBtn = document.createElement("button");
        addBtn.type = "button";
        addBtn.className = "button";
        addBtn.textContent = "Add";
        addBtn.addEventListener("click", () => {
          list.push(defaultsFor(addType.value));
          changed();
        });
        addWrap.appendChild(addType);
        addWrap.appendChild(addBtn);
        head.appendChild(title);
        head.appendChild(addWrap);
        section.appendChild(head);

        if (!list.length) {
          const empty = document.createElement("p");
          empty.className = "be-columns-empty";
          empty.textContent = "No blocks in this column.";
          section.appendChild(empty);
          return section;
        }

        list.forEach((item, index) => {
          const block = normalizeLegacyBlock(item);
          list[index] = block;
          const itemType = String(block.type || "paragraph");

          const card = document.createElement("article");
          card.className = "be-columns-item";

          const bar = document.createElement("div");
          bar.className = "be-columns-item-top";
          const num = document.createElement("span");
          num.textContent = `#${index + 1}`;
          num.className = "be-columns-index";
          const typeSelect = selectInput(
            COLUMN_CHILD_TYPES.map((childType) => {
              const meta = blockMeta(childType);
              return { value: childType, label: meta.label };
            }),
            itemType
          );
          typeSelect.addEventListener("change", () => {
            list[index] = defaultsFor(typeSelect.value);
            changed();
          });

          const up = document.createElement("button");
          up.type = "button";
          up.className = "button";
          up.textContent = "Up";
          up.disabled = index === 0;
          up.addEventListener("click", () => {
            if (index < 1) return;
            const tmp = list[index - 1];
            list[index - 1] = list[index];
            list[index] = tmp;
            changed();
          });

          const down = document.createElement("button");
          down.type = "button";
          down.className = "button";
          down.textContent = "Down";
          down.disabled = index === list.length - 1;
          down.addEventListener("click", () => {
            if (index >= list.length - 1) return;
            const tmp = list[index + 1];
            list[index + 1] = list[index];
            list[index] = tmp;
            changed();
          });

          const remove = document.createElement("button");
          remove.type = "button";
          remove.className = "button deletelink";
          remove.textContent = "Delete";
          remove.addEventListener("click", () => {
            list.splice(index, 1);
            changed();
          });

          bar.appendChild(num);
          bar.appendChild(typeSelect);
          bar.appendChild(up);
          bar.appendChild(down);
          bar.appendChild(remove);
          card.appendChild(bar);

          const body = document.createElement("div");
          body.className = "be-columns-item-body";
          renderColumnChildFields(block, body);
          card.appendChild(body);
          section.appendChild(card);
        });

        return section;
      }

      function defaultRowColumn() {
        return { blocks: [{ type: "paragraph", text: "Column text" }] };
      }

      function normalizeRowItem(row) {
        if (!row || typeof row !== "object") return { columns: [defaultRowColumn()] };
        const columns = Array.isArray(row.columns)
          ? row.columns
              .map((col) => {
                if (!col || typeof col !== "object") return null;
                const blocks = normalizeColumnItems(col.blocks ?? col.items ?? col.text ?? "");
                return { blocks: blocks.length ? blocks : [{ type: "paragraph", text: "Column text" }] };
              })
              .filter(Boolean)
          : [];
        return { columns: columns.length ? columns : [defaultRowColumn()] };
      }

      function renderRowsEditor(rowsBlock) {
        if (!Array.isArray(rowsBlock.rows)) rowsBlock.rows = normalizeRowsLayout(rowsBlock.rows ?? rowsBlock.items);
        delete rowsBlock.items;

        const section = document.createElement("section");
        section.className = "be-rows-editor";

        const head = document.createElement("div");
        head.className = "be-rows-editor-head";
        const title = document.createElement("strong");
        title.textContent = "Rows layout";
        const addRowBtn = document.createElement("button");
        addRowBtn.type = "button";
        addRowBtn.className = "button";
        addRowBtn.textContent = "Add row";
        addRowBtn.addEventListener("click", () => {
          rowsBlock.rows.push({ columns: [defaultRowColumn(), defaultRowColumn()] });
          changed();
        });
        head.appendChild(title);
        head.appendChild(addRowBtn);
        section.appendChild(head);

        if (!rowsBlock.rows.length) {
          const empty = document.createElement("p");
          empty.className = "be-columns-empty";
          empty.textContent = "No rows yet.";
          section.appendChild(empty);
          return section;
        }

        rowsBlock.rows.forEach((row, rowIndex) => {
          const normalizedRow = normalizeRowItem(row);
          rowsBlock.rows[rowIndex] = normalizedRow;

          const rowCard = document.createElement("article");
          rowCard.className = "be-row-item";

          const rowTop = document.createElement("div");
          rowTop.className = "be-row-item-top";
          const rowLabel = document.createElement("strong");
          rowLabel.textContent = `Row #${rowIndex + 1}`;
          const rowButtons = document.createElement("div");
          rowButtons.className = "be-row-actions";

          const addColumnBtn = document.createElement("button");
          addColumnBtn.type = "button";
          addColumnBtn.className = "button";
          addColumnBtn.textContent = "+ Column";
          addColumnBtn.addEventListener("click", () => {
            normalizedRow.columns.push(defaultRowColumn());
            changed();
          });

          const rowUp = document.createElement("button");
          rowUp.type = "button";
          rowUp.className = "button";
          rowUp.textContent = "Up";
          rowUp.disabled = rowIndex === 0;
          rowUp.addEventListener("click", () => {
            if (rowIndex < 1) return;
            const tmp = rowsBlock.rows[rowIndex - 1];
            rowsBlock.rows[rowIndex - 1] = rowsBlock.rows[rowIndex];
            rowsBlock.rows[rowIndex] = tmp;
            changed();
          });

          const rowDown = document.createElement("button");
          rowDown.type = "button";
          rowDown.className = "button";
          rowDown.textContent = "Down";
          rowDown.disabled = rowIndex === rowsBlock.rows.length - 1;
          rowDown.addEventListener("click", () => {
            if (rowIndex >= rowsBlock.rows.length - 1) return;
            const tmp = rowsBlock.rows[rowIndex + 1];
            rowsBlock.rows[rowIndex + 1] = rowsBlock.rows[rowIndex];
            rowsBlock.rows[rowIndex] = tmp;
            changed();
          });

          const rowRemove = document.createElement("button");
          rowRemove.type = "button";
          rowRemove.className = "button deletelink";
          rowRemove.textContent = "Delete";
          rowRemove.addEventListener("click", () => {
            rowsBlock.rows.splice(rowIndex, 1);
            changed();
          });

          rowButtons.appendChild(addColumnBtn);
          rowButtons.appendChild(rowUp);
          rowButtons.appendChild(rowDown);
          rowButtons.appendChild(rowRemove);
          rowTop.appendChild(rowLabel);
          rowTop.appendChild(rowButtons);
          rowCard.appendChild(rowTop);

          const columnsGrid = document.createElement("div");
          columnsGrid.className = "be-row-columns";

          normalizedRow.columns.forEach((column, colIndex) => {
            const colCard = document.createElement("div");
            colCard.className = "be-row-column";

            const colTop = document.createElement("div");
            colTop.className = "be-row-column-top";
            const colLabel = document.createElement("span");
            colLabel.textContent = `Column ${colIndex + 1}`;

            const colActions = document.createElement("div");
            colActions.className = "be-row-actions";

            const colLeft = document.createElement("button");
            colLeft.type = "button";
            colLeft.className = "button";
            colLeft.textContent = "Left";
            colLeft.disabled = colIndex === 0;
            colLeft.addEventListener("click", () => {
              if (colIndex < 1) return;
              const tmp = normalizedRow.columns[colIndex - 1];
              normalizedRow.columns[colIndex - 1] = normalizedRow.columns[colIndex];
              normalizedRow.columns[colIndex] = tmp;
              changed();
            });

            const colRight = document.createElement("button");
            colRight.type = "button";
            colRight.className = "button";
            colRight.textContent = "Right";
            colRight.disabled = colIndex === normalizedRow.columns.length - 1;
            colRight.addEventListener("click", () => {
              if (colIndex >= normalizedRow.columns.length - 1) return;
              const tmp = normalizedRow.columns[colIndex + 1];
              normalizedRow.columns[colIndex + 1] = normalizedRow.columns[colIndex];
              normalizedRow.columns[colIndex] = tmp;
              changed();
            });

            const colRemove = document.createElement("button");
            colRemove.type = "button";
            colRemove.className = "button deletelink";
            colRemove.textContent = "Delete";
            colRemove.disabled = normalizedRow.columns.length <= 1;
            colRemove.addEventListener("click", () => {
              if (normalizedRow.columns.length <= 1) return;
              normalizedRow.columns.splice(colIndex, 1);
              changed();
            });

            colActions.appendChild(colLeft);
            colActions.appendChild(colRight);
            colActions.appendChild(colRemove);
            colTop.appendChild(colLabel);
            colTop.appendChild(colActions);
            colCard.appendChild(colTop);

            colCard.appendChild(renderColumnEditor(column, "blocks", "Blocks"));
            columnsGrid.appendChild(colCard);
          });

          rowCard.appendChild(columnsGrid);
          section.appendChild(rowCard);
        });

        return section;
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
        if (!Array.isArray(selected.left_blocks)) selected.left_blocks = normalizeColumnItems(selected.left_blocks ?? selected.left);
        if (!Array.isArray(selected.right_blocks)) selected.right_blocks = normalizeColumnItems(selected.right_blocks ?? selected.right);
        delete selected.left;
        delete selected.right;
        form.appendChild(renderColumnEditor(selected, "left_blocks", "Left column"));
        form.appendChild(renderColumnEditor(selected, "right_blocks", "Right column"));
      } else if (type === "rows" || type === "raws") {
        form.appendChild(renderRowsEditor(selected));
      } else if (type === "cards_slider") {
        const title = textInput(selected.title || "");
        const subtitle = textArea(selected.subtitle || "", 4);
        subtitle.placeholder = "Короткое описание секции карточек";
        const initialItems = Array.isArray(selected.items)
          ? selected.items
          : parseCardsLines(selected.items || selected.lines || selected.line || selected.text || "");
        const items = textArea(
          initialItems.map((item) => `${item.title || ""}|${item.text || ""}`).join("\n"),
          10
        );
        if (!Array.isArray(selected.items)) {
          selected.items = initialItems;
        }
        items.placeholder = "Заголовок карточки|Текст карточки";
        title.addEventListener("input", () => {
          selected.title = title.value;
          changed();
        });
        subtitle.addEventListener("input", () => {
          selected.subtitle = subtitle.value;
          changed();
        });
        items.addEventListener("input", () => {
          selected.items = parseCardsLines(items.value);
          changed();
        });
        form.appendChild(field("Section title", title));
        form.appendChild(field("Section subtitle", subtitle));
        form.appendChild(field("Cards (title|text, one card per line)", items, "Каждая строка = одна карточка."));
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
