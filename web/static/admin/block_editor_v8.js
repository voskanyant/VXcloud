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
    { value: "bs_dropdown", label: "Bootstrap Dropdown", icon: "DD", group: "Bootstrap Components" },
    { value: "bs_navbar", label: "Bootstrap Navbar", icon: "NB", group: "Bootstrap Components" },
    { value: "bs_ratio", label: "Bootstrap Ratio", icon: "RT", group: "Bootstrap Components" },
    { value: "bs_placeholder", label: "Bootstrap Placeholder", icon: "PH", group: "Bootstrap Components" },
    { value: "bs_container", label: "Bootstrap Container", icon: "CT", group: "Bootstrap Layout" },
    { value: "bs_rows", label: "Bootstrap Rows", icon: "R", group: "Bootstrap Layout" },
    { value: "bs_spacer", label: "Bootstrap Spacer", icon: "S", group: "Bootstrap Layout" },
  ];

  const GROUPS = ["Bootstrap Content", "Bootstrap Components", "Bootstrap Layout"];
  const BLOCK_UID = Symbol("be_uid");
  const COLUMN_CHILD_TYPES = [
    "bs_paragraph",
    "bs_heading",
    "bs_list",
    "bs_quote",
    "bs_button",
    "bs_button_group",
    "bs_image",
    "bs_embed",
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
    "bs_dropdown",
    "bs_navbar",
    "bs_ratio",
    "bs_placeholder",
    "bs_container",
    "bs_rows",
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

  function safeStorageRemove(key) {
    try {
      if (!window.localStorage) return;
      window.localStorage.removeItem(key);
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
    autoResizeTextarea(input, rows || 4);
    return input;
  }

  function autoResizeTextarea(input, minRows) {
    if (!input) return;
    const minHeight = Math.max(68, (Number(minRows || input.rows || 4) * 20) + 16);

    const resize = () => {
      input.style.height = "auto";
      const next = Math.max(minHeight, input.scrollHeight + 2);
      input.style.height = `${next}px`;
    };

    resize();
    input.addEventListener("input", resize);
    input.addEventListener("focus", resize);
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

  function field(label, control, hint, options) {
    const wrapper = document.createElement("label");
    wrapper.className = "be-field";
    const opts = options || {};
    if (opts.compact) wrapper.classList.add("is-compact");
    if (opts.wide) wrapper.classList.add("is-wide");
    if (opts.toned) wrapper.classList.add("is-toned");

    if (!opts.compact) {
      const tagName = String(control.tagName || "").toLowerCase();
      if (tagName === "textarea") wrapper.classList.add("is-wide");
      if (tagName === "input" && String(control.type || "").toLowerCase() === "checkbox") {
        wrapper.classList.add("is-toggle");
      }
    }

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

  function editorBanner(meta, description) {
    const banner = document.createElement("div");
    banner.className = "be-editor-banner";
    banner.innerHTML =
      `<span class="be-editor-eyebrow">${meta.icon} ${meta.label}</span>` +
      `<strong class="be-editor-name">${meta.label}</strong>` +
      `<p class="be-editor-description">${description}</p>`;
    return banner;
  }

  function blockEditorDescription(type) {
    const legacy = toLegacyType(type || "bs_paragraph");
    if (legacy === "paragraph") return "Write body copy directly in the document flow. Best for long-form article text.";
    if (legacy === "heading") return "Use this for clear section hierarchy. Keep headings short and scannable.";
    if (legacy === "list") return "One line becomes one list item. Use lists for steps, requirements, and summaries.";
    if (legacy === "quote") return "Highlight a testimonial, note, or short emphasized statement.";
    if (legacy === "button") return "Primary action block. Keep the label explicit and the target URL clean.";
    if (legacy === "bs_alert") return "Short notice or warning. Keep title and body compact so the callout stays readable.";
    if (legacy === "bs_badge") return "Small status marker. Use it for labels like New, Pro, Beta, or Active.";
    if (legacy === "bs_card") return "Compact teaser card. Best for features, services, or short content summaries.";
    if (legacy === "rows" || legacy === "raws" || legacy === "bs_container") {
      return "Structural layout block. Arrange rows, columns, and nested bootstrap content here.";
    }
    return "Edit the selected block inline. Use compact controls for quick content changes and ordering.";
  }

  function quickEditOnlyTypes() {
    return new Set(["paragraph", "heading", "quote", "list", "button", "bs_alert", "bs_badge", "bs_card"]);
  }

  function supportsQuickEdit(type) {
    return quickEditOnlyTypes().has(toLegacyType(type || "bs_paragraph"));
  }

  function buildVariantOptions(values) {
    return values.map((value) => ({
      value,
      label: value.charAt(0).toUpperCase() + value.slice(1),
    }));
  }

  function quickEditShell(host, title, description) {
    const shell = document.createElement("div");
    shell.className = "be-quick-shell";
    const head = document.createElement("div");
    head.className = "be-quick-head";
    const heading = document.createElement("strong");
    heading.textContent = title;
    const hint = document.createElement("span");
    hint.textContent = description;
    head.appendChild(heading);
    head.appendChild(hint);
    shell.appendChild(head);
    host.appendChild(shell);
    return shell;
  }

  function renderCanvasQuickEdit(block, host, onSync, onCommit) {
    const type = toLegacyType(block.type || "bs_paragraph");
    host.innerHTML = "";
    host.className = "be-card-quick-edit";

    const syncOnly = () => {
      onSync();
    };

    const commit = () => {
      onCommit();
    };

    if (type === "paragraph") {
      const shell = quickEditShell(host, "Paragraph", "Edit the text directly in the document flow.");
      const text = textArea(block.text || "", 5);
      text.classList.add("be-quick-textarea");
      text.placeholder = "Write paragraph text...";
      text.addEventListener("input", () => {
        block.text = text.value;
        syncOnly();
      });
      text.addEventListener("blur", commit);
      shell.appendChild(text);
      return true;
    }

    if (type === "heading") {
      const shell = quickEditShell(host, "Heading", "Keep headings concise and use the right level for hierarchy.");
      const grid = document.createElement("div");
      grid.className = "be-quick-grid";
      const title = textInput(block.text || "");
      title.placeholder = "Heading text";
      title.classList.add("be-quick-input");
      title.addEventListener("input", () => {
        block.text = title.value;
        syncOnly();
      });
      title.addEventListener("blur", commit);

      const level = selectInput(
        [
          { value: 1, label: "H1" },
          { value: 2, label: "H2" },
          { value: 3, label: "H3" },
          { value: 4, label: "H4" },
        ],
        block.level || 2
      );
      level.classList.add("be-quick-select");
      level.addEventListener("change", () => {
        block.level = Number(level.value);
        syncOnly();
        commit();
      });

      grid.appendChild(field("Heading", title, "", { wide: true }));
      grid.appendChild(field("Level", level, "", { compact: true }));
      shell.appendChild(grid);
      return true;
    }

    if (type === "quote") {
      const shell = quickEditShell(host, "Quote", "Use this for short highlighted statements, testimonials, or notes.");
      const quote = textArea(block.text || "", 4);
      quote.classList.add("be-quick-textarea");
      quote.placeholder = "Quote text";
      quote.addEventListener("input", () => {
        block.text = quote.value;
        syncOnly();
      });
      quote.addEventListener("blur", commit);

      const author = textInput(block.cite || "");
      author.placeholder = "Author / source";
      author.classList.add("be-quick-input");
      author.addEventListener("input", () => {
        block.cite = author.value;
        syncOnly();
      });
      author.addEventListener("blur", commit);

      shell.appendChild(quote);
      shell.appendChild(field("Author", author, "", { compact: true }));
      return true;
    }

    if (type === "list") {
      const shell = quickEditShell(host, "List", "Each line becomes a separate list item.");
      const orderedWrap = document.createElement("div");
      orderedWrap.className = "be-quick-inline";
      const ordered = document.createElement("input");
      ordered.type = "checkbox";
      ordered.checked = !!block.ordered;
      ordered.addEventListener("change", () => {
        block.ordered = ordered.checked;
        syncOnly();
        commit();
      });
      const orderedLabel = document.createElement("span");
      orderedLabel.textContent = "Ordered list";
      orderedWrap.appendChild(ordered);
      orderedWrap.appendChild(orderedLabel);

      const items = textArea(Array.isArray(block.items) ? block.items.join("\n") : "", 5);
      items.classList.add("be-quick-textarea");
      items.placeholder = "One line = one list item";
      items.addEventListener("input", () => {
        block.items = items.value
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean);
        syncOnly();
      });
      items.addEventListener("blur", commit);

      shell.appendChild(orderedWrap);
      shell.appendChild(items);
      return true;
    }

    if (type === "button") {
      const shell = quickEditShell(host, "Button", "Set a clear label and target. Use one primary action per block.");
      const grid = document.createElement("div");
      grid.className = "be-quick-grid";
      const label = textInput(block.label || "");
      label.placeholder = "Button label";
      label.classList.add("be-quick-input");
      label.addEventListener("input", () => {
        block.label = label.value;
        syncOnly();
      });
      label.addEventListener("blur", commit);

      const url = textInput(block.url || "");
      url.placeholder = "/target-or-url";
      url.classList.add("be-quick-input");
      url.addEventListener("input", () => {
        block.url = url.value;
        syncOnly();
      });
      url.addEventListener("blur", commit);

      const style = selectInput(
        buildVariantOptions(["primary", "secondary", "outline-primary", "outline-dark", "link"]),
        block.style || "primary"
      );
      style.classList.add("be-quick-select");
      style.addEventListener("change", () => {
        block.style = style.value;
        syncOnly();
        commit();
      });

      grid.appendChild(field("Label", label, "", { compact: true }));
      grid.appendChild(field("Style", style, "", { compact: true }));
      grid.appendChild(field("URL", url, "", { wide: true }));
      shell.appendChild(grid);
      return true;
    }

    if (type === "bs_alert") {
      const shell = quickEditShell(host, "Alert", "Best for concise notices, warnings, and inline support messages.");
      const grid = document.createElement("div");
      grid.className = "be-quick-grid";

      const variant = selectInput(
        buildVariantOptions(["primary", "secondary", "success", "danger", "warning", "info", "light", "dark"]),
        block.variant || "info"
      );
      variant.classList.add("be-quick-select");
      variant.addEventListener("change", () => {
        block.variant = variant.value;
        syncOnly();
        commit();
      });

      const title = textInput(block.title || "");
      title.placeholder = "Alert title";
      title.classList.add("be-quick-input");
      title.addEventListener("input", () => {
        block.title = title.value;
        syncOnly();
      });
      title.addEventListener("blur", commit);

      const body = textArea(block.text || "", 4);
      body.classList.add("be-quick-textarea");
      body.placeholder = "Alert text";
      body.addEventListener("input", () => {
        block.text = body.value;
        syncOnly();
      });
      body.addEventListener("blur", commit);

      grid.appendChild(field("Variant", variant, "", { compact: true }));
      grid.appendChild(field("Title", title, "", { compact: true }));
      shell.appendChild(grid);
      shell.appendChild(body);
      return true;
    }

    if (type === "bs_badge") {
      const shell = quickEditShell(host, "Badge", "Small accent label for state, category, or feature tag.");
      const grid = document.createElement("div");
      grid.className = "be-quick-grid";

      const text = textInput(block.text || "");
      text.placeholder = "Badge text";
      text.classList.add("be-quick-input");
      text.addEventListener("input", () => {
        block.text = text.value;
        syncOnly();
      });
      text.addEventListener("blur", commit);

      const variant = selectInput(
        buildVariantOptions(["primary", "secondary", "success", "danger", "warning", "info", "light", "dark"]),
        block.variant || "primary"
      );
      variant.classList.add("be-quick-select");
      variant.addEventListener("change", () => {
        block.variant = variant.value;
        syncOnly();
        commit();
      });

      const pillWrap = document.createElement("label");
      pillWrap.className = "be-quick-toggle";
      const pill = document.createElement("input");
      pill.type = "checkbox";
      pill.checked = !!block.pill;
      pill.addEventListener("change", () => {
        block.pill = pill.checked;
        syncOnly();
        commit();
      });
      const pillText = document.createElement("span");
      pillText.textContent = "Rounded";
      pillWrap.appendChild(pill);
      pillWrap.appendChild(pillText);

      grid.appendChild(field("Text", text, "", { compact: true }));
      grid.appendChild(field("Variant", variant, "", { compact: true }));
      shell.appendChild(grid);
      shell.appendChild(pillWrap);
      return true;
    }

    if (type === "bs_card") {
      const shell = quickEditShell(host, "Card", "Use cards for feature blurbs, service tiles, and short content teasers.");
      const grid = document.createElement("div");
      grid.className = "be-quick-grid";

      const title = textInput(block.title || "");
      title.placeholder = "Card title";
      title.classList.add("be-quick-input");
      title.addEventListener("input", () => {
        block.title = title.value;
        syncOnly();
      });
      title.addEventListener("blur", commit);

      const image = textInput(block.image || "");
      image.placeholder = "Image URL (optional)";
      image.classList.add("be-quick-input");
      image.addEventListener("input", () => {
        block.image = image.value;
        syncOnly();
      });
      image.addEventListener("blur", commit);

      const text = textArea(block.text || "", 4);
      text.classList.add("be-quick-textarea");
      text.placeholder = "Card text";
      text.addEventListener("input", () => {
        block.text = text.value;
        syncOnly();
      });
      text.addEventListener("blur", commit);

      const ctaLabel = textInput(block.button_label || "");
      ctaLabel.placeholder = "CTA label";
      ctaLabel.classList.add("be-quick-input");
      ctaLabel.addEventListener("input", () => {
        block.button_label = ctaLabel.value;
        syncOnly();
      });
      ctaLabel.addEventListener("blur", commit);

      const ctaUrl = textInput(block.button_url || "");
      ctaUrl.placeholder = "/details";
      ctaUrl.classList.add("be-quick-input");
      ctaUrl.addEventListener("input", () => {
        block.button_url = ctaUrl.value;
        syncOnly();
      });
      ctaUrl.addEventListener("blur", commit);

      grid.appendChild(field("Title", title, "", { compact: true }));
      grid.appendChild(field("Image", image, "", { compact: true }));
      shell.appendChild(grid);
      shell.appendChild(text);

      const ctaGrid = document.createElement("div");
      ctaGrid.className = "be-quick-grid";
      ctaGrid.appendChild(field("CTA label", ctaLabel, "", { compact: true }));
      ctaGrid.appendChild(field("CTA URL", ctaUrl, "", { compact: true }));
      shell.appendChild(ctaGrid);
      return true;
    }

    return false;
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
      groupCollapsed: {},
      collapsedBlocks: {},
      rowCollapsed: {},
      colCollapsed: {},
      nestedCollapsed: {},
      nestedSelected: {},
      selectedRowByParent: {},
      selectedColumnByRow: {},
      compactMode: safeStorageGet("be.compactMode") === "1",
      uidSeq: 1,
    };
    if (state.blocks.length) state.selectedIndex = 0;

    const HISTORY_LIMIT = 120;
    const sourceKey = source.name || source.id || "content_blocks";
    const autosaveKey = `be.autosave.${window.location.pathname}.${sourceKey}`;
    const history = [];
    let historyIndex = -1;
    let autosaveBadge = null;
    let undoBtn = null;
    let redoBtn = null;
    let historyDebounceTimer = null;
    let autosaveTimer = null;
    let isRestoringHistory = false;

    const ROW_PRESETS = [
      { value: "12", label: "1 column (12/12)", widths: [12] },
      { value: "6-6", label: "2 columns (6/6 + 6/6)", widths: [6, 6] },
      { value: "4-4-4", label: "3 columns (4/4 + 4/4 + 4/4)", widths: [4, 4, 4] },
      { value: "3-9", label: "2 columns (3/12 + 9/12)", widths: [3, 9] },
      { value: "9-3", label: "2 columns (9/12 + 3/12)", widths: [9, 3] },
      { value: "3-3-3-3", label: "4 columns (3/3/3/3)", widths: [3, 3, 3, 3] },
    ];

    function rowPresetOptions(includeCustom) {
      const options = ROW_PRESETS.map((preset) => ({ value: preset.value, label: preset.label }));
      if (includeCustom) options.unshift({ value: "custom", label: "Custom (keep current)" });
      return options;
    }

    function rowPresetFromColumns(columns) {
      if (!Array.isArray(columns) || !columns.length) return "custom";
      const key = columns
        .map((col) => {
          const width = Number(col && col.width ? col.width : 6) || 6;
          return width < 1 ? 1 : width > 12 ? 12 : width;
        })
        .join("-");
      return ROW_PRESETS.some((preset) => preset.value === key) ? key : "custom";
    }

    function blockUid(block) {
      if (!block || typeof block !== "object") return "";
      if (!block[BLOCK_UID]) {
        block[BLOCK_UID] = `b${state.uidSeq++}`;
      }
      return block[BLOCK_UID];
    }

    function setCompactMode(nextValue) {
      state.compactMode = !!nextValue;
      safeStorageSet("be.compactMode", state.compactMode ? "1" : "0");
    }

    function allBlocksCollapsed() {
      if (!state.blocks.length) return false;
      return state.blocks.every((block) => !!state.collapsedBlocks[blockUid(block)]);
    }

    function setAllBlocksCollapsed(collapsed) {
      state.blocks.forEach((block) => {
        state.collapsedBlocks[blockUid(block)] = !!collapsed;
      });
    }

    function isTypingContext(target) {
      if (!target || !(target instanceof Element)) return false;
      if (target.closest("textarea, input, select, [contenteditable='true']")) return true;
      if (target.closest(".be-inspector-form")) return true;
      return false;
    }

    function cloneBlocks(input) {
      try {
        return JSON.parse(JSON.stringify(input || []));
      } catch (_error) {
        return [];
      }
    }

    function blocksToJSON(input) {
      try {
        return JSON.stringify(input || []);
      } catch (_error) {
        return "[]";
      }
    }

    function updateHistoryButtons() {
      if (undoBtn) undoBtn.disabled = historyIndex <= 0;
      if (redoBtn) redoBtn.disabled = historyIndex < 0 || historyIndex >= history.length - 1;
    }

    function setAutosaveState(status, message) {
      if (!autosaveBadge) return;
      autosaveBadge.classList.remove("is-dirty", "is-saving", "is-saved");
      if (status) autosaveBadge.classList.add(`is-${status}`);
      autosaveBadge.textContent = message || "";
    }

    function writeAutosaveSnapshot() {
      safeStorageSet(autosaveKey, blocksToJSON(state.blocks));
      safeStorageSet(`${autosaveKey}.ts`, String(Date.now()));
      setAutosaveState("saved", "Saved");
    }

    function clearAutosaveSnapshot() {
      safeStorageRemove(autosaveKey);
      safeStorageRemove(`${autosaveKey}.ts`);
      setAutosaveState("saved", "Saved");
    }

    function scheduleAutosave() {
      setAutosaveState("dirty", "Unsaved");
      if (autosaveTimer) window.clearTimeout(autosaveTimer);
      autosaveTimer = window.setTimeout(() => {
        setAutosaveState("saving", "Saving...");
        writeAutosaveSnapshot();
      }, 700);
    }

    function pushHistorySnapshot() {
      if (isRestoringHistory) return;
      const snapshot = cloneBlocks(state.blocks);
      const serialized = blocksToJSON(snapshot);
      if (historyIndex >= 0) {
        const currentSerialized = blocksToJSON(history[historyIndex]);
        if (currentSerialized === serialized) {
          updateHistoryButtons();
          return;
        }
      }
      if (historyIndex < history.length - 1) {
        history.splice(historyIndex + 1);
      }
      history.push(snapshot);
      if (history.length > HISTORY_LIMIT) {
        history.shift();
      }
      historyIndex = history.length - 1;
      updateHistoryButtons();
    }

    function queueHistorySnapshot() {
      if (historyDebounceTimer) window.clearTimeout(historyDebounceTimer);
      historyDebounceTimer = window.setTimeout(() => {
        pushHistorySnapshot();
      }, 350);
    }

    function applyHistorySnapshot(nextIndex) {
      if (nextIndex < 0 || nextIndex >= history.length) return;
      isRestoringHistory = true;
      historyIndex = nextIndex;
      state.blocks = cloneBlocks(history[nextIndex]);
      if (!state.blocks.length) state.selectedIndex = -1;
      else if (state.selectedIndex < 0 || state.selectedIndex >= state.blocks.length) {
        state.selectedIndex = Math.min(state.blocks.length - 1, 0);
      }
      renderPanels();
      isRestoringHistory = false;
      updateHistoryButtons();
      scheduleAutosave();
    }

    function undoHistory() {
      applyHistorySnapshot(historyIndex - 1);
    }

    function redoHistory() {
      applyHistorySnapshot(historyIndex + 1);
    }

    function restoreAutosaveIfAvailable() {
      const raw = safeStorageGet(autosaveKey);
      if (!raw) return;
      const current = blocksToJSON(state.blocks);
      if (raw === current) {
        setAutosaveState("saved", "Saved");
        return;
      }
      const ts = safeStorageGet(`${autosaveKey}.ts`);
      const dateText = ts ? new Date(Number(ts)).toLocaleString() : "";
      const shouldRestore = window.confirm(
        `Unsaved draft found${dateText ? ` (${dateText})` : ""}. Restore it?`
      );
      if (!shouldRestore) {
        setAutosaveState("saved", "Draft skipped");
        return;
      }
      state.blocks = parseJSON(raw);
      state.selectedIndex = state.blocks.length ? 0 : -1;
      setAutosaveState("saved", "Draft restored");
    }

    function sync() {
      source.value = JSON.stringify(state.blocks);
    }

    function getFocusableControls(scope) {
      if (!scope) return [];
      return Array.from(scope.querySelectorAll("input, textarea, select, button"));
    }

    function captureInlineEditorSnapshot() {
      const stage = center.querySelector(".be-canvas-stage");
      const snapshot = {
        stageScrollTop: stage ? stage.scrollTop : 0,
        focus: null,
      };
      if (!stage) return snapshot;

      const active = document.activeElement;
      if (!active) return snapshot;
      if (!stage.contains(active)) return snapshot;

      const controls = getFocusableControls(stage);
      const controlIndex = controls.indexOf(active);
      if (controlIndex < 0) return snapshot;

      const focus = {
        index: controlIndex,
        tagName: active.tagName,
        type: active.type || "",
      };

      if (typeof active.selectionStart === "number" && typeof active.selectionEnd === "number") {
        focus.selectionStart = active.selectionStart;
        focus.selectionEnd = active.selectionEnd;
      }
      if (typeof active.scrollTop === "number") {
        focus.scrollTop = active.scrollTop;
      }

      snapshot.focus = focus;
      return snapshot;
    }

    function restoreInlineEditorSnapshot(snapshot) {
      const stage = center.querySelector(".be-canvas-stage");
      if (stage && snapshot && typeof snapshot.stageScrollTop === "number") {
        stage.scrollTop = snapshot.stageScrollTop;
      }
      if (!snapshot || !snapshot.focus || !stage) return;

      const controls = getFocusableControls(stage);
      let target = controls[snapshot.focus.index] || null;

      if (
        target &&
        snapshot.focus.tagName &&
        String(target.tagName || "").toUpperCase() !== String(snapshot.focus.tagName || "").toUpperCase()
      ) {
        target = controls.find((el) => String(el.tagName || "").toUpperCase() === String(snapshot.focus.tagName || "").toUpperCase()) || null;
      }
      if (!target) return;

      try {
        target.focus({ preventScroll: true });
      } catch (_error) {
        target.focus();
      }

      if (
        typeof snapshot.focus.selectionStart === "number" &&
        typeof snapshot.focus.selectionEnd === "number" &&
        typeof target.setSelectionRange === "function"
      ) {
        const max = typeof target.value === "string" ? target.value.length : snapshot.focus.selectionEnd;
        const start = Math.max(0, Math.min(snapshot.focus.selectionStart, max));
        const end = Math.max(start, Math.min(snapshot.focus.selectionEnd, max));
        target.setSelectionRange(start, end);
      }
      if (typeof snapshot.focus.scrollTop === "number" && typeof target.scrollTop === "number") {
        target.scrollTop = snapshot.focus.scrollTop;
      }
    }

    function renderCanvasPreserveInlineFocus() {
      const snapshot = captureInlineEditorSnapshot();
      renderCanvas();
      restoreInlineEditorSnapshot(snapshot);
    }

    function renderPanels() {
      renderLeft();
      renderCanvas();
      sync();
    }

    function selectBlock(index) {
      state.selectedIndex = index;
      renderPanels();
    }

    function addBlock(type) {
      state.blocks.push(defaultsFor(type));
      state.selectedIndex = state.blocks.length - 1;
      renderPanels();
      pushHistorySnapshot();
      scheduleAutosave();
    }

    function insertBlockAt(index, type) {
      const at = Math.max(0, Math.min(index, state.blocks.length));
      state.blocks.splice(at, 0, defaultsFor(type));
      state.selectedIndex = at;
      renderPanels();
      pushHistorySnapshot();
      scheduleAutosave();
    }

    function removeSelected() {
      if (state.selectedIndex < 0 || state.selectedIndex >= state.blocks.length) return;
      state.blocks.splice(state.selectedIndex, 1);
      if (!state.blocks.length) state.selectedIndex = -1;
      else if (state.selectedIndex >= state.blocks.length) state.selectedIndex = state.blocks.length - 1;
      renderPanels();
      pushHistorySnapshot();
      scheduleAutosave();
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
      renderPanels();
      pushHistorySnapshot();
      scheduleAutosave();
    }

    function duplicateSelected() {
      const index = state.selectedIndex;
      if (index < 0 || index >= state.blocks.length) return;
      const clone = JSON.parse(JSON.stringify(state.blocks[index]));
      state.blocks.splice(index + 1, 0, clone);
      state.selectedIndex = index + 1;
      renderPanels();
      pushHistorySnapshot();
      scheduleAutosave();
    }

    function displayTypeName(block) {
      const type = toBootstrapType(block && block.type ? block.type : "bs_paragraph");
      if (type === "bs_container") return "Section";
      if (type === "bs_rows") return "Row";
      if (type === "bs_columns") return "Columns";
      if (type === "bs_paragraph") return "Text";
      return blockMeta(type).label;
    }

    function structureNode(label, depth, active, onClick) {
      const node = document.createElement("button");
      node.type = "button";
      node.className = "be-structure-item";
      node.style.setProperty("--be-depth", String(depth || 0));
      if (active) node.classList.add("is-active");
      node.textContent = label;
      node.addEventListener("click", onClick);
      return node;
    }

    function renderLeft() {
      left.innerHTML = "";

      const head = document.createElement("header");
      head.className = "be-left-head be-builder-head";
      head.innerHTML = "<strong>UX Builder</strong><span>VXcloud editor</span>";

      const quick = document.createElement("div");
      quick.className = "be-builder-quick";
      [
        { label: "+ Add Section", type: "bs_container" },
        { label: "+ Add Row", type: "bs_rows" },
        { label: "+ Add Text", type: "bs_paragraph" },
      ].forEach((item) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "button be-builder-btn";
        btn.textContent = item.label;
        btn.addEventListener("click", () => addBlock(item.type));
        quick.appendChild(btn);
      });

      const structureWrap = document.createElement("section");
      structureWrap.className = "be-structure";
      const structureTitle = document.createElement("div");
      structureTitle.className = "be-structure-title";
      structureTitle.textContent = "Content Structure";
      structureWrap.appendChild(structureTitle);

      if (!state.blocks.length) {
        const empty = document.createElement("p");
        empty.className = "be-structure-empty";
        empty.textContent = "No blocks yet. Add first section.";
        structureWrap.appendChild(empty);
      } else {
        const list = document.createElement("div");
        list.className = "be-structure-list";

        state.blocks.forEach((block, index) => {
          const rootActive = state.selectedIndex === index;
          list.appendChild(
            structureNode(
              `${index + 1}. ${displayTypeName(block)}`,
              0,
              rootActive,
              () => {
                state.selectedIndex = index;
                renderPanels();
              }
            )
          );

          const rows = Array.isArray(block.rows) ? block.rows : [];
          rows.forEach((row, rowIndex) => {
            list.appendChild(
              structureNode(
                `Row ${rowIndex + 1}`,
                1,
                false,
                () => {
                  state.selectedIndex = index;
                  renderPanels();
                }
              )
            );
            const columns = Array.isArray(row.columns) ? row.columns : [];
            columns.forEach((column, colIndex) => {
              const width = Number(column && column.width ? column.width : 6) || 6;
              list.appendChild(
                structureNode(
                  `Column ${colIndex + 1} (${width}/12)`,
                  2,
                  false,
                  () => {
                    state.selectedIndex = index;
                    renderPanels();
                  }
                )
              );
            });
          });
        });
        structureWrap.appendChild(list);
      }

      const library = document.createElement("section");
      library.className = "be-library";

      const libraryHead = document.createElement("button");
      libraryHead.type = "button";
      libraryHead.className = "be-library-head";
      const libCollapsed = !!state.groupCollapsed.__library;
      libraryHead.innerHTML = `<span>Elements</span><i>${libCollapsed ? "+" : "−"}</i>`;
      libraryHead.addEventListener("click", () => {
        state.groupCollapsed.__library = !state.groupCollapsed.__library;
        renderLeft();
      });
      library.appendChild(libraryHead);

      if (!libCollapsed) {
        const search = textInput(state.search || "");
        search.classList.add("be-search");
        search.placeholder = "Search elements...";
        search.addEventListener("input", () => {
          state.search = search.value.toLowerCase();
          renderLeft();
        });
        library.appendChild(search);

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
          const collapsedByUser = !!state.groupCollapsed[group];
          const isCollapsed = !state.search && collapsedByUser;
          if (isCollapsed) groupBlock.classList.add("is-collapsed");

          const title = document.createElement("button");
          title.type = "button";
          title.className = "be-library-toggle";
          title.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
          title.innerHTML = `<span>${group}</span><i>${isCollapsed ? "+" : "−"} ${filtered.length}</i>`;
          title.addEventListener("click", () => {
            state.groupCollapsed[group] = !state.groupCollapsed[group];
            renderLeft();
          });

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

        library.appendChild(list);
      }

      left.appendChild(head);
      left.appendChild(quick);
      left.appendChild(structureWrap);
      left.appendChild(library);
    }

    function renderCanvas() {
      center.innerHTML = "";

      const top = document.createElement("header");
      top.className = "be-canvas-head";

      const meta = document.createElement("div");
      meta.className = "be-doc-meta";
      const metaTitle = document.createElement("strong");
      metaTitle.textContent = "Document";
      const metaHint = document.createElement("small");
      metaHint.textContent = "Type / to choose a block · drag cards to reorder";
      meta.appendChild(metaTitle);
      meta.appendChild(metaHint);

      const actions = document.createElement("div");
      actions.className = "be-canvas-head-actions";

      const count = document.createElement("span");
      count.className = "be-doc-count";
      count.textContent = `${state.blocks.length} blocks`;

      autosaveBadge = document.createElement("span");
      autosaveBadge.className = "be-autosave-state";
      autosaveBadge.textContent = "Saved";

      undoBtn = document.createElement("button");
      undoBtn.type = "button";
      undoBtn.className = "button";
      undoBtn.textContent = "Undo";
      undoBtn.title = "Ctrl/Cmd + Z";
      undoBtn.addEventListener("click", undoHistory);

      redoBtn = document.createElement("button");
      redoBtn.type = "button";
      redoBtn.className = "button";
      redoBtn.textContent = "Redo";
      redoBtn.title = "Ctrl/Cmd + Shift + Z / Ctrl + Y";
      redoBtn.addEventListener("click", redoHistory);

      const compactToggle = document.createElement("button");
      compactToggle.type = "button";
      compactToggle.className = "button";
      compactToggle.textContent = state.compactMode ? "Expanded view" : "Compact view";
      compactToggle.title = "Switch preview density for long pages";
      compactToggle.addEventListener("click", () => {
        setCompactMode(!state.compactMode);
        renderCanvas();
      });

      const collapseToggle = document.createElement("button");
      collapseToggle.type = "button";
      collapseToggle.className = "button";
      collapseToggle.textContent = allBlocksCollapsed() ? "Expand all" : "Collapse all";
      collapseToggle.title = "Collapse/expand all blocks";
      collapseToggle.addEventListener("click", () => {
        const collapse = !allBlocksCollapsed();
        setAllBlocksCollapsed(collapse);
        renderCanvas();
      });

      const quickAdd = document.createElement("div");
      quickAdd.className = "be-head-quick-add";
      [
        { type: "bs_paragraph", label: "+ Paragraph" },
        { type: "bs_heading", label: "+ Heading" },
        { type: "bs_rows", label: "+ Rows" },
      ].forEach((item) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "button";
        btn.textContent = item.label;
        btn.addEventListener("click", () => addBlock(item.type));
        quickAdd.appendChild(btn);
      });

      actions.appendChild(count);
      actions.appendChild(autosaveBadge);
      actions.appendChild(undoBtn);
      actions.appendChild(redoBtn);
      actions.appendChild(compactToggle);
      actions.appendChild(collapseToggle);
      actions.appendChild(quickAdd);
      top.appendChild(meta);
      top.appendChild(actions);
      updateHistoryButtons();

      const stage = document.createElement("div");
      stage.className = "be-canvas-stage";
      if (state.compactMode) stage.classList.add("is-compact");

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
          pushHistorySnapshot();
          scheduleAutosave();
        };

        state.blocks.forEach((block, index) => {
          const meta = blockMeta(toBootstrapType(block.type || "bs_paragraph"));
          const uid = blockUid(block);
          const isCollapsed = !!state.collapsedBlocks[uid];
          const card = document.createElement("article");
          card.className = "be-canvas-block";
          if (state.compactMode) card.classList.add("is-compact");
          if (isCollapsed) card.classList.add("is-collapsed");
          if (state.selectedIndex === index) card.classList.add("is-selected");
          card.draggable = true;
          card.innerHTML =
            "<div class='be-canvas-block-top'>" +
            `<span class='be-canvas-type'><span class='be-drag-handle' title='Drag to reorder'>⋮⋮</span>${meta.icon} ${meta.label}</span>` +
            "<div class='be-canvas-top-right'></div>" +
            "</div>" +
            "<div class='be-canvas-preview'></div>";
          const topRight = card.querySelector(".be-canvas-top-right");

          const indexBadge = document.createElement("span");
          indexBadge.className = "be-canvas-index";
          indexBadge.textContent = `#${index + 1}`;

          const collapseBtn = document.createElement("button");
          collapseBtn.type = "button";
          collapseBtn.className = "button be-mini-btn";
          collapseBtn.textContent = isCollapsed ? "Expand" : "Collapse";
          collapseBtn.title = "Collapse block settings";
          collapseBtn.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            state.collapsedBlocks[uid] = !state.collapsedBlocks[uid];
            renderCanvas();
            sync();
          });

          const insertAfterBtn = document.createElement("button");
          insertAfterBtn.type = "button";
          insertAfterBtn.className = "button be-mini-btn";
          insertAfterBtn.textContent = "+P";
          insertAfterBtn.title = "Insert paragraph below";
          insertAfterBtn.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            insertBlockAt(index + 1, "bs_paragraph");
          });

          const duplicateBtn = document.createElement("button");
          duplicateBtn.type = "button";
          duplicateBtn.className = "button be-mini-btn";
          duplicateBtn.textContent = "Dup";
          duplicateBtn.title = "Duplicate block";
          duplicateBtn.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            state.selectedIndex = index;
            duplicateSelected();
          });

          const deleteBtn = document.createElement("button");
          deleteBtn.type = "button";
          deleteBtn.className = "button be-mini-btn deletelink";
          deleteBtn.textContent = "Del";
          deleteBtn.title = "Delete block";
          deleteBtn.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            state.selectedIndex = index;
            removeSelected();
          });

          topRight.appendChild(indexBadge);
          topRight.appendChild(collapseBtn);
          topRight.appendChild(insertAfterBtn);
          topRight.appendChild(duplicateBtn);
          topRight.appendChild(deleteBtn);

          card.querySelector(".be-canvas-preview").textContent = blockPreview(block);

          const syncQuickEdit = () => {
            sync();
            scheduleAutosave();
          };

          const commitQuickEdit = () => {
            queueHistorySnapshot();
          };

          card.addEventListener("click", (event) => {
            if (
              event.target &&
              event.target.closest &&
              event.target.closest(".be-inline-editor, .be-card-quick-edit")
            ) {
              return;
            }
            state.collapsedBlocks[uid] = false;
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
          if (state.selectedIndex === index && !isCollapsed) {
            const quickEdit = document.createElement("div");
            const hasQuickEdit = renderCanvasQuickEdit(block, quickEdit, syncQuickEdit, commitQuickEdit);
            if (hasQuickEdit) {
              card.appendChild(quickEdit);
            }
            if (!hasQuickEdit || !supportsQuickEdit(block.type)) {
              const inline = document.createElement("div");
              inline.className = "be-inline-editor";
              card.appendChild(inline);
              renderInspector(inline);
            }
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

      target.appendChild(editorBanner(meta, blockEditorDescription(selected.type)));

      const actions = document.createElement("div");
      actions.className = "be-inspector-actions is-inline";
      actions.innerHTML = "<span>Block actions</span>";
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
        renderCanvasPreserveInlineFocus();
        sync();
        queueHistorySnapshot();
        scheduleAutosave();
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

      function renderColumnEditor(columnBlock, key, labelText, options) {
        if (!Array.isArray(columnBlock[key])) columnBlock[key] = normalizeColumnItems(columnBlock[key]);
        const list = columnBlock[key];
        const keyPrefix = options && options.keyPrefix ? options.keyPrefix : blockUid(columnBlock);
        const selectedKey = `${keyPrefix}:selected`;
        let selectedIndexRaw = Number(state.nestedSelected[selectedKey]);
        if (!Number.isFinite(selectedIndexRaw)) selectedIndexRaw = 0;
        if (selectedIndexRaw < 0) selectedIndexRaw = 0;
        if (selectedIndexRaw > list.length - 1) selectedIndexRaw = Math.max(0, list.length - 1);
        state.nestedSelected[selectedKey] = selectedIndexRaw;

        const section = document.createElement("section");
        section.className = "be-columns-editor be-columns-editor--builder";

        const head = document.createElement("div");
        head.className = "be-columns-editor-head";

        const leftMeta = document.createElement("div");
        leftMeta.className = "be-columns-head-meta";
        const title = document.createElement("strong");
        title.textContent = labelText;
        const count = document.createElement("small");
        count.textContent = `${list.length} block${list.length === 1 ? "" : "s"}`;
        leftMeta.appendChild(title);
        leftMeta.appendChild(count);

        const addWrap = document.createElement("div");
        addWrap.className = "be-columns-add";
        const addType = selectInput(
          COLUMN_CHILD_TYPES.map((childType) => {
            const meta = blockMeta(childType);
            return { value: childType, label: meta.label };
          }),
          "bs_paragraph"
        );
        addType.classList.add("be-mini-select");
        const addBtn = document.createElement("button");
        addBtn.type = "button";
        addBtn.className = "button";
        addBtn.textContent = "Add";
        addBtn.addEventListener("click", () => {
          list.push(defaultsFor(addType.value));
          state.nestedSelected[selectedKey] = list.length - 1;
          changed();
        });
        addWrap.appendChild(addType);
        addWrap.appendChild(addBtn);

        head.appendChild(leftMeta);
        head.appendChild(addWrap);
        section.appendChild(head);

        if (!list.length) {
          const empty = document.createElement("p");
          empty.className = "be-columns-empty";
          empty.textContent = "No blocks in this column yet.";
          section.appendChild(empty);
          return section;
        }

        let dragChildIndex = -1;
        const listPane = document.createElement("div");
        listPane.className = "be-nested-list";

        const clearDropMarkers = () => {
          listPane.querySelectorAll(".be-nested-row").forEach((el) => {
            el.classList.remove("is-drop-before");
            el.classList.remove("is-drop-after");
          });
        };

        const setSelected = (nextIndex) => {
          const safe = Math.max(0, Math.min(nextIndex, list.length - 1));
          state.nestedSelected[selectedKey] = safe;
        };

        const rerenderNestedSelection = () => {
          renderCanvasPreserveInlineFocus();
        };

        const moveChild = (fromIndex, toIndex) => {
          if (fromIndex < 0 || fromIndex >= list.length) return;
          let target = Math.max(0, Math.min(toIndex, list.length));
          if (target === fromIndex || target === fromIndex + 1) return;
          const moved = list.splice(fromIndex, 1)[0];
          if (target > fromIndex) target -= 1;
          list.splice(target, 0, moved);

          const selected = Number(state.nestedSelected[selectedKey] || 0);
          if (selected === fromIndex) {
            state.nestedSelected[selectedKey] = target;
          } else if (fromIndex < selected && selected <= target) {
            state.nestedSelected[selectedKey] = selected - 1;
          } else if (target <= selected && selected < fromIndex) {
            state.nestedSelected[selectedKey] = selected + 1;
          }
          changed();
        };

        list.forEach((item, index) => {
          const block = normalizeLegacyBlock(item);
          list[index] = block;
          const itemType = toBootstrapType(block.type || "bs_paragraph");
          const itemMeta = blockMeta(itemType);
          const active = index === selectedIndexRaw;

          const row = document.createElement("article");
          row.className = "be-nested-row";
          if (active) row.classList.add("is-active");
          row.draggable = true;
          row.addEventListener("click", () => {
            setSelected(index);
            rerenderNestedSelection();
          });
          row.addEventListener("dragstart", (event) => {
            dragChildIndex = index;
            row.classList.add("is-dragging");
            if (event.dataTransfer) {
              event.dataTransfer.effectAllowed = "move";
              event.dataTransfer.setData("application/x-be-column-child-index", String(index));
            }
          });
          row.addEventListener("dragend", () => {
            dragChildIndex = -1;
            row.classList.remove("is-dragging");
            clearDropMarkers();
          });
          row.addEventListener("dragover", (event) => {
            if (dragChildIndex < 0) return;
            event.preventDefault();
            const rect = row.getBoundingClientRect();
            const dropBefore = event.clientY < rect.top + rect.height / 2;
            clearDropMarkers();
            row.classList.add(dropBefore ? "is-drop-before" : "is-drop-after");
          });
          row.addEventListener("drop", (event) => {
            if (dragChildIndex < 0) return;
            event.preventDefault();
            const rect = row.getBoundingClientRect();
            const dropBefore = event.clientY < rect.top + rect.height / 2;
            const targetIndex = dropBefore ? index : index + 1;
            clearDropMarkers();
            moveChild(dragChildIndex, targetIndex);
          });

          const rowInfo = document.createElement("div");
          rowInfo.className = "be-nested-row-info";
          const idx = document.createElement("span");
          idx.className = "be-columns-index";
          idx.textContent = `#${index + 1}`;
          const typeBadge = document.createElement("span");
          typeBadge.className = "be-nested-type";
          typeBadge.textContent = `${itemMeta.icon} ${itemMeta.label}`;
          const summary = document.createElement("span");
          summary.className = "be-nested-row-summary";
          summary.textContent = blockPreview(block) || itemMeta.label;
          rowInfo.appendChild(idx);
          rowInfo.appendChild(typeBadge);
          rowInfo.appendChild(summary);

          const actions = document.createElement("div");
          actions.className = "be-row-actions";

          const actionButton = (label, className, handler, disabled) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = className;
            btn.textContent = label;
            btn.disabled = !!disabled;
            btn.addEventListener("click", (event) => {
              event.preventDefault();
              event.stopPropagation();
              handler();
            });
            return btn;
          };

          actions.appendChild(
            actionButton("↑", "button be-mini-btn", () => {
              if (index < 1) return;
              const tmp = list[index - 1];
              list[index - 1] = list[index];
              list[index] = tmp;
              setSelected(index - 1);
              changed();
            }, index === 0)
          );
          actions.appendChild(
            actionButton("↓", "button be-mini-btn", () => {
              if (index >= list.length - 1) return;
              const tmp = list[index + 1];
              list[index + 1] = list[index];
              list[index] = tmp;
              setSelected(index + 1);
              changed();
            }, index === list.length - 1)
          );
          actions.appendChild(
            actionButton("Dup", "button be-mini-btn", () => {
              list.splice(index + 1, 0, JSON.parse(JSON.stringify(block)));
              setSelected(index + 1);
              changed();
            })
          );
          actions.appendChild(
            actionButton("Delete", "button deletelink be-mini-btn", () => {
              list.splice(index, 1);
              setSelected(Math.max(0, index - 1));
              changed();
            })
          );

          const rowMain = document.createElement("div");
          rowMain.className = "be-nested-row-main";
          rowMain.appendChild(rowInfo);
          rowMain.appendChild(actions);
          row.appendChild(rowMain);

          if (active) {
            const inlineBody = document.createElement("div");
            inlineBody.className = "be-nested-row-body";
            inlineBody.addEventListener("click", (event) => {
              event.stopPropagation();
            });

            const inlineHead = document.createElement("div");
            inlineHead.className = "be-nested-inline-head";

            const inlineMeta = document.createElement("div");
            inlineMeta.className = "be-nested-inline-meta";
            const inlineTitle = document.createElement("strong");
            inlineTitle.textContent = itemMeta.label;
            const inlineHint = document.createElement("small");
            inlineHint.textContent = "Edit this block directly in the document.";
            inlineMeta.appendChild(inlineTitle);
            inlineMeta.appendChild(inlineHint);

            const typeSelect = selectInput(
              COLUMN_CHILD_TYPES.map((childType) => {
                const meta = blockMeta(childType);
                return { value: childType, label: meta.label };
              }),
              itemType
            );
            typeSelect.classList.add("be-mini-select");
            typeSelect.addEventListener("change", () => {
              list[index] = defaultsFor(typeSelect.value);
              setSelected(index);
              changed();
            });

            inlineHead.appendChild(inlineMeta);
            inlineHead.appendChild(typeSelect);
            inlineBody.appendChild(inlineHead);

            const fields = document.createElement("div");
            fields.className = "be-columns-item-body be-columns-item-body--inline";
            renderColumnChildFields(block, fields);
            inlineBody.appendChild(fields);

            row.appendChild(inlineBody);
          }

          listPane.appendChild(row);
        });

        section.appendChild(listPane);
        return section;
      }

      function defaultRowColumn() {
        return { width: 6, blocks: [{ type: "bs_paragraph", text: "Column text" }] };
      }

      function rowFromPreset(presetValue, existingColumns) {
        const preset = ROW_PRESETS.find((item) => item.value === presetValue) || ROW_PRESETS[1];
        const previous = Array.isArray(existingColumns) ? existingColumns : [];
        return {
          gutter: 3,
          align: "start",
          columns: preset.widths.map((width, index) => {
            const prevColumn = previous[index];
            const prevBlocks = prevColumn && Array.isArray(prevColumn.blocks) ? normalizeColumnItems(prevColumn.blocks) : [];
            return {
              width,
              blocks: prevBlocks.length ? prevBlocks : [{ type: "bs_paragraph", text: "Column text" }],
            };
          }),
        };
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
        section.className = "be-rows-editor be-rows-workbench";

        const head = document.createElement("div");
        head.className = "be-canvas-block-top";
        const titleWrap = document.createElement("div");
        titleWrap.className = "be-canvas-block-top-left";
        const title = document.createElement("strong");
        title.textContent = "Bootstrap container";
        const hint = document.createElement("small");
        hint.textContent = "Container -> row -> column";
        titleWrap.appendChild(title);
        titleWrap.appendChild(hint);

        const headActions = document.createElement("div");
        headActions.className = "be-canvas-top-right";
        const presetSelect = selectInput(rowPresetOptions(false), "6-6");
        presetSelect.classList.add("be-mini-select");
        const headPreset = presetSelect;
        const addRowBtn = document.createElement("button");
        addRowBtn.type = "button";
        addRowBtn.className = "button";
        addRowBtn.textContent = "+ Row";
        addRowBtn.addEventListener("click", () => {
          rowsBlock.rows.push(rowFromPreset(presetSelect.value, []));
          changed();
        });
        headActions.appendChild(presetSelect);
        headActions.appendChild(addRowBtn);
        head.appendChild(titleWrap);
        head.appendChild(headActions);
        section.appendChild(head);

        const parentUid = blockUid(rowsBlock);
        const split = document.createElement("div");
        split.className = "be-rows-split";
        const structurePane = document.createElement("aside");
        structurePane.className = "be-rows-structure";
        const structureHead = document.createElement("div");
        structureHead.className = "be-rows-structure-head";
        const structureTitle = document.createElement("strong");
        structureTitle.textContent = "Structure";
        const structureHint = document.createElement("small");
        structureHint.textContent = "Rows and columns";
        structureHead.appendChild(structureTitle);
        structureHead.appendChild(structureHint);
        structurePane.appendChild(structureHead);
        const structureList = document.createElement("div");
        structureList.className = "be-rows-structure-list";
        structurePane.appendChild(structureList);
        split.appendChild(structurePane);

        const canvasPane = document.createElement("div");
        canvasPane.className = "be-rows-canvas";
        const canvasHead = document.createElement("div");
        canvasHead.className = "be-rows-canvas-head";
        const canvasTitle = document.createElement("strong");
        canvasTitle.textContent = "Canvas";
        const canvasHint = document.createElement("small");
        canvasHint.textContent = "Drag rows/columns and edit in place";
        canvasHead.appendChild(canvasTitle);
        canvasHead.appendChild(canvasHint);
        canvasPane.appendChild(canvasHead);
        split.appendChild(canvasPane);
        section.appendChild(split);

        let dragRowIndex = -1;
        let dragColumn = null;

        const createDragGhost = (event, label) => {
          if (!event.dataTransfer) return;
          const ghost = document.createElement("div");
          ghost.className = "be-drag-ghost";
          ghost.textContent = label;
          document.body.appendChild(ghost);
          event.dataTransfer.setDragImage(ghost, 10, 10);
          setTimeout(() => ghost.remove(), 0);
        };

        const clearRowDropzones = () => {
          canvasPane.querySelectorAll(".be-row-dropzone").forEach((el) => {
            el.classList.remove("is-active");
          });
        };
        const clearColumnDropzones = () => {
          canvasPane.querySelectorAll(".be-col-dropzone").forEach((el) => {
            el.classList.remove("is-active");
          });
        };

        const moveRow = (fromIndex, targetIndexRaw) => {
          if (fromIndex < 0 || fromIndex >= rowsBlock.rows.length) return;
          let target = Math.max(0, Math.min(targetIndexRaw, rowsBlock.rows.length));
          if (target === fromIndex || target === fromIndex + 1) return;
          const moved = rowsBlock.rows.splice(fromIndex, 1)[0];
          if (target > fromIndex) target -= 1;
          rowsBlock.rows.splice(target, 0, moved);
          changed();
        };

        const moveColumn = (rowIndex, fromIndex, targetIndexRaw) => {
          const row = rowsBlock.rows[rowIndex];
          if (!row || !Array.isArray(row.columns)) return;
          const columns = row.columns;
          if (fromIndex < 0 || fromIndex >= columns.length) return;
          let target = Math.max(0, Math.min(targetIndexRaw, columns.length));
          if (target === fromIndex || target === fromIndex + 1) return;
          const moved = columns.splice(fromIndex, 1)[0];
          if (target > fromIndex) target -= 1;
          columns.splice(target, 0, moved);
          changed();
        };

        const createRowDropzone = (targetIndex) => {
          const zone = document.createElement("button");
          zone.type = "button";
          zone.className = "be-row-dropzone";
          zone.textContent = "+ Add row here or drop";
          zone.addEventListener("click", () => {
            rowsBlock.rows.splice(targetIndex, 0, rowFromPreset(headPreset.value, []));
            changed();
          });
          zone.addEventListener("dragover", (event) => {
            if (dragRowIndex < 0) return;
            event.preventDefault();
            clearRowDropzones();
            zone.classList.add("is-active");
          });
          zone.addEventListener("drop", (event) => {
            if (dragRowIndex < 0) return;
            event.preventDefault();
            clearRowDropzones();
            moveRow(dragRowIndex, targetIndex);
          });
          return zone;
        };

        const createColumnDropzone = (rowIndex, targetIndex) => {
          const zone = document.createElement("button");
          zone.type = "button";
          zone.className = "be-col-dropzone";
          zone.textContent = "+";
          zone.title = "Drop column here";
          zone.addEventListener("dragover", (event) => {
            if (!dragColumn || dragColumn.rowIndex !== rowIndex) return;
            event.preventDefault();
            clearColumnDropzones();
            zone.classList.add("is-active");
          });
          zone.addEventListener("drop", (event) => {
            if (!dragColumn || dragColumn.rowIndex !== rowIndex) return;
            event.preventDefault();
            clearColumnDropzones();
            moveColumn(rowIndex, dragColumn.colIndex, targetIndex);
          });
          return zone;
        };

        canvasPane.appendChild(createRowDropzone(0));

        rowsBlock.rows.forEach((row, rowIndex) => {
          const normalizedRow = normalizeRowItem(row);
          rowsBlock.rows[rowIndex] = normalizedRow;
          const rowKey = `${parentUid}:r:${rowIndex}`;
          const rowCollapsed = typeof state.rowCollapsed[rowKey] === "boolean" ? state.rowCollapsed[rowKey] : rowIndex !== 0;

          const structureItem = document.createElement("button");
          structureItem.type = "button";
          structureItem.className = "be-rows-structure-item";
          if (!rowCollapsed) structureItem.classList.add("is-active");
          const structureLabel = document.createElement("span");
          structureLabel.textContent = `Row ${rowIndex + 1}`;
          const structureMeta = document.createElement("small");
          structureMeta.textContent = `${normalizedRow.columns.length} cols`;
          structureItem.appendChild(structureLabel);
          structureItem.appendChild(structureMeta);
          structureItem.addEventListener("click", () => {
            state.rowCollapsed[rowKey] = false;
            changed();
          });
          structureList.appendChild(structureItem);

          const structureColumns = document.createElement("div");
          structureColumns.className = "be-rows-structure-sublist";
          normalizedRow.columns.forEach((column, colIndex) => {
            const colKey = `${rowKey}:c:${colIndex}`;
            const isColOpen =
              !rowCollapsed &&
              (typeof state.colCollapsed[colKey] === "boolean" ? !state.colCollapsed[colKey] : colIndex === 0);
            const sub = document.createElement("button");
            sub.type = "button";
            sub.className = "be-rows-structure-subitem";
            if (isColOpen) sub.classList.add("is-active");
            sub.textContent = `Column ${colIndex + 1} · ${Number(column.width || 6) || 6}/12`;
            sub.addEventListener("click", () => {
              state.rowCollapsed[rowKey] = false;
              state.colCollapsed[colKey] = false;
              changed();
            });
            structureColumns.appendChild(sub);
          });
          structureList.appendChild(structureColumns);

          const rowCard = document.createElement("article");
          rowCard.className = "be-row-item";
          if (rowCollapsed) rowCard.classList.add("is-collapsed");
          rowCard.draggable = false;

          const rowTop = document.createElement("div");
          rowTop.className = "be-row-item-top be-sticky-toolbar be-row-toolbar";
          const rowMeta = document.createElement("div");
          rowMeta.className = "be-row-meta";
          const rowLabel = document.createElement("strong");
          rowLabel.textContent = `Row ${rowIndex + 1}`;
          const rowChips = document.createElement("div");
          rowChips.className = "be-row-chips";
          const chipCols = document.createElement("span");
          chipCols.className = "be-chip";
          chipCols.textContent = `${normalizedRow.columns.length} cols`;
          const chipGap = document.createElement("span");
          chipGap.className = "be-chip";
          chipGap.textContent = `gap-${normalizedRow.gutter}`;
          const chipAlign = document.createElement("span");
          chipAlign.className = "be-chip";
          chipAlign.textContent = normalizedRow.align;
          rowChips.appendChild(chipCols);
          rowChips.appendChild(chipGap);
          rowChips.appendChild(chipAlign);
          rowMeta.appendChild(rowLabel);
          rowMeta.appendChild(rowChips);

          const rowButtons = document.createElement("div");
          rowButtons.className = "be-row-actions";

          const rowDrag = document.createElement("button");
          rowDrag.type = "button";
          rowDrag.className = "button be-mini-btn be-drag-pill";
          rowDrag.textContent = "⋮⋮";
          rowDrag.title = "Drag row";
          rowDrag.draggable = true;
          rowDrag.addEventListener("dragstart", (event) => {
            dragRowIndex = rowIndex;
            rowCard.classList.add("is-dragging");
            createDragGhost(event, `Row ${rowIndex + 1}`);
            if (event.dataTransfer) {
              event.dataTransfer.effectAllowed = "move";
              event.dataTransfer.setData("application/x-be-row-index", String(rowIndex));
            }
          });
          rowDrag.addEventListener("dragend", () => {
            dragRowIndex = -1;
            rowCard.classList.remove("is-dragging");
            clearRowDropzones();
          });

          const rowToggle = document.createElement("button");
          rowToggle.type = "button";
          rowToggle.className = "button be-mini-btn";
          rowToggle.textContent = rowCollapsed ? "Show" : "Hide";
          rowToggle.addEventListener("click", () => {
            state.rowCollapsed[rowKey] = !rowCollapsed;
            changed();
          });

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

          rowButtons.appendChild(rowDrag);
          rowButtons.appendChild(rowToggle);
          rowButtons.appendChild(addColumnBtn);
          rowButtons.appendChild(rowUp);
          rowButtons.appendChild(rowDown);
          rowButtons.appendChild(rowRemove);
          rowTop.appendChild(rowMeta);
          rowTop.appendChild(rowButtons);
          rowCard.appendChild(rowTop);

          if (rowCollapsed) {
            const mini = document.createElement("div");
            mini.className = "be-row-mini-map";
            const totalWidth = normalizedRow.columns.reduce((sum, col) => sum + (Number(col.width || 6) || 6), 0) || 12;
            normalizedRow.columns.forEach((column, colIndex) => {
              const cell = document.createElement("span");
              cell.className = "be-row-mini-cell";
              const colWidth = Number(column.width || 6) || 6;
              const pct = Math.max(8, Math.round((colWidth / totalWidth) * 100));
              cell.style.flexBasis = `${pct}%`;
              const nestedCount = Array.isArray(column.blocks) ? column.blocks.length : 0;
              cell.textContent = `${colIndex + 1}:${colWidth}/12 · ${nestedCount}`;
              mini.appendChild(cell);
            });
            rowCard.appendChild(mini);

            const rowSummary = document.createElement("p");
            rowSummary.className = "be-collapse-summary";
            rowSummary.textContent = "Click Show to edit columns and nested blocks.";
            rowCard.appendChild(rowSummary);
            canvasPane.appendChild(rowCard);
            canvasPane.appendChild(createRowDropzone(rowIndex + 1));
            return;
          }

          const rowSettings = document.createElement("div");
          rowSettings.className = "be-row-settings be-row-settings-inline";

          const inlineControl = (labelText, inputEl, helperText) => {
            const wrap = document.createElement("label");
            wrap.className = "be-inline-control";
            const titleEl = document.createElement("span");
            titleEl.className = "be-inline-label";
            titleEl.textContent = labelText;
            wrap.appendChild(titleEl);
            wrap.appendChild(inputEl);
            if (helperText) {
              const hintEl = document.createElement("small");
              hintEl.className = "be-inline-help";
              hintEl.textContent = helperText;
              wrap.appendChild(hintEl);
            }
            return wrap;
          };

          const rowPresetSelect = selectInput(rowPresetOptions(true), rowPresetFromColumns(normalizedRow.columns));
          rowPresetSelect.classList.add("be-row-preset-select");
          rowPresetSelect.addEventListener("change", () => {
            if (rowPresetSelect.value === "custom") return;
            rowsBlock.rows[rowIndex] = rowFromPreset(rowPresetSelect.value, normalizedRow.columns);
            changed();
          });

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

          rowSettings.appendChild(
            inlineControl("Layout preset", rowPresetSelect, "Replaces current row columns")
          );
          rowSettings.appendChild(inlineControl("Row gap", gutterSelect));
          rowSettings.appendChild(inlineControl("Vertical align", alignSelect));
          rowCard.appendChild(rowSettings);

          const columnsGrid = document.createElement("div");
          columnsGrid.className = "be-row-columns";
          columnsGrid.appendChild(createColumnDropzone(rowIndex, 0));

          normalizedRow.columns.forEach((column, colIndex) => {
            const colKey = `${rowKey}:c:${colIndex}`;
            const colCollapsed = typeof state.colCollapsed[colKey] === "boolean" ? state.colCollapsed[colKey] : colIndex !== 0;
            const colCard = document.createElement("div");
            colCard.className = "be-row-column";
            if (colCollapsed) colCard.classList.add("is-collapsed");
            colCard.draggable = false;

            const colTop = document.createElement("div");
            colTop.className = "be-row-column-top be-sticky-toolbar be-col-toolbar";
            const colMeta = document.createElement("div");
            colMeta.className = "be-col-meta";
            const colLabel = document.createElement("span");
            colLabel.textContent = `Column ${colIndex + 1}`;
            const widthBadge = document.createElement("small");
            widthBadge.className = "be-chip";
            widthBadge.textContent = `${Number(column.width || 6) || 6}/12`;
            colMeta.appendChild(colLabel);
            colMeta.appendChild(widthBadge);

            const colActions = document.createElement("div");
            colActions.className = "be-row-actions";

            const colDrag = document.createElement("button");
            colDrag.type = "button";
            colDrag.className = "button be-mini-btn be-drag-pill";
            colDrag.textContent = "⋮⋮";
            colDrag.title = "Drag column";
            colDrag.draggable = true;
            colDrag.addEventListener("dragstart", (event) => {
              dragColumn = { rowIndex, colIndex };
              colCard.classList.add("is-dragging");
              createDragGhost(event, `Column ${colIndex + 1}`);
              if (event.dataTransfer) {
                event.dataTransfer.effectAllowed = "move";
                event.dataTransfer.setData("application/x-be-col-index", String(colIndex));
              }
            });
            colDrag.addEventListener("dragend", () => {
              dragColumn = null;
              colCard.classList.remove("is-dragging");
              clearColumnDropzones();
            });

            const colToggle = document.createElement("button");
            colToggle.type = "button";
            colToggle.className = "button be-mini-btn";
            colToggle.textContent = colCollapsed ? "Show" : "Hide";
            colToggle.addEventListener("click", () => {
              state.colCollapsed[colKey] = !colCollapsed;
              changed();
            });

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

            colActions.appendChild(colDrag);
            colActions.appendChild(colToggle);
            colActions.appendChild(colLeft);
            colActions.appendChild(colRight);
            colActions.appendChild(colRemove);
            colTop.appendChild(colMeta);
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
            widthSelect.classList.add("be-mini-select");
            widthSelect.addEventListener("change", () => {
              column.width = Number(widthSelect.value || 6);
              changed();
            });
            colActions.appendChild(widthSelect);

            if (colCollapsed) {
              const colSummary = document.createElement("p");
              colSummary.className = "be-collapse-summary";
              const nested = Array.isArray(column.blocks) ? column.blocks.length : 0;
              const labels = (Array.isArray(column.blocks) ? column.blocks : [])
                .slice(0, 3)
                .map((child) => blockMeta(toBootstrapType(child.type || "bs_paragraph")).label)
                .join(", ");
              colSummary.textContent = nested
                ? `${nested} nested block${nested === 1 ? "" : "s"} · ${labels}${nested > 3 ? "..." : ""}`
                : "No nested blocks yet.";
              colCard.appendChild(colSummary);
            } else {
              colCard.appendChild(
                renderColumnEditor(column, "blocks", "Nested blocks", {
                  keyPrefix: `${rowKey}:c:${colIndex}`,
                })
              );
            }
            columnsGrid.appendChild(colCard);
            columnsGrid.appendChild(createColumnDropzone(rowIndex, colIndex + 1));
          });

          rowCard.appendChild(columnsGrid);
          canvasPane.appendChild(rowCard);
          canvasPane.appendChild(createRowDropzone(rowIndex + 1));
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

    root.addEventListener("keydown", (event) => {
      if (state.selectedIndex < 0) return;
      const key = String(event.key || "");
      const lower = key.toLowerCase();
      const typing = isTypingContext(event.target);

      if ((event.ctrlKey || event.metaKey) && lower === "z" && !event.shiftKey) {
        if (typing) return;
        event.preventDefault();
        undoHistory();
        return;
      }

      if (
        (event.ctrlKey || event.metaKey) &&
        ((lower === "z" && event.shiftKey) || lower === "y")
      ) {
        if (typing) return;
        event.preventDefault();
        redoHistory();
        return;
      }

      if ((event.ctrlKey || event.metaKey) && lower === "d") {
        if (typing) return;
        event.preventDefault();
        duplicateSelected();
        return;
      }

      if (event.altKey && key === "ArrowUp") {
        event.preventDefault();
        moveSelected(-1);
        return;
      }

      if (event.altKey && key === "ArrowDown") {
        event.preventDefault();
        moveSelected(1);
        return;
      }

      if ((key === "Delete" || key === "Backspace") && !typing) {
        event.preventDefault();
        removeSelected();
      }
    });

    restoreAutosaveIfAvailable();
    pushHistorySnapshot();
    renderAll();
    setAutosaveState("saved", "Saved");

    const form = source.closest("form");
    if (form) {
      form.addEventListener("submit", () => {
        if (autosaveTimer) window.clearTimeout(autosaveTimer);
        if (historyDebounceTimer) window.clearTimeout(historyDebounceTimer);
        sync();
        clearAutosaveSnapshot();
      });
    }
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

