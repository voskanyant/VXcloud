(function () {
  const SOURCE_SELECTORS = [
    "textarea.js-block-editor-source",
    "textarea#id_content_blocks",
    "textarea[name='content_blocks']",
  ];

  const BLOCK_TYPES = [
    { value: "bs_paragraph", label: "Bootstrap Paragraph", icon: "P", group: "Bootstrap Content" },
    { value: "bs_heading", label: "Bootstrap Heading", icon: "H", group: "Bootstrap Content" },
    { value: "bs_list", label: "Bootstrap List", icon: "L", group: "Bootstrap Content" },
    { value: "bs_quote", label: "Bootstrap Quote", icon: "Q", group: "Bootstrap Content" },
    { value: "bs_image", label: "Bootstrap Image", icon: "I", group: "Bootstrap Content" },
    { value: "bs_embed", label: "Bootstrap Embed", icon: "E", group: "Bootstrap Content" },
    { value: "bs_button", label: "Bootstrap Button", icon: "B", group: "Bootstrap Content" },
    { value: "bs_button_group", label: "Bootstrap Button Group", icon: "BG", group: "Bootstrap Content" },
    { value: "bs_cards_slider", label: "Bootstrap Cards Slider", icon: "CS", group: "Bootstrap Components" },
    { value: "bs_alert", label: "Bootstrap Alert", icon: "AL", group: "Bootstrap Components" },
    { value: "bs_badge", label: "Bootstrap Badge", icon: "BD", group: "Bootstrap Components" },
    { value: "bs_card", label: "Bootstrap Card", icon: "CD", group: "Bootstrap Components" },
    { value: "bs_accordion", label: "Bootstrap Accordion", icon: "AC", group: "Bootstrap Components" },
    { value: "bs_tabs", label: "Bootstrap Tabs", icon: "TB", group: "Bootstrap Components" },
    { value: "bs_table", label: "Bootstrap Table", icon: "TR", group: "Bootstrap Components" },
    { value: "bs_list_group", label: "Bootstrap List Group", icon: "LG", group: "Bootstrap Components" },
    { value: "bs_progress", label: "Bootstrap Progress", icon: "PR", group: "Bootstrap Components" },
    { value: "bs_breadcrumb", label: "Bootstrap Breadcrumb", icon: "BR", group: "Bootstrap Components" },
    { value: "bs_pagination", label: "Bootstrap Pagination", icon: "PG", group: "Bootstrap Components" },
    { value: "bs_collapse", label: "Bootstrap Collapse", icon: "CP", group: "Bootstrap Components" },
    { value: "bs_spinner", label: "Bootstrap Spinner", icon: "SP", group: "Bootstrap Components" },
    { value: "bs_carousel", label: "Bootstrap Carousel", icon: "CR", group: "Bootstrap Components" },
    { value: "bs_nav", label: "Bootstrap Nav", icon: "NV", group: "Bootstrap Components" },
    { value: "bs_modal", label: "Bootstrap Modal", icon: "MO", group: "Bootstrap Components" },
    { value: "bs_toast", label: "Bootstrap Toast", icon: "TS", group: "Bootstrap Components" },
    { value: "bs_offcanvas", label: "Bootstrap Offcanvas", icon: "OF", group: "Bootstrap Components" },
    { value: "bs_timeline", label: "Bootstrap Timeline", icon: "TL", group: "Bootstrap Components" },
    { value: "bs_pricing_table", label: "Bootstrap Pricing", icon: "PT", group: "Bootstrap Components" },
    { value: "bs_faq", label: "Bootstrap FAQ Item", icon: "?", group: "Bootstrap Components" },
    { value: "bs_divider", label: "Bootstrap Divider", icon: "DV", group: "Bootstrap Components" },
    { value: "bs_dropdown", label: "Bootstrap Dropdown", icon: "DD", group: "Bootstrap Components" },
    { value: "bs_navbar", label: "Bootstrap Navbar", icon: "NB", group: "Bootstrap Components" },
    { value: "bs_ratio", label: "Bootstrap Ratio", icon: "RT", group: "Bootstrap Components" },
    { value: "bs_placeholder", label: "Bootstrap Placeholder", icon: "PH", group: "Bootstrap Components" },
    { value: "bs_container", label: "Bootstrap Container", icon: "CT", group: "Bootstrap Layout" },
    { value: "bs_rows", label: "Bootstrap Rows", icon: "R", group: "Bootstrap Layout" },
    { value: "bs_columns", label: "Bootstrap Columns", icon: "C", group: "Bootstrap Layout" },
    { value: "bs_spacer", label: "Bootstrap Spacer", icon: "S", group: "Bootstrap Layout" },
  ];

  const GROUPS = ["Bootstrap Content", "Bootstrap Components", "Bootstrap Layout"];
  const COLUMN_CHILD_TYPES = [
    "bs_paragraph",
    "bs_heading",
    "bs_list",
    "bs_quote",
    "bs_button",
    "bs_button_group",
    "bs_image",
    "bs_embed",
    "bs_cards_slider",
    "bs_alert",
    "bs_badge",
    "bs_card",
    "bs_accordion",
    "bs_tabs",
    "bs_table",
    "bs_list_group",
    "bs_progress",
    "bs_breadcrumb",
    "bs_pagination",
    "bs_collapse",
    "bs_spinner",
    "bs_carousel",
    "bs_nav",
    "bs_modal",
    "bs_toast",
    "bs_offcanvas",
    "bs_timeline",
    "bs_pricing_table",
    "bs_dropdown",
    "bs_navbar",
    "bs_ratio",
    "bs_placeholder",
    "bs_faq",
    "bs_divider",
    "bs_container",
    "bs_rows",
    "bs_columns",
    "bs_spacer",
  ];

  const LEGACY_TO_BOOTSTRAP_TYPE = {
    paragraph: "bs_paragraph",
    heading: "bs_heading",
    list: "bs_list",
    quote: "bs_quote",
    image: "bs_image",
    embed: "bs_embed",
    button: "bs_button",
    buttons: "bs_button_group",
    cards_slider: "bs_cards_slider",
    "cards-slider": "bs_cards_slider",
    "cards slider": "bs_cards_slider",
    cs_cards_slider: "bs_cards_slider",
    faq: "bs_faq",
    spacer: "bs_spacer",
    html: "bs_html",
    rows: "bs_rows",
    row: "bs_rows",
    raws: "bs_rows",
    columns: "bs_columns",
  };

  const BOOTSTRAP_TO_LEGACY_TYPE = {
    bs_paragraph: "paragraph",
    bs_heading: "heading",
    bs_list: "list",
    bs_quote: "quote",
    bs_image: "image",
    bs_embed: "embed",
    bs_button: "button",
    bs_button_group: "buttons",
    bs_cards_slider: "cards_slider",
    bs_faq: "faq",
    bs_spacer: "spacer",
    bs_html: "html",
    bs_container: "rows",
    bs_rows: "rows",
    bs_columns: "rows",
  };

  function toBootstrapType(value) {
    const type = String(value || "bs_paragraph").trim().toLowerCase();
    return LEGACY_TO_BOOTSTRAP_TYPE[type] || type;
  }

  function toLegacyType(value) {
    const type = String(value || "bs_paragraph").trim().toLowerCase();
    return BOOTSTRAP_TO_LEGACY_TYPE[type] || type;
  }

  function safeStorageGet(key) {
    try {
      if (!window.localStorage) return null;
      return window.localStorage.getItem(key);
    } catch (_error) {
      return null;
    }
  }

  function safeStorageSet(key, value) {
    try {
      if (!window.localStorage) return;
      window.localStorage.setItem(key, value);
    } catch (_error) {
      // ignore storage errors (privacy mode / blocked storage)
    }
  }

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

  function parseTitleTextLines(raw) {
    if (!raw) return [];
    return String(raw)
      .replace(/\r/g, "\n")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const parts = line.split("|");
        return {
          title: (parts.shift() || "").trim(),
          text: parts.join("|").trim(),
        };
      })
      .filter((item) => item.title || item.text);
  }

  function parseTimelineLines(raw) {
    if (!raw) return [];
    return String(raw)
      .replace(/\r/g, "\n")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const parts = line.split("|").map((part) => part.trim());
        return {
          date: parts[0] || "",
          title: parts[1] || "",
          text: parts.slice(2).join("|"),
        };
      })
      .filter((item) => item.title || item.text);
  }

  function parsePricingLines(raw) {
    if (!raw) return [];
    return String(raw)
      .replace(/\r/g, "\n")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const parts = line.split("|").map((part) => part.trim());
        const featureText = parts[3] || "";
        return {
          title: parts[0] || "",
          price: parts[1] || "",
          period: parts[2] || "",
          features: featureText
            .split(";")
            .map((item) => item.trim())
            .filter(Boolean),
          button_label: parts[4] || "Choose",
          button_url: parts[5] || "#",
          recommended: String(parts[6] || "").toLowerCase() === "recommended",
        };
      })
      .filter((item) => item.title || item.price || item.features.length);
  }

  function parseCsvLine(line) {
    return String(line || "")
      .split("|")
      .map((part) => part.trim())
      .filter((part) => part !== "");
  }

  function normalizeNestedBlocks(value) {
    if (Array.isArray(value)) {
      return value
        .filter((item) => item && typeof item === "object")
        .map((item) => normalizeLegacyBlock(item));
    }
    if (typeof value === "string" && value.trim()) {
      return [{ type: "bs_paragraph", text: value.trim() }];
    }
    return [];
  }

  function normalizeRowsLayout(value) {
    if (!Array.isArray(value)) {
      if (typeof value === "string" && value.trim()) {
        return [{ columns: [{ blocks: [{ type: "bs_paragraph", text: value.trim() }] }] }];
      }
      return [];
    }

    return value
      .map((row) => {
        if (typeof row === "string" && row.trim()) {
          return { columns: [{ blocks: [{ type: "bs_paragraph", text: row.trim() }] }] };
        }
        if (!row || typeof row !== "object") return null;

        let columns = [];
        if (Array.isArray(row.columns)) {
          columns = row.columns
            .map((col) => {
              if (!col || typeof col !== "object") return null;
              const blocks = normalizeNestedBlocks(col.blocks ?? col.items ?? col.text ?? "");
              return {
                width: Number(col.width || 6) || 6,
                blocks: blocks.length ? blocks : [{ type: "bs_paragraph", text: "Column text" }],
              };
            })
            .filter(Boolean);
        }

        if (!columns.length) {
          const leftBlocks = normalizeNestedBlocks(row.left_blocks ?? row.left ?? "");
          const rightBlocks = normalizeNestedBlocks(row.right_blocks ?? row.right ?? "");
          if (leftBlocks.length) columns.push({ width: 6, blocks: leftBlocks });
          if (rightBlocks.length) columns.push({ width: 6, blocks: rightBlocks });
        }

        return columns.length ? { columns } : null;
      })
      .filter(Boolean);
  }

  function normalizeLegacyBlock(block) {
    if (!block || typeof block !== "object") return defaultsFor("bs_paragraph");
    const originalType = String(block.type || "bs_paragraph").trim().toLowerCase();

    if (originalType === "columns") {
      const leftBlocks = normalizeNestedBlocks(block.left_blocks ?? block.left ?? "");
      const rightBlocks = normalizeNestedBlocks(block.right_blocks ?? block.right ?? "");
      return {
        type: "bs_columns",
        rows: [
          {
            gutter: 3,
            align: "start",
            columns: [
              { width: 6, blocks: leftBlocks.length ? leftBlocks : [{ type: "bs_paragraph", text: "Left column text" }] },
              { width: 6, blocks: rightBlocks.length ? rightBlocks : [{ type: "bs_paragraph", text: "Right column text" }] },
            ],
          },
        ],
      };
    }

    block.type = toBootstrapType(originalType);

    if (String(block.type || "") === "bs_cards_slider") {
      const source = Array.isArray(block.items) ? block.items : block.items || block.lines || block.line || block.text || "";
      if (!Array.isArray(block.items)) {
        block.items = parseCardsLines(source);
      }
      if (!("title" in block)) block.title = "";
      if (!("subtitle" in block)) block.subtitle = "";
    }

    if (String(block.type || "") === "bs_container" || String(block.type || "") === "bs_rows" || String(block.type || "") === "bs_columns") {
      block.rows = normalizeRowsLayout(block.rows ?? block.items);
      delete block.items;
    }
    if (String(block.type || "") === "bs_accordion") {
      if (!Array.isArray(block.items)) {
        block.items = parseTitleTextLines(block.items || "");
      }
      block.flush = !!block.flush;
    }
    if (String(block.type || "") === "bs_tabs") {
      if (!Array.isArray(block.items)) {
        block.items = parseTitleTextLines(block.items || "");
      }
      block.style = String(block.style || "tabs");
    }
    if (String(block.type || "") === "bs_table") {
      if (!Array.isArray(block.headers)) {
        block.headers = parseCsvLine(block.headers || "");
      }
      if (!Array.isArray(block.rows)) {
        block.rows = String(block.rows || "")
          .replace(/\r/g, "\n")
          .split("\n")
          .map((line) => parseCsvLine(line))
          .filter((row) => row.length);
      }
      block.striped = block.striped !== false;
      block.hover = block.hover !== false;
      block.bordered = !!block.bordered;
    }
    if (String(block.type || "") === "bs_list_group") {
      if (!Array.isArray(block.items)) {
        block.items = String(block.items || "")
          .replace(/\r/g, "\n")
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean);
      }
      block.numbered = !!block.numbered;
      block.flush = !!block.flush;
    }
    if (String(block.type || "") === "bs_progress") {
      const value = Number(block.value || 0);
      block.value = Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0;
      block.label = String(block.label || "");
      block.variant = String(block.variant || "primary");
      block.striped = !!block.striped;
      block.animated = !!block.animated;
    }
    if (String(block.type || "") === "bs_breadcrumb") {
      const items = Array.isArray(block.items) ? block.items : parseTitleTextLines(block.items || "");
      block.items = items.map((item, idx) => ({
        label: String(item.title || item.label || ""),
        url: String(item.text || item.url || ""),
        active: !!item.active || idx === items.length - 1,
      }));
    }
    if (String(block.type || "") === "bs_pagination") {
      const items = Array.isArray(block.items) ? block.items : parseTitleTextLines(block.items || "");
      block.items = items.map((item) => ({
        label: String(item.label || item.title || ""),
        url: String(item.url || item.text || ""),
        active: !!item.active,
        disabled: !!item.disabled,
      }));
      block.size = String(block.size || "");
      block.align = String(block.align || "start");
    }
    if (String(block.type || "") === "bs_collapse") {
      block.button_text = String(block.button_text || "Toggle content");
      block.text = String(block.text || "");
      block.variant = String(block.variant || "primary");
      block.open = !!block.open;
    }
    if (String(block.type || "") === "bs_spinner") {
      block.spinner_type = String(block.spinner_type || "border");
      block.variant = String(block.variant || "primary");
      block.size = String(block.size || "");
      block.label = String(block.label || "Loading...");
    }
    if (String(block.type || "") === "bs_carousel") {
      const items = Array.isArray(block.items) ? block.items : parseTitleTextLines(block.items || "");
      block.items = items.map((item) => ({
        image: String(item.image || item.url || item.src || ""),
        title: String(item.title || ""),
        caption: String(item.caption || item.text || ""),
        alt: String(item.alt || ""),
      }));
      block.controls = block.controls !== false;
      block.indicators = block.indicators !== false;
      block.fade = !!block.fade;
      block.auto = !!block.auto;
    }
    if (String(block.type || "") === "bs_nav") {
      const items = Array.isArray(block.items) ? block.items : parseTitleTextLines(block.items || "");
      block.items = items.map((item) => ({
        label: String(item.label || item.title || ""),
        url: String(item.url || item.text || ""),
        active: !!item.active,
      }));
      block.style = String(block.style || "tabs");
      block.fill = !!block.fill;
      block.justified = !!block.justified;
      block.vertical = !!block.vertical;
    }
    if (String(block.type || "") === "bs_modal") {
      block.button_text = String(block.button_text || "Open modal");
      block.button_variant = String(block.button_variant || "primary");
      block.title = String(block.title || "Modal title");
      block.text = String(block.text || "");
      block.size = String(block.size || "");
      block.scrollable = !!block.scrollable;
      block.centered = !!block.centered;
      block.fullscreen = !!block.fullscreen;
      block.footer_primary_text = String(block.footer_primary_text || "Got it");
      block.footer_secondary_text = String(block.footer_secondary_text || "Close");
    }
    if (String(block.type || "") === "bs_toast") {
      block.title = String(block.title || "Notification");
      block.text = String(block.text || "");
      block.delay = Number(block.delay || 5000) || 5000;
      block.autohide = block.autohide !== false;
      block.variant = String(block.variant || "primary");
    }
    if (String(block.type || "") === "bs_offcanvas") {
      block.button_text = String(block.button_text || "Open panel");
      block.button_variant = String(block.button_variant || "primary");
      block.title = String(block.title || "Panel");
      block.text = String(block.text || "");
      block.placement = String(block.placement || "end");
    }
    if (String(block.type || "") === "bs_timeline") {
      block.title = String(block.title || "");
      if (!Array.isArray(block.items)) {
        block.items = parseTimelineLines(block.items || "");
      }
    }
    if (String(block.type || "") === "bs_pricing_table") {
      block.title = String(block.title || "Pricing plans");
      block.subtitle = String(block.subtitle || "");
      if (!Array.isArray(block.plans)) {
        block.plans = parsePricingLines(block.plans || "");
      }
    }
    return block;
  }

  function defaultsFor(type) {
    const bsType = toBootstrapType(type || "bs_paragraph");
    const kind = toLegacyType(bsType);

    switch (kind) {
      case "heading":
        return { type: bsType, level: 2, text: "New heading" };
      case "list":
        return { type: bsType, ordered: false, items: ["Item 1", "Item 2"] };
      case "quote":
        return { type: bsType, text: "Quote text", cite: "" };
      case "image":
        return { type: bsType, src: "", alt: "", caption: "" };
      case "embed":
        return { type: bsType, url: "" };
      case "button":
        return { type: bsType, label: "Buy access", url: "/account/buy/", style: "primary" };
      case "buttons":
        return {
          type: bsType,
          items: [
            { label: "Buy access", url: "/account/buy/", style: "primary" },
            { label: "Renew", url: "/account/renew/", style: "secondary" },
          ],
        };
      case "rows":
        if (bsType === "bs_columns") {
          return {
            type: bsType,
            rows: [
              {
                gutter: 3,
                align: "start",
                columns: [
                  { width: 6, blocks: [{ type: "bs_heading", level: 3, text: "Column title" }] },
                  { width: 6, blocks: [{ type: "bs_paragraph", text: "Column text" }] },
                ],
              },
            ],
          };
        }
        return {
          type: bsType,
          rows: [
            {
              gutter: 3,
              align: "start",
              columns: [
                { width: 6, blocks: [{ type: "bs_heading", level: 3, text: "Column title" }] },
                { width: 6, blocks: [{ type: "bs_paragraph", text: "Column text" }] },
              ],
            },
          ],
        };
      case "cards_slider":
        return {
          type: bsType,
          title: "Why VXcloud",
          subtitle: "Quick reasons clients choose the service.",
          items: [
            { title: "Simple start", text: "Connect in minutes without complex setup." },
            { title: "Clear format", text: "After purchase you immediately get all required access data." },
            { title: "Convenient control", text: "Main actions are available through site and Telegram." },
          ],
        };
      case "faq":
        return { type: bsType, question: "Question", answer: "Answer" };
      case "spacer":
        return { type: bsType, height: 24 };
      case "html":
        return { type: bsType, html: "<div></div>" };
      case "bs_alert":
        return { type: bsType, variant: "info", title: "Important", text: "Alert text for users." };
      case "bs_badge":
        return { type: bsType, variant: "primary", text: "New", pill: true };
      case "bs_card":
        return {
          type: bsType,
          title: "Card title",
          text: "Card text. Explain an important point briefly.",
          image: "",
          button_label: "Details",
          button_url: "/",
          button_style: "primary",
        };
      case "bs_accordion":
        return {
          type: bsType,
          flush: false,
          items: [
            { title: "Question 1", text: "Answer to the first question." },
            { title: "Question 2", text: "Answer to the second question." },
          ],
        };
      case "bs_tabs":
        return {
          type: bsType,
          style: "tabs",
          items: [
            { title: "iOS", text: "iOS setup guide." },
            { title: "Android", text: "Android setup guide." },
          ],
        };
      case "bs_table":
        return {
          type: bsType,
          headers: ["Plan", "Duration", "Price"],
          rows: [
            ["Basic", "30 days", "10 Stars"],
            ["Extended", "90 days", "27 Stars"],
          ],
          striped: true,
          hover: true,
          bordered: false,
        };
      case "bs_list_group":
        return { type: bsType, numbered: false, flush: false, items: ["Item 1", "Item 2", "Item 3"] };
      case "bs_progress":
        return { type: bsType, value: 65, label: "65%", variant: "primary", striped: false, animated: false };
      case "bs_breadcrumb":
        return {
          type: bsType,
          items: [
            { label: "Home", url: "/", active: false },
            { label: "Guides", url: "/guides/", active: false },
            { label: "Current page", url: "", active: true },
          ],
        };
      case "bs_pagination":
        return {
          type: bsType,
          size: "",
          align: "start",
          items: [
            { label: "Prev", url: "#", disabled: true },
            { label: "1", url: "#", active: true },
            { label: "2", url: "#", active: false },
            { label: "3", url: "#", active: false },
            { label: "Next", url: "#", active: false },
          ],
        };
      case "bs_collapse":
        return {
          type: bsType,
          button_text: "Show details",
          text: "Collapsed content for additional instructions.",
          variant: "primary",
          open: false,
        };
      case "bs_spinner":
        return { type: bsType, spinner_type: "border", variant: "primary", size: "", label: "Loading..." };
      case "bs_carousel":
        return {
          type: bsType,
          controls: true,
          indicators: true,
          fade: false,
          auto: false,
          items: [
            {
              image: "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
              title: "Step 1",
              caption: "Purchase a subscription.",
              alt: "Step 1",
            },
            {
              image: "https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=1200&q=80",
              title: "Step 2",
              caption: "Get your config.",
              alt: "Step 2",
            },
          ],
        };
      case "bs_nav":
        return {
          type: bsType,
          style: "tabs",
          fill: false,
          justified: false,
          vertical: false,
          items: [
            { label: "iOS", url: "#", active: true },
            { label: "Android", url: "#", active: false },
            { label: "Windows", url: "#", active: false },
          ],
        };
      case "bs_modal":
        return {
          type: bsType,
          button_text: "Open details",
          button_variant: "primary",
          title: "Connection details",
          text: "Detailed instructions and access information.",
          size: "",
          scrollable: false,
          centered: true,
          fullscreen: false,
          footer_primary_text: "OK",
          footer_secondary_text: "Close",
        };
      case "bs_toast":
        return {
          type: bsType,
          title: "Notification",
          text: "Your order has been accepted.",
          delay: 5000,
          autohide: true,
          variant: "primary",
        };
      case "bs_offcanvas":
        return {
          type: bsType,
          button_text: "Open panel",
          button_variant: "primary",
          title: "Quick actions",
          text: "Place useful links and helper instructions here.",
          placement: "end",
        };
      case "bs_timeline":
        return {
          type: bsType,
          title: "How it works",
          items: [
            { date: "Step 1", title: "Purchase", text: "Choose a plan and complete payment." },
            { date: "Step 2", title: "Connect", text: "Receive config and set up your app." },
            { date: "Step 3", title: "Use", text: "Use the service on your selected device." },
          ],
        };
      case "bs_pricing_table":
        return {
          type: bsType,
          title: "VXcloud plans",
          subtitle: "Choose the plan that fits your scenario.",
          plans: [
            {
              title: "Start",
              price: "10 Stars",
              period: "30 days",
              features: ["1 device", "Standard speed", "Support"],
              button_label: "Choose",
              button_url: "/account/buy/",
              recommended: false,
            },
            {
              title: "Pro",
              price: "27 Stars",
              period: "90 days",
              features: ["1 device", "Best value", "Priority support"],
              button_label: "Choose Pro",
              button_url: "/account/buy/",
              recommended: true,
            },
          ],
        };
      case "bs_dropdown":
        return {
          type: bsType,
          button_text: "Menu",
          button_variant: "primary",
          align: "",
          items: [
            { label: "Action", url: "#" },
            { label: "Another action", url: "#" },
            { label: "Separated link", url: "#", divider_before: true },
          ],
        };
      case "bs_navbar":
        return {
          type: bsType,
          brand: "VXcloud",
          brand_url: "/",
          expand: "lg",
          theme: "dark",
          bg: "dark",
          items: [
            { label: "Home", url: "/" },
            { label: "Instructions", url: "/instructions/" },
            { label: "Account", url: "/account/" },
          ],
        };
      case "bs_ratio":
        return {
          type: bsType,
          ratio: "16x9",
          html: '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" title="Video" allowfullscreen></iframe>',
        };
      case "bs_placeholder":
        return {
          type: bsType,
          lines: 3,
          width: 100,
          size: "md",
          glow: false,
        };
      case "bs_divider":
        return { type: bsType, spacing: 24, label: "" };
      default:
        return { type: bsType, text: "New paragraph" };
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
    const type = toLegacyType(block.type || "bs_paragraph");
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
    if (type === "bs_alert") return `${block.variant || "info"} alert`;
    if (type === "bs_badge") return `${block.text || "Badge"}`;
    if (type === "bs_card") return `${block.title || "Card"}`;
    if (type === "bs_accordion") return `Accordion (${Array.isArray(block.items) ? block.items.length : 0})`;
    if (type === "bs_tabs") return `Tabs (${Array.isArray(block.items) ? block.items.length : 0})`;
    if (type === "bs_table") return `Table (${Array.isArray(block.rows) ? block.rows.length : 0} rows)`;
    if (type === "bs_list_group") return `List group (${Array.isArray(block.items) ? block.items.length : 0})`;
    if (type === "bs_progress") return `Progress ${Math.max(0, Math.min(100, Number(block.value || 0)))}%`;
    if (type === "bs_breadcrumb") return `Breadcrumb (${Array.isArray(block.items) ? block.items.length : 0})`;
    if (type === "bs_pagination") return `Pagination (${Array.isArray(block.items) ? block.items.length : 0})`;
    if (type === "bs_collapse") return `${block.button_text || "Collapse"} block`;
    if (type === "bs_spinner") return `${block.spinner_type || "border"} spinner`;
    if (type === "bs_carousel") return `Carousel (${Array.isArray(block.items) ? block.items.length : 0} slides)`;
    if (type === "bs_nav") return `Nav (${Array.isArray(block.items) ? block.items.length : 0} links)`;
    if (type === "bs_modal") return `${block.button_text || "Modal"} trigger`;
    if (type === "bs_toast") return `${block.title || "Toast"} notification`;
    if (type === "bs_offcanvas") return `${block.button_text || "Offcanvas"} panel`;
    if (type === "bs_timeline") return `Timeline (${Array.isArray(block.items) ? block.items.length : 0} items)`;
    if (type === "bs_pricing_table") return `Pricing (${Array.isArray(block.plans) ? block.plans.length : 0} plans)`;
    if (type === "bs_dropdown") return `Dropdown (${Array.isArray(block.items) ? block.items.length : 0} items)`;
    if (type === "bs_navbar") return `${block.brand || "Navbar"}`;
    if (type === "bs_ratio") return `Ratio ${block.ratio || "16x9"}`;
    if (type === "bs_placeholder") return `Placeholder (${block.lines || 3} lines)`;
    if (type === "bs_divider") return "Divider";
    if (type === "rows" || type === "raws" || type === "bs_container") {
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
    if (!source || source.dataset.beMounted === "1") return;
    source.dataset.beMounted = "1";
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
    root.appendChild(left);
    root.appendChild(center);

    function applyResponsiveMode() {
      const width = root.getBoundingClientRect().width || 0;
      root.classList.toggle("be-mode-stack", width > 0 && width < 980);
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
      sync();
    }

    function addBlock(type) {
      state.blocks.push(defaultsFor(type));
      state.selectedIndex = state.blocks.length - 1;
      renderCanvas();
      sync();
    }

    function insertBlockAt(index, type) {
      const at = Math.max(0, Math.min(index, state.blocks.length));
      state.blocks.splice(at, 0, defaultsFor(type));
      state.selectedIndex = at;
      renderCanvas();
      sync();
    }

    function removeSelected() {
      if (state.selectedIndex < 0 || state.selectedIndex >= state.blocks.length) return;
      state.blocks.splice(state.selectedIndex, 1);
      if (!state.blocks.length) state.selectedIndex = -1;
      else if (state.selectedIndex >= state.blocks.length) state.selectedIndex = state.blocks.length - 1;
      renderCanvas();
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
      sync();
    }

    function duplicateSelected() {
      const index = state.selectedIndex;
      if (index < 0 || index >= state.blocks.length) return;
      const clone = JSON.parse(JSON.stringify(state.blocks[index]));
      state.blocks.splice(index + 1, 0, clone);
      state.selectedIndex = index + 1;
      renderCanvas();
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
      tabs.innerHTML = "<span class='is-active'>Bootstrap blocks</span>";

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

        const title = document.createElement("div");
        title.className = "be-library-toggle";
        title.innerHTML = `<span>${group}</span><i>${filtered.length}</i>`;

        const grid = document.createElement("div");
        grid.className = "be-library-grid";

        filtered.forEach((meta) => {
          const item = document.createElement("button");
          item.type = "button";
          item.className = "be-library-item";
          item.innerHTML = `<span class="be-lib-icon">${meta.icon}</span><span class="be-lib-label">${meta.label}</span>`;
          item.draggable = true;
          item.dataset.blockType = meta.value;
          item.addEventListener("click", () => addBlock(meta.value));
          item.addEventListener("dragstart", (event) => {
            item.classList.add("is-dragging");
            if (event.dataTransfer) {
              event.dataTransfer.effectAllowed = "copy";
              event.dataTransfer.setData("application/x-be-new-type", meta.value);
              event.dataTransfer.setData("text/plain", meta.value);
            }
          });
          item.addEventListener("dragend", () => {
            item.classList.remove("is-dragging");
          });
          grid.appendChild(item);
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
        "<div class='be-doc-meta'><strong>Document</strong><small>Type / to choose a block · drag cards to reorder</small></div>" +
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
        quickAdd.addEventListener("click", () => addBlock("bs_paragraph"));
        empty.appendChild(quickAdd);
        stage.appendChild(empty);
      } else {
        const clearDropMarkers = () => {
          stage.querySelectorAll(".be-canvas-block.is-drop-before, .be-canvas-block.is-drop-after").forEach((el) => {
            el.classList.remove("is-drop-before", "is-drop-after");
          });
          stage.classList.remove("is-drop-target");
        };

        const draggedNewType = (event) => {
          if (!event.dataTransfer) return "";
          const customType = event.dataTransfer.getData("application/x-be-new-type");
          if (customType) return toBootstrapType(customType);
          const fallback = event.dataTransfer.getData("text/plain");
          if (fallback && BLOCK_TYPES.some((meta) => meta.value === fallback)) return fallback;
          return "";
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
          sync();
        };

        state.blocks.forEach((block, index) => {
          const meta = blockMeta(toBootstrapType(block.type || "bs_paragraph"));
          const card = document.createElement("article");
          card.className = "be-canvas-block";
          if (state.selectedIndex === index) card.classList.add("is-selected");
          card.draggable = true;
          card.innerHTML =
            "<div class='be-canvas-block-top'>" +
            `<span class='be-canvas-type'><span class='be-drag-handle' title='Drag to reorder'>⋮⋮</span>${meta.icon} ${meta.label}</span>` +
            `<span class='be-canvas-index'>#${index + 1}</span>` +
            "</div>" +
            "<div class='be-canvas-preview'></div>";
          card.querySelector(".be-canvas-preview").textContent = blockPreview(block);
          card.addEventListener("click", (event) => {
            if (event.target && event.target.closest && event.target.closest(".be-inline-editor")) return;
            selectBlock(index);
          });
          card.addEventListener("dragstart", (event) => {
            state.dragIndex = index;
            card.classList.add("is-dragging");
            if (event.dataTransfer) {
              event.dataTransfer.effectAllowed = "move";
              event.dataTransfer.setData("application/x-be-move-index", String(index));
              event.dataTransfer.setData("text/plain", String(index));
            }
          });
          card.addEventListener("dragover", (event) => {
            const addingType = draggedNewType(event);
            const moving = state.dragIndex >= 0 && state.dragIndex !== index;
            if (!addingType && !moving) return;
            event.preventDefault();
            clearDropMarkers();
            const rect = card.getBoundingClientRect();
            const before = event.clientY < rect.top + rect.height / 2;
            card.classList.add(before ? "is-drop-before" : "is-drop-after");
          });
          card.addEventListener("drop", (event) => {
            event.preventDefault();
            event.stopPropagation();
            const addingType = draggedNewType(event);
            const rect = card.getBoundingClientRect();
            const before = event.clientY < rect.top + rect.height / 2;
            const target = before ? index : index + 1;
            if (addingType) {
              insertBlockAt(target, addingType);
              clearDropMarkers();
              return;
            }
            if (state.dragIndex < 0 || state.dragIndex === index) return;
            moveBlockByDrag(state.dragIndex, target);
          });
          card.addEventListener("dragend", () => {
            card.classList.remove("is-dragging");
            state.dragIndex = -1;
            clearDropMarkers();
          });
          if (state.selectedIndex === index) {
            const inline = document.createElement("div");
            inline.className = "be-inline-editor";
            card.appendChild(inline);
            renderInspector(inline);
          }
          stage.appendChild(card);
        });

        stage.addEventListener("dragover", (event) => {
          const addingType = draggedNewType(event);
          if (!addingType) return;
          event.preventDefault();
          stage.classList.add("is-drop-target");
        });
        stage.addEventListener("dragleave", (event) => {
          if (!event.relatedTarget || !stage.contains(event.relatedTarget)) {
            stage.classList.remove("is-drop-target");
          }
        });
        stage.addEventListener("drop", (event) => {
          const addingType = draggedNewType(event);
          if (!addingType) return;
          event.preventDefault();
          insertBlockAt(state.blocks.length, addingType);
          stage.classList.remove("is-drop-target");
        });

        const addMore = document.createElement("button");
        addMore.type = "button";
        addMore.className = "button default be-add-more";
        addMore.textContent = "+ Add block";
        addMore.addEventListener("click", () => addBlock("bs_paragraph"));
        stage.appendChild(addMore);
      }

      center.appendChild(top);
      center.appendChild(stage);
    }

    function renderInspector(host) {
      const target = host || null;
      if (!target) return;
      target.innerHTML = "";

      if (state.selectedIndex < 0 || state.selectedIndex >= state.blocks.length) {
        const empty = document.createElement("p");
        empty.className = "be-right-empty";
        empty.textContent = "Select a block to edit settings.";
        target.appendChild(empty);
        return;
      }

      const selected = state.blocks[state.selectedIndex];
      const meta = blockMeta(toBootstrapType(selected.type || "bs_paragraph"));

      const title = document.createElement("div");
      title.className = "be-selected-title";
      title.textContent = `${meta.icon} ${meta.label}`;
      target.appendChild(title);

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
      target.appendChild(actions);

      const form = document.createElement("div");
      form.className = "be-inspector-form";
      target.appendChild(form);

      function changed() {
        renderCanvas();
        sync();
      }

      function normalizeColumnItems(value) {
        return normalizeNestedBlocks(value);
      }

      function renderColumnChildFields(item, holder) {
        const type = toLegacyType(item.type || "bs_paragraph");
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
        if (type === "rows" || type === "raws") {
          holder.appendChild(renderRowsEditor(item));
          return;
        }
        if (type === "bs_alert") {
          const variant = selectInput(
            [
              { value: "primary", label: "Primary" },
              { value: "secondary", label: "Secondary" },
              { value: "success", label: "Success" },
              { value: "danger", label: "Danger" },
              { value: "warning", label: "Warning" },
              { value: "info", label: "Info" },
              { value: "light", label: "Light" },
              { value: "dark", label: "Dark" },
            ],
            item.variant || "info"
          );
          const title = textInput(item.title || "");
          const text = textArea(item.text || "", 4);
          variant.addEventListener("change", () => {
            item.variant = variant.value;
            changed();
          });
          title.addEventListener("input", () => {
            item.title = title.value;
            changed();
          });
          text.addEventListener("input", () => {
            item.text = text.value;
            changed();
          });
          holder.appendChild(field("Variant", variant));
          holder.appendChild(field("Title", title));
          holder.appendChild(field("Text", text));
          return;
        }
        if (type === "bs_badge") {
          const variant = selectInput(
            [
              { value: "primary", label: "Primary" },
              { value: "secondary", label: "Secondary" },
              { value: "success", label: "Success" },
              { value: "danger", label: "Danger" },
              { value: "warning", label: "Warning" },
              { value: "info", label: "Info" },
              { value: "light", label: "Light" },
              { value: "dark", label: "Dark" },
            ],
            item.variant || "primary"
          );
          const text = textInput(item.text || "");
          const pill = document.createElement("input");
          pill.type = "checkbox";
          pill.checked = item.pill !== false;
          variant.addEventListener("change", () => {
            item.variant = variant.value;
            changed();
          });
          text.addEventListener("input", () => {
            item.text = text.value;
            changed();
          });
          pill.addEventListener("change", () => {
            item.pill = pill.checked;
            changed();
          });
          holder.appendChild(field("Variant", variant));
          holder.appendChild(field("Text", text));
          holder.appendChild(field("Pill shape", pill));
          return;
        }
        if (type === "bs_card") {
          const title = textInput(item.title || "");
          const text = textArea(item.text || "", 4);
          const image = textInput(item.image || "");
          const buttonLabel = textInput(item.button_label || "");
          const buttonUrl = textInput(item.button_url || "");
          const buttonStyle = selectInput(
            [
              { value: "primary", label: "Primary" },
              { value: "secondary", label: "Secondary" },
              { value: "success", label: "Success" },
              { value: "danger", label: "Danger" },
              { value: "warning", label: "Warning" },
              { value: "info", label: "Info" },
              { value: "dark", label: "Dark" },
              { value: "light", label: "Light" },
              { value: "link", label: "Link" },
            ],
            item.button_style || "primary"
          );
          title.addEventListener("input", () => {
            item.title = title.value;
            changed();
          });
          text.addEventListener("input", () => {
            item.text = text.value;
            changed();
          });
          image.addEventListener("input", () => {
            item.image = image.value;
            changed();
          });
          buttonLabel.addEventListener("input", () => {
            item.button_label = buttonLabel.value;
            changed();
          });
          buttonUrl.addEventListener("input", () => {
            item.button_url = buttonUrl.value;
            changed();
          });
          buttonStyle.addEventListener("change", () => {
            item.button_style = buttonStyle.value;
            changed();
          });
          holder.appendChild(field("Title", title));
          holder.appendChild(field("Text", text));
          holder.appendChild(field("Image URL (optional)", image));
          holder.appendChild(field("Button label", buttonLabel));
          holder.appendChild(field("Button URL", buttonUrl));
          holder.appendChild(field("Button style", buttonStyle));
          return;
        }
        if (type === "bs_accordion") {
          const flush = document.createElement("input");
          flush.type = "checkbox";
          flush.checked = !!item.flush;
          const items = textArea(
            (Array.isArray(item.items) ? item.items : parseTitleTextLines(item.items || ""))
              .map((row) => `${row.title || ""}|${row.text || ""}`)
              .join("\n"),
            8
          );
          flush.addEventListener("change", () => {
            item.flush = flush.checked;
            changed();
          });
          items.addEventListener("input", () => {
            item.items = parseTitleTextLines(items.value);
            changed();
          });
          holder.appendChild(field("Flush style", flush));
          holder.appendChild(field("Items (title|text, one item per line)", items));
          return;
        }
        if (type === "bs_tabs") {
          const style = selectInput(
            [
              { value: "tabs", label: "Tabs" },
              { value: "pills", label: "Pills" },
            ],
            item.style || "tabs"
          );
          const items = textArea(
            (Array.isArray(item.items) ? item.items : parseTitleTextLines(item.items || ""))
              .map((row) => `${row.title || ""}|${row.text || ""}`)
              .join("\n"),
            8
          );
          style.addEventListener("change", () => {
            item.style = style.value;
            changed();
          });
          items.addEventListener("input", () => {
            item.items = parseTitleTextLines(items.value);
            changed();
          });
          holder.appendChild(field("Style", style));
          holder.appendChild(field("Tabs (title|text, one tab per line)", items));
          return;
        }
        if (type === "bs_table") {
          const headers = textArea((Array.isArray(item.headers) ? item.headers : []).join("|"), 2);
          const rows = textArea(
            (Array.isArray(item.rows) ? item.rows : [])
              .map((row) => (Array.isArray(row) ? row.join("|") : ""))
              .join("\n"),
            8
          );
          const striped = document.createElement("input");
          striped.type = "checkbox";
          striped.checked = item.striped !== false;
          const hover = document.createElement("input");
          hover.type = "checkbox";
          hover.checked = item.hover !== false;
          const bordered = document.createElement("input");
          bordered.type = "checkbox";
          bordered.checked = !!item.bordered;
          headers.addEventListener("input", () => {
            item.headers = parseCsvLine(headers.value);
            changed();
          });
          rows.addEventListener("input", () => {
            item.rows = rows.value
              .replace(/\r/g, "\n")
              .split("\n")
              .map((line) => parseCsvLine(line))
              .filter((line) => line.length);
            changed();
          });
          striped.addEventListener("change", () => {
            item.striped = striped.checked;
            changed();
          });
          hover.addEventListener("change", () => {
            item.hover = hover.checked;
            changed();
          });
          bordered.addEventListener("change", () => {
            item.bordered = bordered.checked;
            changed();
          });
          holder.appendChild(field("Headers (h1|h2|h3)", headers));
          holder.appendChild(field("Rows (c1|c2|c3, one row per line)", rows));
          holder.appendChild(field("Striped", striped));
          holder.appendChild(field("Hover", hover));
          holder.appendChild(field("Bordered", bordered));
          return;
        }
        if (type === "bs_list_group") {
          const items = textArea((Array.isArray(item.items) ? item.items : []).join("\n"), 6);
          const numbered = document.createElement("input");
          numbered.type = "checkbox";
          numbered.checked = !!item.numbered;
          const flush = document.createElement("input");
          flush.type = "checkbox";
          flush.checked = !!item.flush;
          items.addEventListener("input", () => {
            item.items = items.value
              .replace(/\r/g, "\n")
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean);
            changed();
          });
          numbered.addEventListener("change", () => {
            item.numbered = numbered.checked;
            changed();
          });
          flush.addEventListener("change", () => {
            item.flush = flush.checked;
            changed();
          });
          holder.appendChild(field("Items (one line per item)", items));
          holder.appendChild(field("Numbered", numbered));
          holder.appendChild(field("Flush", flush));
          return;
        }
        if (type === "bs_progress") {
          const value = numberInput(item.value || 0, 0, 100);
          const label = textInput(item.label || "");
          const variant = selectInput(
            [
              { value: "primary", label: "Primary" },
              { value: "secondary", label: "Secondary" },
              { value: "success", label: "Success" },
              { value: "danger", label: "Danger" },
              { value: "warning", label: "Warning" },
              { value: "info", label: "Info" },
              { value: "light", label: "Light" },
              { value: "dark", label: "Dark" },
            ],
            item.variant || "primary"
          );
          const striped = document.createElement("input");
          striped.type = "checkbox";
          striped.checked = !!item.striped;
          const animated = document.createElement("input");
          animated.type = "checkbox";
          animated.checked = !!item.animated;
          value.addEventListener("input", () => {
            item.value = Number(value.value || 0);
            changed();
          });
          label.addEventListener("input", () => {
            item.label = label.value;
            changed();
          });
          variant.addEventListener("change", () => {
            item.variant = variant.value;
            changed();
          });
          striped.addEventListener("change", () => {
            item.striped = striped.checked;
            changed();
          });
          animated.addEventListener("change", () => {
            item.animated = animated.checked;
            changed();
          });
          holder.appendChild(field("Value (0-100)", value));
          holder.appendChild(field("Label", label));
          holder.appendChild(field("Variant", variant));
          holder.appendChild(field("Striped", striped));
          holder.appendChild(field("Animated", animated));
          return;
        }
        if (type === "bs_breadcrumb") {
          const items = textArea(
            (Array.isArray(item.items) ? item.items : [])
              .map((row) => `${row.label || ""}|${row.url || ""}|${row.active ? "active" : ""}`)
              .join("\n"),
            8
          );
          items.addEventListener("input", () => {
            item.items = items.value
              .replace(/\r/g, "\n")
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean)
              .map((line, idx, arr) => {
                const parts = line.split("|").map((part) => part.trim());
                return {
                  label: parts[0] || "",
                  url: parts[1] || "",
                  active: parts[2] === "active" || idx === arr.length - 1,
                };
              });
            changed();
          });
          holder.appendChild(field("Items (label|url|active)", items));
          return;
        }
        if (type === "bs_pagination") {
          const size = selectInput(
            [
              { value: "", label: "Default" },
              { value: "sm", label: "Small" },
              { value: "lg", label: "Large" },
            ],
            item.size || ""
          );
          const align = selectInput(
            [
              { value: "start", label: "Left" },
              { value: "center", label: "Center" },
              { value: "end", label: "Right" },
            ],
            item.align || "start"
          );
          const items = textArea(
            (Array.isArray(item.items) ? item.items : [])
              .map((row) => `${row.label || ""}|${row.url || ""}|${row.active ? "active" : row.disabled ? "disabled" : ""}`)
              .join("\n"),
            8
          );
          size.addEventListener("change", () => {
            item.size = size.value;
            changed();
          });
          align.addEventListener("change", () => {
            item.align = align.value;
            changed();
          });
          items.addEventListener("input", () => {
            item.items = items.value
              .replace(/\r/g, "\n")
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean)
              .map((line) => {
                const parts = line.split("|").map((part) => part.trim());
                return {
                  label: parts[0] || "",
                  url: parts[1] || "",
                  active: parts[2] === "active",
                  disabled: parts[2] === "disabled",
                };
              });
            changed();
          });
          holder.appendChild(field("Size", size));
          holder.appendChild(field("Align", align));
          holder.appendChild(field("Items (label|url|active|disabled)", items));
          return;
        }
        if (type === "bs_collapse") {
          const buttonText = textInput(item.button_text || "");
          const text = textArea(item.text || "", 6);
          const variant = selectInput(
            [
              { value: "primary", label: "Primary" },
              { value: "secondary", label: "Secondary" },
              { value: "success", label: "Success" },
              { value: "danger", label: "Danger" },
              { value: "warning", label: "Warning" },
              { value: "info", label: "Info" },
              { value: "light", label: "Light" },
              { value: "dark", label: "Dark" },
            ],
            item.variant || "primary"
          );
          const open = document.createElement("input");
          open.type = "checkbox";
          open.checked = !!item.open;
          buttonText.addEventListener("input", () => {
            item.button_text = buttonText.value;
            changed();
          });
          text.addEventListener("input", () => {
            item.text = text.value;
            changed();
          });
          variant.addEventListener("change", () => {
            item.variant = variant.value;
            changed();
          });
          open.addEventListener("change", () => {
            item.open = open.checked;
            changed();
          });
          holder.appendChild(field("Button text", buttonText));
          holder.appendChild(field("Text", text));
          holder.appendChild(field("Button variant", variant));
          holder.appendChild(field("Open by default", open));
          return;
        }
        if (type === "bs_spinner") {
          const spinnerType = selectInput(
            [
              { value: "border", label: "Border" },
              { value: "grow", label: "Grow" },
            ],
            item.spinner_type || "border"
          );
          const variant = selectInput(
            [
              { value: "primary", label: "Primary" },
              { value: "secondary", label: "Secondary" },
              { value: "success", label: "Success" },
              { value: "danger", label: "Danger" },
              { value: "warning", label: "Warning" },
              { value: "info", label: "Info" },
              { value: "light", label: "Light" },
              { value: "dark", label: "Dark" },
            ],
            item.variant || "primary"
          );
          const size = selectInput(
            [
              { value: "", label: "Default" },
              { value: "sm", label: "Small" },
            ],
            item.size || ""
          );
          const label = textInput(item.label || "");
          spinnerType.addEventListener("change", () => {
            item.spinner_type = spinnerType.value;
            changed();
          });
          variant.addEventListener("change", () => {
            item.variant = variant.value;
            changed();
          });
          size.addEventListener("change", () => {
            item.size = size.value;
            changed();
          });
          label.addEventListener("input", () => {
            item.label = label.value;
            changed();
          });
          holder.appendChild(field("Type", spinnerType));
          holder.appendChild(field("Variant", variant));
          holder.appendChild(field("Size", size));
          holder.appendChild(field("Label", label));
          return;
        }
        if (type === "bs_carousel") {
          const controls = document.createElement("input");
          controls.type = "checkbox";
          controls.checked = item.controls !== false;
          const indicators = document.createElement("input");
          indicators.type = "checkbox";
          indicators.checked = item.indicators !== false;
          const fade = document.createElement("input");
          fade.type = "checkbox";
          fade.checked = !!item.fade;
          const auto = document.createElement("input");
          auto.type = "checkbox";
          auto.checked = !!item.auto;
          const items = textArea(
            (Array.isArray(item.items) ? item.items : [])
              .map((slide) => `${slide.image || ""}|${slide.title || ""}|${slide.caption || ""}|${slide.alt || ""}`)
              .join("\n"),
            10
          );
          controls.addEventListener("change", () => {
            item.controls = controls.checked;
            changed();
          });
          indicators.addEventListener("change", () => {
            item.indicators = indicators.checked;
            changed();
          });
          fade.addEventListener("change", () => {
            item.fade = fade.checked;
            changed();
          });
          auto.addEventListener("change", () => {
            item.auto = auto.checked;
            changed();
          });
          items.addEventListener("input", () => {
            item.items = items.value
              .replace(/\r/g, "\n")
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean)
              .map((line) => {
                const parts = line.split("|").map((part) => part.trim());
                return {
                  image: parts[0] || "",
                  title: parts[1] || "",
                  caption: parts[2] || "",
                  alt: parts[3] || "",
                };
              });
            changed();
          });
          holder.appendChild(field("Slides (image|title|caption|alt)", items));
          holder.appendChild(field("Show controls", controls));
          holder.appendChild(field("Show indicators", indicators));
          holder.appendChild(field("Fade animation", fade));
          holder.appendChild(field("Auto slide", auto));
          return;
        }
        if (type === "bs_nav") {
          const style = selectInput(
            [
              { value: "tabs", label: "Tabs" },
              { value: "pills", label: "Pills" },
            ],
            item.style || "tabs"
          );
          const fill = document.createElement("input");
          fill.type = "checkbox";
          fill.checked = !!item.fill;
          const justified = document.createElement("input");
          justified.type = "checkbox";
          justified.checked = !!item.justified;
          const vertical = document.createElement("input");
          vertical.type = "checkbox";
          vertical.checked = !!item.vertical;
          const items = textArea(
            (Array.isArray(item.items) ? item.items : [])
              .map((row) => `${row.label || ""}|${row.url || ""}|${row.active ? "active" : ""}`)
              .join("\n"),
            8
          );
          style.addEventListener("change", () => {
            item.style = style.value;
            changed();
          });
          fill.addEventListener("change", () => {
            item.fill = fill.checked;
            changed();
          });
          justified.addEventListener("change", () => {
            item.justified = justified.checked;
            changed();
          });
          vertical.addEventListener("change", () => {
            item.vertical = vertical.checked;
            changed();
          });
          items.addEventListener("input", () => {
            item.items = items.value
              .replace(/\r/g, "\n")
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean)
              .map((line, idx) => {
                const parts = line.split("|").map((part) => part.trim());
                return {
                  label: parts[0] || "",
                  url: parts[1] || "",
                  active: parts[2] === "active" || idx === 0,
                };
              });
            changed();
          });
          holder.appendChild(field("Style", style));
          holder.appendChild(field("Links (label|url|active)", items));
          holder.appendChild(field("Fill width", fill));
          holder.appendChild(field("Justified", justified));
          holder.appendChild(field("Vertical", vertical));
          return;
        }
        if (type === "bs_modal") {
          const buttonText = textInput(item.button_text || "");
          const buttonVariant = selectInput(
            [
              { value: "primary", label: "Primary" },
              { value: "secondary", label: "Secondary" },
              { value: "success", label: "Success" },
              { value: "danger", label: "Danger" },
              { value: "warning", label: "Warning" },
              { value: "info", label: "Info" },
              { value: "dark", label: "Dark" },
            ],
            item.button_variant || "primary"
          );
          const title = textInput(item.title || "");
          const text = textArea(item.text || "", 6);
          const size = selectInput(
            [
              { value: "", label: "Default" },
              { value: "sm", label: "Small" },
              { value: "lg", label: "Large" },
              { value: "xl", label: "Extra Large" },
            ],
            item.size || ""
          );
          const centered = document.createElement("input");
          centered.type = "checkbox";
          centered.checked = !!item.centered;
          const scrollable = document.createElement("input");
          scrollable.type = "checkbox";
          scrollable.checked = !!item.scrollable;
          const fullscreen = document.createElement("input");
          fullscreen.type = "checkbox";
          fullscreen.checked = !!item.fullscreen;
          const footerPrimary = textInput(item.footer_primary_text || "");
          const footerSecondary = textInput(item.footer_secondary_text || "");
          buttonText.addEventListener("input", () => {
            item.button_text = buttonText.value;
            changed();
          });
          buttonVariant.addEventListener("change", () => {
            item.button_variant = buttonVariant.value;
            changed();
          });
          title.addEventListener("input", () => {
            item.title = title.value;
            changed();
          });
          text.addEventListener("input", () => {
            item.text = text.value;
            changed();
          });
          size.addEventListener("change", () => {
            item.size = size.value;
            changed();
          });
          centered.addEventListener("change", () => {
            item.centered = centered.checked;
            changed();
          });
          scrollable.addEventListener("change", () => {
            item.scrollable = scrollable.checked;
            changed();
          });
          fullscreen.addEventListener("change", () => {
            item.fullscreen = fullscreen.checked;
            changed();
          });
          footerPrimary.addEventListener("input", () => {
            item.footer_primary_text = footerPrimary.value;
            changed();
          });
          footerSecondary.addEventListener("input", () => {
            item.footer_secondary_text = footerSecondary.value;
            changed();
          });
          holder.appendChild(field("Button text", buttonText));
          holder.appendChild(field("Button variant", buttonVariant));
          holder.appendChild(field("Modal title", title));
          holder.appendChild(field("Modal text", text));
          holder.appendChild(field("Size", size));
          holder.appendChild(field("Centered", centered));
          holder.appendChild(field("Scrollable body", scrollable));
          holder.appendChild(field("Fullscreen", fullscreen));
          holder.appendChild(field("Footer primary button", footerPrimary));
          holder.appendChild(field("Footer secondary button", footerSecondary));
          return;
        }
        if (type === "bs_toast") {
          const title = textInput(item.title || "");
          const text = textArea(item.text || "", 6);
          const delay = numberInput(item.delay || 5000, 1000, 20000);
          const autohide = document.createElement("input");
          autohide.type = "checkbox";
          autohide.checked = item.autohide !== false;
          const variant = selectInput(
            [
              { value: "primary", label: "Primary" },
              { value: "secondary", label: "Secondary" },
              { value: "success", label: "Success" },
              { value: "danger", label: "Danger" },
              { value: "warning", label: "Warning" },
              { value: "info", label: "Info" },
              { value: "dark", label: "Dark" },
            ],
            item.variant || "primary"
          );
          title.addEventListener("input", () => {
            item.title = title.value;
            changed();
          });
          text.addEventListener("input", () => {
            item.text = text.value;
            changed();
          });
          delay.addEventListener("input", () => {
            item.delay = Number(delay.value || 5000);
            changed();
          });
          autohide.addEventListener("change", () => {
            item.autohide = autohide.checked;
            changed();
          });
          variant.addEventListener("change", () => {
            item.variant = variant.value;
            changed();
          });
          holder.appendChild(field("Title", title));
          holder.appendChild(field("Text", text));
          holder.appendChild(field("Autohide delay (ms)", delay));
          holder.appendChild(field("Autohide", autohide));
          holder.appendChild(field("Variant", variant));
          return;
        }
        if (type === "bs_offcanvas") {
          const buttonText = textInput(item.button_text || "");
          const buttonVariant = selectInput(
            [
              { value: "primary", label: "Primary" },
              { value: "secondary", label: "Secondary" },
              { value: "success", label: "Success" },
              { value: "danger", label: "Danger" },
              { value: "warning", label: "Warning" },
              { value: "info", label: "Info" },
              { value: "dark", label: "Dark" },
            ],
            item.button_variant || "primary"
          );
          const title = textInput(item.title || "");
          const text = textArea(item.text || "", 6);
          const placement = selectInput(
            [
              { value: "start", label: "Left" },
              { value: "end", label: "Right" },
              { value: "top", label: "Top" },
              { value: "bottom", label: "Bottom" },
            ],
            item.placement || "end"
          );
          buttonText.addEventListener("input", () => {
            item.button_text = buttonText.value;
            changed();
          });
          buttonVariant.addEventListener("change", () => {
            item.button_variant = buttonVariant.value;
            changed();
          });
          title.addEventListener("input", () => {
            item.title = title.value;
            changed();
          });
          text.addEventListener("input", () => {
            item.text = text.value;
            changed();
          });
          placement.addEventListener("change", () => {
            item.placement = placement.value;
            changed();
          });
          holder.appendChild(field("Button text", buttonText));
          holder.appendChild(field("Button variant", buttonVariant));
          holder.appendChild(field("Panel title", title));
          holder.appendChild(field("Panel text", text));
          holder.appendChild(field("Placement", placement));
          return;
        }
        if (type === "bs_timeline") {
          const title = textInput(item.title || "");
          const items = textArea(
            (Array.isArray(item.items) ? item.items : [])
              .map((row) => `${row.date || ""}|${row.title || ""}|${row.text || ""}`)
              .join("\n"),
            8
          );
          title.addEventListener("input", () => {
            item.title = title.value;
            changed();
          });
          items.addEventListener("input", () => {
            item.items = parseTimelineLines(items.value);
            changed();
          });
          holder.appendChild(field("Section title", title));
          holder.appendChild(field("Items (date|title|text)", items));
          return;
        }
        if (type === "bs_pricing_table") {
          const title = textInput(item.title || "");
          const subtitle = textInput(item.subtitle || "");
          const plans = textArea(
            (Array.isArray(item.plans) ? item.plans : [])
              .map((plan) =>
                `${plan.title || ""}|${plan.price || ""}|${plan.period || ""}|${(Array.isArray(plan.features) ? plan.features : []).join(";")}|${plan.button_label || ""}|${plan.button_url || ""}|${plan.recommended ? "recommended" : ""}`
              )
              .join("\n"),
            10
          );
          title.addEventListener("input", () => {
            item.title = title.value;
            changed();
          });
          subtitle.addEventListener("input", () => {
            item.subtitle = subtitle.value;
            changed();
          });
          plans.addEventListener("input", () => {
            item.plans = parsePricingLines(plans.value);
            changed();
          });
          holder.appendChild(field("Section title", title));
          holder.appendChild(field("Section subtitle", subtitle));
          holder.appendChild(field("Plans (title|price|period|f1;f2|button|url|recommended)", plans));
          return;
        }
        if (type === "bs_dropdown") {
          const buttonText = textInput(item.button_text || "Menu");
          const buttonVariant = selectInput(
            [
              { value: "primary", label: "Primary" },
              { value: "secondary", label: "Secondary" },
              { value: "success", label: "Success" },
              { value: "danger", label: "Danger" },
              { value: "warning", label: "Warning" },
              { value: "info", label: "Info" },
              { value: "dark", label: "Dark" },
            ],
            item.button_variant || "primary"
          );
          const align = selectInput(
            [
              { value: "", label: "Default" },
              { value: "start", label: "Start" },
              { value: "end", label: "End" },
            ],
            item.align || ""
          );
          const items = textArea(
            (Array.isArray(item.items) ? item.items : [])
              .map((row) => `${row.label || ""}|${row.url || ""}|${row.divider_before ? "divider" : ""}`)
              .join("\n"),
            8
          );
          buttonText.addEventListener("input", () => {
            item.button_text = buttonText.value;
            changed();
          });
          buttonVariant.addEventListener("change", () => {
            item.button_variant = buttonVariant.value;
            changed();
          });
          align.addEventListener("change", () => {
            item.align = align.value;
            changed();
          });
          items.addEventListener("input", () => {
            item.items = items.value
              .replace(/\r/g, "\n")
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean)
              .map((line) => {
                const parts = line.split("|").map((part) => part.trim());
                return {
                  label: parts[0] || "",
                  url: parts[1] || "#",
                  divider_before: parts[2] === "divider",
                };
              });
            changed();
          });
          holder.appendChild(field("Button text", buttonText));
          holder.appendChild(field("Button variant", buttonVariant));
          holder.appendChild(field("Alignment", align));
          holder.appendChild(field("Items (label|url|divider)", items));
          return;
        }
        if (type === "bs_navbar") {
          const brand = textInput(item.brand || "VXcloud");
          const brandUrl = textInput(item.brand_url || "/");
          const expand = selectInput(
            [
              { value: "sm", label: "sm" },
              { value: "md", label: "md" },
              { value: "lg", label: "lg" },
              { value: "xl", label: "xl" },
              { value: "xxl", label: "xxl" },
              { value: "", label: "Always expanded" },
            ],
            item.expand || "lg"
          );
          const theme = selectInput(
            [
              { value: "dark", label: "Dark" },
              { value: "light", label: "Light" },
            ],
            item.theme || "dark"
          );
          const bg = textInput(item.bg || "dark");
          const links = textArea(
            (Array.isArray(item.items) ? item.items : [])
              .map((row) => `${row.label || ""}|${row.url || ""}`)
              .join("\n"),
            8
          );
          brand.addEventListener("input", () => {
            item.brand = brand.value;
            changed();
          });
          brandUrl.addEventListener("input", () => {
            item.brand_url = brandUrl.value;
            changed();
          });
          expand.addEventListener("change", () => {
            item.expand = expand.value;
            changed();
          });
          theme.addEventListener("change", () => {
            item.theme = theme.value;
            changed();
          });
          bg.addEventListener("input", () => {
            item.bg = bg.value;
            changed();
          });
          links.addEventListener("input", () => {
            item.items = links.value
              .replace(/\r/g, "\n")
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean)
              .map((line) => {
                const parts = line.split("|").map((part) => part.trim());
                return { label: parts[0] || "", url: parts[1] || "#" };
              });
            changed();
          });
          holder.appendChild(field("Brand", brand));
          holder.appendChild(field("Brand URL", brandUrl));
          holder.appendChild(field("Expand breakpoint", expand));
          holder.appendChild(field("Theme", theme));
          holder.appendChild(field("Background class suffix", bg, "Example: dark, primary, light"));
          holder.appendChild(field("Links (label|url)", links));
          return;
        }
        if (type === "bs_ratio") {
          const ratio = selectInput(
            [
              { value: "1x1", label: "1x1" },
              { value: "4x3", label: "4x3" },
              { value: "16x9", label: "16x9" },
              { value: "21x9", label: "21x9" },
            ],
            item.ratio || "16x9"
          );
          const html = textArea(item.html || "", 8);
          ratio.addEventListener("change", () => {
            item.ratio = ratio.value;
            changed();
          });
          html.addEventListener("input", () => {
            item.html = html.value;
            changed();
          });
          holder.appendChild(field("Ratio", ratio));
          holder.appendChild(field("Inner HTML (iframe/video/img)", html));
          return;
        }
        if (type === "bs_placeholder") {
          const lines = numberInput(item.lines || 3, 1, 12);
          const width = numberInput(item.width || 100, 10, 100);
          const size = selectInput(
            [
              { value: "sm", label: "Small" },
              { value: "md", label: "Medium" },
              { value: "lg", label: "Large" },
            ],
            item.size || "md"
          );
          const glow = document.createElement("input");
          glow.type = "checkbox";
          glow.checked = !!item.glow;
          lines.addEventListener("input", () => {
            item.lines = Number(lines.value || 3);
            changed();
          });
          width.addEventListener("input", () => {
            item.width = Number(width.value || 100);
            changed();
          });
          size.addEventListener("change", () => {
            item.size = size.value;
            changed();
          });
          glow.addEventListener("change", () => {
            item.glow = glow.checked;
            changed();
          });
          holder.appendChild(field("Lines", lines));
          holder.appendChild(field("Line width %", width));
          holder.appendChild(field("Size", size));
          holder.appendChild(field("Glow animation", glow));
          return;
        }
        if (type === "bs_divider") {
          const spacing = numberInput(item.spacing || 24, 0, 120);
          const label = textInput(item.label || "");
          spacing.addEventListener("input", () => {
            item.spacing = Number(spacing.value || 24);
            changed();
          });
          label.addEventListener("input", () => {
            item.label = label.value;
            changed();
          });
          holder.appendChild(field("Vertical spacing (px)", spacing));
          holder.appendChild(field("Label (optional)", label));
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
          "bs_paragraph"
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
          const itemType = toBootstrapType(block.type || "bs_paragraph");

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
        return { width: 6, blocks: [{ type: "bs_paragraph", text: "Column text" }] };
      }

      function normalizeRowItem(row) {
        if (!row || typeof row !== "object") return { columns: [defaultRowColumn()] };
        const columns = Array.isArray(row.columns)
          ? row.columns
              .map((col) => {
                if (!col || typeof col !== "object") return null;
                const blocks = normalizeColumnItems(col.blocks ?? col.items ?? col.text ?? "");
                const width = Number(col.width || 6) || 6;
                return {
                  width: width < 1 ? 1 : width > 12 ? 12 : width,
                  blocks: blocks.length ? blocks : [{ type: "bs_paragraph", text: "Column text" }],
                };
              })
              .filter(Boolean)
          : [];
        const gutter = Number(row.gutter || 3) || 3;
        const align = String(row.align || "start");
        return {
          gutter: gutter < 0 ? 0 : gutter > 5 ? 5 : gutter,
          align: ["start", "center", "end", "stretch"].includes(align) ? align : "start",
          columns: columns.length ? columns : [defaultRowColumn()],
        };
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
          rowsBlock.rows.push({ gutter: 3, align: "start", columns: [defaultRowColumn(), defaultRowColumn()] });
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

          const rowSettings = document.createElement("div");
          rowSettings.className = "be-row-settings";

          const gutterSelect = selectInput(
            [
              { value: 0, label: "No gap" },
              { value: 1, label: "Gap 1" },
              { value: 2, label: "Gap 2" },
              { value: 3, label: "Gap 3" },
              { value: 4, label: "Gap 4" },
              { value: 5, label: "Gap 5" },
            ],
            normalizedRow.gutter || 3
          );
          gutterSelect.addEventListener("change", () => {
            normalizedRow.gutter = Number(gutterSelect.value || 3);
            changed();
          });

          const alignSelect = selectInput(
            [
              { value: "start", label: "Top align" },
              { value: "center", label: "Center align" },
              { value: "end", label: "Bottom align" },
              { value: "stretch", label: "Stretch" },
            ],
            normalizedRow.align || "start"
          );
          alignSelect.addEventListener("change", () => {
            normalizedRow.align = alignSelect.value;
            changed();
          });

          rowSettings.appendChild(field("Row gap", gutterSelect));
          rowSettings.appendChild(field("Vertical align", alignSelect));
          rowCard.appendChild(rowSettings);

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

            const widthSelect = selectInput(
              [
                { value: 12, label: "12/12 (full)" },
                { value: 9, label: "9/12" },
                { value: 8, label: "8/12" },
                { value: 7, label: "7/12" },
                { value: 6, label: "6/12" },
                { value: 5, label: "5/12" },
                { value: 4, label: "4/12" },
                { value: 3, label: "3/12" },
                { value: 2, label: "2/12" },
              ],
              column.width || 6
            );
            widthSelect.addEventListener("change", () => {
              column.width = Number(widthSelect.value || 6);
              changed();
            });
            colCard.appendChild(field("Desktop width", widthSelect));

            colCard.appendChild(renderColumnEditor(column, "blocks", "Blocks"));
            columnsGrid.appendChild(colCard);
          });

          rowCard.appendChild(columnsGrid);
          section.appendChild(rowCard);
        });

        return section;
      }

      const type = toLegacyType(selected.type || "bs_paragraph");
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
      } else if (type === "bs_alert") {
        const variant = selectInput(
          [
            { value: "primary", label: "Primary" },
            { value: "secondary", label: "Secondary" },
            { value: "success", label: "Success" },
            { value: "danger", label: "Danger" },
            { value: "warning", label: "Warning" },
            { value: "info", label: "Info" },
            { value: "light", label: "Light" },
            { value: "dark", label: "Dark" },
          ],
          selected.variant || "info"
        );
        const titleInput = textInput(selected.title || "");
        const textInputField = textArea(selected.text || "", 6);
        variant.addEventListener("change", () => {
          selected.variant = variant.value;
          changed();
        });
        titleInput.addEventListener("input", () => {
          selected.title = titleInput.value;
          changed();
        });
        textInputField.addEventListener("input", () => {
          selected.text = textInputField.value;
          changed();
        });
        form.appendChild(field("Variant", variant));
        form.appendChild(field("Title", titleInput));
        form.appendChild(field("Text", textInputField));
      } else if (type === "bs_badge") {
        const variant = selectInput(
          [
            { value: "primary", label: "Primary" },
            { value: "secondary", label: "Secondary" },
            { value: "success", label: "Success" },
            { value: "danger", label: "Danger" },
            { value: "warning", label: "Warning" },
            { value: "info", label: "Info" },
            { value: "light", label: "Light" },
            { value: "dark", label: "Dark" },
          ],
          selected.variant || "primary"
        );
        const textInputField = textInput(selected.text || "");
        const pill = document.createElement("input");
        pill.type = "checkbox";
        pill.checked = selected.pill !== false;
        variant.addEventListener("change", () => {
          selected.variant = variant.value;
          changed();
        });
        textInputField.addEventListener("input", () => {
          selected.text = textInputField.value;
          changed();
        });
        pill.addEventListener("change", () => {
          selected.pill = pill.checked;
          changed();
        });
        form.appendChild(field("Variant", variant));
        form.appendChild(field("Text", textInputField));
        form.appendChild(field("Pill shape", pill));
      } else if (type === "bs_card") {
        const titleInput = textInput(selected.title || "");
        const textInputField = textArea(selected.text || "", 6);
        const image = textInput(selected.image || "");
        const buttonLabel = textInput(selected.button_label || "");
        const buttonUrl = textInput(selected.button_url || "");
        const buttonStyle = selectInput(
          [
            { value: "primary", label: "Primary" },
            { value: "secondary", label: "Secondary" },
            { value: "success", label: "Success" },
            { value: "danger", label: "Danger" },
            { value: "warning", label: "Warning" },
            { value: "info", label: "Info" },
            { value: "dark", label: "Dark" },
            { value: "light", label: "Light" },
            { value: "link", label: "Link" },
          ],
          selected.button_style || "primary"
        );
        titleInput.addEventListener("input", () => {
          selected.title = titleInput.value;
          changed();
        });
        textInputField.addEventListener("input", () => {
          selected.text = textInputField.value;
          changed();
        });
        image.addEventListener("input", () => {
          selected.image = image.value;
          changed();
        });
        buttonLabel.addEventListener("input", () => {
          selected.button_label = buttonLabel.value;
          changed();
        });
        buttonUrl.addEventListener("input", () => {
          selected.button_url = buttonUrl.value;
          changed();
        });
        buttonStyle.addEventListener("change", () => {
          selected.button_style = buttonStyle.value;
          changed();
        });
        form.appendChild(field("Title", titleInput));
        form.appendChild(field("Text", textInputField));
        form.appendChild(field("Image URL (optional)", image));
        form.appendChild(field("Button label", buttonLabel));
        form.appendChild(field("Button URL", buttonUrl));
        form.appendChild(field("Button style", buttonStyle));
      } else if (type === "bs_accordion") {
        const flush = document.createElement("input");
        flush.type = "checkbox";
        flush.checked = !!selected.flush;
        const items = textArea(
          (Array.isArray(selected.items) ? selected.items : parseTitleTextLines(selected.items || ""))
            .map((row) => `${row.title || ""}|${row.text || ""}`)
            .join("\n"),
          10
        );
        flush.addEventListener("change", () => {
          selected.flush = flush.checked;
          changed();
        });
        items.addEventListener("input", () => {
          selected.items = parseTitleTextLines(items.value);
          changed();
        });
        form.appendChild(field("Flush style", flush));
        form.appendChild(field("Items (title|text, one item per line)", items));
      } else if (type === "bs_tabs") {
        const style = selectInput(
          [
            { value: "tabs", label: "Tabs" },
            { value: "pills", label: "Pills" },
          ],
          selected.style || "tabs"
        );
        const items = textArea(
          (Array.isArray(selected.items) ? selected.items : parseTitleTextLines(selected.items || ""))
            .map((row) => `${row.title || ""}|${row.text || ""}`)
            .join("\n"),
          10
        );
        style.addEventListener("change", () => {
          selected.style = style.value;
          changed();
        });
        items.addEventListener("input", () => {
          selected.items = parseTitleTextLines(items.value);
          changed();
        });
        form.appendChild(field("Style", style));
        form.appendChild(field("Tabs (title|text, one tab per line)", items));
      } else if (type === "bs_table") {
        const headers = textArea((Array.isArray(selected.headers) ? selected.headers : []).join("|"), 2);
        const rows = textArea(
          (Array.isArray(selected.rows) ? selected.rows : [])
            .map((row) => (Array.isArray(row) ? row.join("|") : ""))
            .join("\n"),
          10
        );
        const striped = document.createElement("input");
        striped.type = "checkbox";
        striped.checked = selected.striped !== false;
        const hover = document.createElement("input");
        hover.type = "checkbox";
        hover.checked = selected.hover !== false;
        const bordered = document.createElement("input");
        bordered.type = "checkbox";
        bordered.checked = !!selected.bordered;
        headers.addEventListener("input", () => {
          selected.headers = parseCsvLine(headers.value);
          changed();
        });
        rows.addEventListener("input", () => {
          selected.rows = rows.value
            .replace(/\r/g, "\n")
            .split("\n")
            .map((line) => parseCsvLine(line))
            .filter((line) => line.length);
          changed();
        });
        striped.addEventListener("change", () => {
          selected.striped = striped.checked;
          changed();
        });
        hover.addEventListener("change", () => {
          selected.hover = hover.checked;
          changed();
        });
        bordered.addEventListener("change", () => {
          selected.bordered = bordered.checked;
          changed();
        });
        form.appendChild(field("Headers (h1|h2|h3)", headers));
        form.appendChild(field("Rows (c1|c2|c3, one row per line)", rows));
        form.appendChild(field("Striped", striped));
        form.appendChild(field("Hover", hover));
        form.appendChild(field("Bordered", bordered));
      } else if (type === "bs_list_group") {
        const items = textArea((Array.isArray(selected.items) ? selected.items : []).join("\n"), 8);
        const numbered = document.createElement("input");
        numbered.type = "checkbox";
        numbered.checked = !!selected.numbered;
        const flush = document.createElement("input");
        flush.type = "checkbox";
        flush.checked = !!selected.flush;
        items.addEventListener("input", () => {
          selected.items = items.value
            .replace(/\r/g, "\n")
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean);
          changed();
        });
        numbered.addEventListener("change", () => {
          selected.numbered = numbered.checked;
          changed();
        });
        flush.addEventListener("change", () => {
          selected.flush = flush.checked;
          changed();
        });
        form.appendChild(field("Items (one line per item)", items));
        form.appendChild(field("Numbered", numbered));
        form.appendChild(field("Flush", flush));
      } else if (type === "bs_progress") {
        const value = numberInput(selected.value || 0, 0, 100);
        const label = textInput(selected.label || "");
        const variant = selectInput(
          [
            { value: "primary", label: "Primary" },
            { value: "secondary", label: "Secondary" },
            { value: "success", label: "Success" },
            { value: "danger", label: "Danger" },
            { value: "warning", label: "Warning" },
            { value: "info", label: "Info" },
            { value: "light", label: "Light" },
            { value: "dark", label: "Dark" },
          ],
          selected.variant || "primary"
        );
        const striped = document.createElement("input");
        striped.type = "checkbox";
        striped.checked = !!selected.striped;
        const animated = document.createElement("input");
        animated.type = "checkbox";
        animated.checked = !!selected.animated;
        value.addEventListener("input", () => {
          selected.value = Number(value.value || 0);
          changed();
        });
        label.addEventListener("input", () => {
          selected.label = label.value;
          changed();
        });
        variant.addEventListener("change", () => {
          selected.variant = variant.value;
          changed();
        });
        striped.addEventListener("change", () => {
          selected.striped = striped.checked;
          changed();
        });
        animated.addEventListener("change", () => {
          selected.animated = animated.checked;
          changed();
        });
        form.appendChild(field("Value (0-100)", value));
        form.appendChild(field("Label", label));
        form.appendChild(field("Variant", variant));
        form.appendChild(field("Striped", striped));
        form.appendChild(field("Animated", animated));
      } else if (type === "bs_breadcrumb") {
        const items = textArea(
          (Array.isArray(selected.items) ? selected.items : [])
            .map((row) => `${row.label || ""}|${row.url || ""}|${row.active ? "active" : ""}`)
            .join("\n"),
          10
        );
        items.addEventListener("input", () => {
          selected.items = items.value
            .replace(/\r/g, "\n")
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean)
            .map((line, idx, arr) => {
              const parts = line.split("|").map((part) => part.trim());
              return {
                label: parts[0] || "",
                url: parts[1] || "",
                active: parts[2] === "active" || idx === arr.length - 1,
              };
            });
          changed();
        });
        form.appendChild(field("Items (label|url|active)", items));
      } else if (type === "bs_pagination") {
        const size = selectInput(
          [
            { value: "", label: "Default" },
            { value: "sm", label: "Small" },
            { value: "lg", label: "Large" },
          ],
          selected.size || ""
        );
        const align = selectInput(
          [
            { value: "start", label: "Left" },
            { value: "center", label: "Center" },
            { value: "end", label: "Right" },
          ],
          selected.align || "start"
        );
        const items = textArea(
          (Array.isArray(selected.items) ? selected.items : [])
            .map((row) => `${row.label || ""}|${row.url || ""}|${row.active ? "active" : row.disabled ? "disabled" : ""}`)
            .join("\n"),
          10
        );
        size.addEventListener("change", () => {
          selected.size = size.value;
          changed();
        });
        align.addEventListener("change", () => {
          selected.align = align.value;
          changed();
        });
        items.addEventListener("input", () => {
          selected.items = items.value
            .replace(/\r/g, "\n")
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean)
            .map((line) => {
              const parts = line.split("|").map((part) => part.trim());
              return {
                label: parts[0] || "",
                url: parts[1] || "",
                active: parts[2] === "active",
                disabled: parts[2] === "disabled",
              };
            });
          changed();
        });
        form.appendChild(field("Size", size));
        form.appendChild(field("Align", align));
        form.appendChild(field("Items (label|url|active|disabled)", items));
      } else if (type === "bs_collapse") {
        const buttonText = textInput(selected.button_text || "");
        const textInputField = textArea(selected.text || "", 8);
        const variant = selectInput(
          [
            { value: "primary", label: "Primary" },
            { value: "secondary", label: "Secondary" },
            { value: "success", label: "Success" },
            { value: "danger", label: "Danger" },
            { value: "warning", label: "Warning" },
            { value: "info", label: "Info" },
            { value: "light", label: "Light" },
            { value: "dark", label: "Dark" },
          ],
          selected.variant || "primary"
        );
        const open = document.createElement("input");
        open.type = "checkbox";
        open.checked = !!selected.open;
        buttonText.addEventListener("input", () => {
          selected.button_text = buttonText.value;
          changed();
        });
        textInputField.addEventListener("input", () => {
          selected.text = textInputField.value;
          changed();
        });
        variant.addEventListener("change", () => {
          selected.variant = variant.value;
          changed();
        });
        open.addEventListener("change", () => {
          selected.open = open.checked;
          changed();
        });
        form.appendChild(field("Button text", buttonText));
        form.appendChild(field("Text", textInputField));
        form.appendChild(field("Button variant", variant));
        form.appendChild(field("Open by default", open));
      } else if (type === "bs_spinner") {
        const spinnerType = selectInput(
          [
            { value: "border", label: "Border" },
            { value: "grow", label: "Grow" },
          ],
          selected.spinner_type || "border"
        );
        const variant = selectInput(
          [
            { value: "primary", label: "Primary" },
            { value: "secondary", label: "Secondary" },
            { value: "success", label: "Success" },
            { value: "danger", label: "Danger" },
            { value: "warning", label: "Warning" },
            { value: "info", label: "Info" },
            { value: "light", label: "Light" },
            { value: "dark", label: "Dark" },
          ],
          selected.variant || "primary"
        );
        const size = selectInput(
          [
            { value: "", label: "Default" },
            { value: "sm", label: "Small" },
          ],
          selected.size || ""
        );
        const label = textInput(selected.label || "");
        spinnerType.addEventListener("change", () => {
          selected.spinner_type = spinnerType.value;
          changed();
        });
        variant.addEventListener("change", () => {
          selected.variant = variant.value;
          changed();
        });
        size.addEventListener("change", () => {
          selected.size = size.value;
          changed();
        });
        label.addEventListener("input", () => {
          selected.label = label.value;
          changed();
        });
        form.appendChild(field("Type", spinnerType));
        form.appendChild(field("Variant", variant));
        form.appendChild(field("Size", size));
        form.appendChild(field("Label", label));
      } else if (type === "bs_carousel") {
        const controls = document.createElement("input");
        controls.type = "checkbox";
        controls.checked = selected.controls !== false;
        const indicators = document.createElement("input");
        indicators.type = "checkbox";
        indicators.checked = selected.indicators !== false;
        const fade = document.createElement("input");
        fade.type = "checkbox";
        fade.checked = !!selected.fade;
        const auto = document.createElement("input");
        auto.type = "checkbox";
        auto.checked = !!selected.auto;
        const items = textArea(
          (Array.isArray(selected.items) ? selected.items : [])
            .map((slide) => `${slide.image || ""}|${slide.title || ""}|${slide.caption || ""}|${slide.alt || ""}`)
            .join("\n"),
          10
        );
        controls.addEventListener("change", () => {
          selected.controls = controls.checked;
          changed();
        });
        indicators.addEventListener("change", () => {
          selected.indicators = indicators.checked;
          changed();
        });
        fade.addEventListener("change", () => {
          selected.fade = fade.checked;
          changed();
        });
        auto.addEventListener("change", () => {
          selected.auto = auto.checked;
          changed();
        });
        items.addEventListener("input", () => {
          selected.items = items.value
            .replace(/\r/g, "\n")
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean)
            .map((line) => {
              const parts = line.split("|").map((part) => part.trim());
              return {
                image: parts[0] || "",
                title: parts[1] || "",
                caption: parts[2] || "",
                alt: parts[3] || "",
              };
            });
          changed();
        });
        form.appendChild(field("Slides (image|title|caption|alt)", items));
        form.appendChild(field("Show controls", controls));
        form.appendChild(field("Show indicators", indicators));
        form.appendChild(field("Fade animation", fade));
        form.appendChild(field("Auto slide", auto));
      } else if (type === "bs_nav") {
        const style = selectInput(
          [
            { value: "tabs", label: "Tabs" },
            { value: "pills", label: "Pills" },
          ],
          selected.style || "tabs"
        );
        const fill = document.createElement("input");
        fill.type = "checkbox";
        fill.checked = !!selected.fill;
        const justified = document.createElement("input");
        justified.type = "checkbox";
        justified.checked = !!selected.justified;
        const vertical = document.createElement("input");
        vertical.type = "checkbox";
        vertical.checked = !!selected.vertical;
        const items = textArea(
          (Array.isArray(selected.items) ? selected.items : [])
            .map((row) => `${row.label || ""}|${row.url || ""}|${row.active ? "active" : ""}`)
            .join("\n"),
          10
        );
        style.addEventListener("change", () => {
          selected.style = style.value;
          changed();
        });
        fill.addEventListener("change", () => {
          selected.fill = fill.checked;
          changed();
        });
        justified.addEventListener("change", () => {
          selected.justified = justified.checked;
          changed();
        });
        vertical.addEventListener("change", () => {
          selected.vertical = vertical.checked;
          changed();
        });
        items.addEventListener("input", () => {
          selected.items = items.value
            .replace(/\r/g, "\n")
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean)
            .map((line, idx) => {
              const parts = line.split("|").map((part) => part.trim());
              return {
                label: parts[0] || "",
                url: parts[1] || "",
                active: parts[2] === "active" || idx === 0,
              };
            });
          changed();
        });
        form.appendChild(field("Style", style));
        form.appendChild(field("Links (label|url|active)", items));
        form.appendChild(field("Fill width", fill));
        form.appendChild(field("Justified", justified));
        form.appendChild(field("Vertical", vertical));
      } else if (type === "bs_modal") {
        const buttonText = textInput(selected.button_text || "");
        const buttonVariant = selectInput(
          [
            { value: "primary", label: "Primary" },
            { value: "secondary", label: "Secondary" },
            { value: "success", label: "Success" },
            { value: "danger", label: "Danger" },
            { value: "warning", label: "Warning" },
            { value: "info", label: "Info" },
            { value: "dark", label: "Dark" },
          ],
          selected.button_variant || "primary"
        );
        const title = textInput(selected.title || "");
        const textField = textArea(selected.text || "", 6);
        const size = selectInput(
          [
            { value: "", label: "Default" },
            { value: "sm", label: "Small" },
            { value: "lg", label: "Large" },
            { value: "xl", label: "Extra Large" },
          ],
          selected.size || ""
        );
        const centered = document.createElement("input");
        centered.type = "checkbox";
        centered.checked = !!selected.centered;
        const scrollable = document.createElement("input");
        scrollable.type = "checkbox";
        scrollable.checked = !!selected.scrollable;
        const fullscreen = document.createElement("input");
        fullscreen.type = "checkbox";
        fullscreen.checked = !!selected.fullscreen;
        const footerPrimary = textInput(selected.footer_primary_text || "");
        const footerSecondary = textInput(selected.footer_secondary_text || "");
        buttonText.addEventListener("input", () => {
          selected.button_text = buttonText.value;
          changed();
        });
        buttonVariant.addEventListener("change", () => {
          selected.button_variant = buttonVariant.value;
          changed();
        });
        title.addEventListener("input", () => {
          selected.title = title.value;
          changed();
        });
        textField.addEventListener("input", () => {
          selected.text = textField.value;
          changed();
        });
        size.addEventListener("change", () => {
          selected.size = size.value;
          changed();
        });
        centered.addEventListener("change", () => {
          selected.centered = centered.checked;
          changed();
        });
        scrollable.addEventListener("change", () => {
          selected.scrollable = scrollable.checked;
          changed();
        });
        fullscreen.addEventListener("change", () => {
          selected.fullscreen = fullscreen.checked;
          changed();
        });
        footerPrimary.addEventListener("input", () => {
          selected.footer_primary_text = footerPrimary.value;
          changed();
        });
        footerSecondary.addEventListener("input", () => {
          selected.footer_secondary_text = footerSecondary.value;
          changed();
        });
        form.appendChild(field("Button text", buttonText));
        form.appendChild(field("Button variant", buttonVariant));
        form.appendChild(field("Modal title", title));
        form.appendChild(field("Modal text", textField));
        form.appendChild(field("Size", size));
        form.appendChild(field("Centered", centered));
        form.appendChild(field("Scrollable body", scrollable));
        form.appendChild(field("Fullscreen", fullscreen));
        form.appendChild(field("Footer primary button", footerPrimary));
        form.appendChild(field("Footer secondary button", footerSecondary));
      } else if (type === "bs_toast") {
        const title = textInput(selected.title || "");
        const textField = textArea(selected.text || "", 6);
        const delay = numberInput(selected.delay || 5000, 1000, 20000);
        const autohide = document.createElement("input");
        autohide.type = "checkbox";
        autohide.checked = selected.autohide !== false;
        const variant = selectInput(
          [
            { value: "primary", label: "Primary" },
            { value: "secondary", label: "Secondary" },
            { value: "success", label: "Success" },
            { value: "danger", label: "Danger" },
            { value: "warning", label: "Warning" },
            { value: "info", label: "Info" },
            { value: "dark", label: "Dark" },
          ],
          selected.variant || "primary"
        );
        title.addEventListener("input", () => {
          selected.title = title.value;
          changed();
        });
        textField.addEventListener("input", () => {
          selected.text = textField.value;
          changed();
        });
        delay.addEventListener("input", () => {
          selected.delay = Number(delay.value || 5000);
          changed();
        });
        autohide.addEventListener("change", () => {
          selected.autohide = autohide.checked;
          changed();
        });
        variant.addEventListener("change", () => {
          selected.variant = variant.value;
          changed();
        });
        form.appendChild(field("Title", title));
        form.appendChild(field("Text", textField));
        form.appendChild(field("Autohide delay (ms)", delay));
        form.appendChild(field("Autohide", autohide));
        form.appendChild(field("Variant", variant));
      } else if (type === "bs_offcanvas") {
        const buttonText = textInput(selected.button_text || "");
        const buttonVariant = selectInput(
          [
            { value: "primary", label: "Primary" },
            { value: "secondary", label: "Secondary" },
            { value: "success", label: "Success" },
            { value: "danger", label: "Danger" },
            { value: "warning", label: "Warning" },
            { value: "info", label: "Info" },
            { value: "dark", label: "Dark" },
          ],
          selected.button_variant || "primary"
        );
        const title = textInput(selected.title || "");
        const textField = textArea(selected.text || "", 6);
        const placement = selectInput(
          [
            { value: "start", label: "Left" },
            { value: "end", label: "Right" },
            { value: "top", label: "Top" },
            { value: "bottom", label: "Bottom" },
          ],
          selected.placement || "end"
        );
        buttonText.addEventListener("input", () => {
          selected.button_text = buttonText.value;
          changed();
        });
        buttonVariant.addEventListener("change", () => {
          selected.button_variant = buttonVariant.value;
          changed();
        });
        title.addEventListener("input", () => {
          selected.title = title.value;
          changed();
        });
        textField.addEventListener("input", () => {
          selected.text = textField.value;
          changed();
        });
        placement.addEventListener("change", () => {
          selected.placement = placement.value;
          changed();
        });
        form.appendChild(field("Button text", buttonText));
        form.appendChild(field("Button variant", buttonVariant));
        form.appendChild(field("Panel title", title));
        form.appendChild(field("Panel text", textField));
        form.appendChild(field("Placement", placement));
      } else if (type === "bs_timeline") {
        const title = textInput(selected.title || "");
        const items = textArea(
          (Array.isArray(selected.items) ? selected.items : [])
            .map((row) => `${row.date || ""}|${row.title || ""}|${row.text || ""}`)
            .join("\n"),
          8
        );
        title.addEventListener("input", () => {
          selected.title = title.value;
          changed();
        });
        items.addEventListener("input", () => {
          selected.items = parseTimelineLines(items.value);
          changed();
        });
        form.appendChild(field("Section title", title));
        form.appendChild(field("Items (date|title|text)", items));
      } else if (type === "bs_pricing_table") {
        const title = textInput(selected.title || "");
        const subtitle = textInput(selected.subtitle || "");
        const plans = textArea(
          (Array.isArray(selected.plans) ? selected.plans : [])
            .map((plan) =>
              `${plan.title || ""}|${plan.price || ""}|${plan.period || ""}|${(Array.isArray(plan.features) ? plan.features : []).join(";")}|${plan.button_label || ""}|${plan.button_url || ""}|${plan.recommended ? "recommended" : ""}`
            )
            .join("\n"),
          10
        );
        title.addEventListener("input", () => {
          selected.title = title.value;
          changed();
        });
        subtitle.addEventListener("input", () => {
          selected.subtitle = subtitle.value;
          changed();
        });
        plans.addEventListener("input", () => {
          selected.plans = parsePricingLines(plans.value);
          changed();
        });
        form.appendChild(field("Section title", title));
        form.appendChild(field("Section subtitle", subtitle));
        form.appendChild(field("Plans (title|price|period|f1;f2|button|url|recommended)", plans));
      } else if (type === "bs_dropdown") {
        const buttonText = textInput(selected.button_text || "Menu");
        const buttonVariant = selectInput(
          [
            { value: "primary", label: "Primary" },
            { value: "secondary", label: "Secondary" },
            { value: "success", label: "Success" },
            { value: "danger", label: "Danger" },
            { value: "warning", label: "Warning" },
            { value: "info", label: "Info" },
            { value: "dark", label: "Dark" },
          ],
          selected.button_variant || "primary"
        );
        const align = selectInput(
          [
            { value: "", label: "Default" },
            { value: "start", label: "Start" },
            { value: "end", label: "End" },
          ],
          selected.align || ""
        );
        const items = textArea(
          (Array.isArray(selected.items) ? selected.items : [])
            .map((row) => `${row.label || ""}|${row.url || ""}|${row.divider_before ? "divider" : ""}`)
            .join("\n"),
          8
        );
        buttonText.addEventListener("input", () => {
          selected.button_text = buttonText.value;
          changed();
        });
        buttonVariant.addEventListener("change", () => {
          selected.button_variant = buttonVariant.value;
          changed();
        });
        align.addEventListener("change", () => {
          selected.align = align.value;
          changed();
        });
        items.addEventListener("input", () => {
          selected.items = items.value
            .replace(/\r/g, "\n")
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean)
            .map((line) => {
              const parts = line.split("|").map((part) => part.trim());
              return {
                label: parts[0] || "",
                url: parts[1] || "#",
                divider_before: parts[2] === "divider",
              };
            });
          changed();
        });
        form.appendChild(field("Button text", buttonText));
        form.appendChild(field("Button variant", buttonVariant));
        form.appendChild(field("Alignment", align));
        form.appendChild(field("Items (label|url|divider)", items));
      } else if (type === "bs_navbar") {
        const brand = textInput(selected.brand || "VXcloud");
        const brandUrl = textInput(selected.brand_url || "/");
        const expand = selectInput(
          [
            { value: "sm", label: "sm" },
            { value: "md", label: "md" },
            { value: "lg", label: "lg" },
            { value: "xl", label: "xl" },
            { value: "xxl", label: "xxl" },
            { value: "", label: "Always expanded" },
          ],
          selected.expand || "lg"
        );
        const theme = selectInput(
          [
            { value: "dark", label: "Dark" },
            { value: "light", label: "Light" },
          ],
          selected.theme || "dark"
        );
        const bg = textInput(selected.bg || "dark");
        const links = textArea(
          (Array.isArray(selected.items) ? selected.items : [])
            .map((row) => `${row.label || ""}|${row.url || ""}`)
            .join("\n"),
          8
        );
        brand.addEventListener("input", () => {
          selected.brand = brand.value;
          changed();
        });
        brandUrl.addEventListener("input", () => {
          selected.brand_url = brandUrl.value;
          changed();
        });
        expand.addEventListener("change", () => {
          selected.expand = expand.value;
          changed();
        });
        theme.addEventListener("change", () => {
          selected.theme = theme.value;
          changed();
        });
        bg.addEventListener("input", () => {
          selected.bg = bg.value;
          changed();
        });
        links.addEventListener("input", () => {
          selected.items = links.value
            .replace(/\r/g, "\n")
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean)
            .map((line) => {
              const parts = line.split("|").map((part) => part.trim());
              return { label: parts[0] || "", url: parts[1] || "#" };
            });
          changed();
        });
        form.appendChild(field("Brand", brand));
        form.appendChild(field("Brand URL", brandUrl));
        form.appendChild(field("Expand breakpoint", expand));
        form.appendChild(field("Theme", theme));
        form.appendChild(field("Background class suffix", bg, "Example: dark, primary, light"));
        form.appendChild(field("Links (label|url)", links));
      } else if (type === "bs_ratio") {
        const ratio = selectInput(
          [
            { value: "1x1", label: "1x1" },
            { value: "4x3", label: "4x3" },
            { value: "16x9", label: "16x9" },
            { value: "21x9", label: "21x9" },
          ],
          selected.ratio || "16x9"
        );
        const html = textArea(selected.html || "", 8);
        ratio.addEventListener("change", () => {
          selected.ratio = ratio.value;
          changed();
        });
        html.addEventListener("input", () => {
          selected.html = html.value;
          changed();
        });
        form.appendChild(field("Ratio", ratio));
        form.appendChild(field("Inner HTML (iframe/video/img)", html));
      } else if (type === "bs_placeholder") {
        const lines = numberInput(selected.lines || 3, 1, 12);
        const width = numberInput(selected.width || 100, 10, 100);
        const size = selectInput(
          [
            { value: "sm", label: "Small" },
            { value: "md", label: "Medium" },
            { value: "lg", label: "Large" },
          ],
          selected.size || "md"
        );
        const glow = document.createElement("input");
        glow.type = "checkbox";
        glow.checked = !!selected.glow;
        lines.addEventListener("input", () => {
          selected.lines = Number(lines.value || 3);
          changed();
        });
        width.addEventListener("input", () => {
          selected.width = Number(width.value || 100);
          changed();
        });
        size.addEventListener("change", () => {
          selected.size = size.value;
          changed();
        });
        glow.addEventListener("change", () => {
          selected.glow = glow.checked;
          changed();
        });
        form.appendChild(field("Lines", lines));
        form.appendChild(field("Line width %", width));
        form.appendChild(field("Size", size));
        form.appendChild(field("Glow animation", glow));
      } else if (type === "bs_divider") {
        const spacing = numberInput(selected.spacing || 24, 0, 120);
        const label = textInput(selected.label || "");
        spacing.addEventListener("input", () => {
          selected.spacing = Number(spacing.value || 24);
          changed();
        });
        label.addEventListener("input", () => {
          selected.label = label.value;
          changed();
        });
        form.appendChild(field("Vertical spacing (px)", spacing));
        form.appendChild(field("Label (optional)", label));
      } else if (type === "rows" || type === "raws") {
        form.appendChild(renderRowsEditor(selected));
      } else if (type === "cards_slider") {
        const title = textInput(selected.title || "");
        const subtitle = textArea(selected.subtitle || "", 4);
        subtitle.placeholder = "Short description above the cards";
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
        items.placeholder = "Card title|Card text";
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
        form.appendChild(field("Cards (title|text, one card per line)", items, "Each line creates one card."));
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
      sync();
    }

    renderAll();

    const form = source.closest("form");
    if (form) form.addEventListener("submit", sync);
  }

  function init() {
    const seen = new Set();
    SOURCE_SELECTORS.forEach((selector) => {
      document.querySelectorAll(selector).forEach((source) => {
        if (seen.has(source)) return;
        seen.add(source);
        mountEditor(source);
      });
    });
  }

  function initWithRetries() {
    init();
    // Some admin themes rebuild form rows after load; remount editor a few times.
    let attempts = 0;
    const maxAttempts = 12;
    const timer = window.setInterval(() => {
      attempts += 1;
      init();
      if (attempts >= maxAttempts) {
        window.clearInterval(timer);
      }
    }, 500);

    if (typeof MutationObserver !== "undefined") {
      const observer = new MutationObserver(() => {
        init();
      });
      observer.observe(document.body, { childList: true, subtree: true });
      window.setTimeout(() => observer.disconnect(), 15000);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initWithRetries);
  } else {
    initWithRetries();
  }
})();

