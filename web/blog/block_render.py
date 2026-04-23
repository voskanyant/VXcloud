from __future__ import annotations

import json
from html import escape
from typing import Any
from uuid import uuid4

from django.utils.safestring import mark_safe


def _safe_text(value: Any) -> str:
    return escape(str(value or ""))


def _safe_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url:
        return "#"
    return escape(url, quote=True)


def _render_buttons(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    parts: list[str] = ['<div class="site-button-row" aria-label="Button group">']
    for item in items:
        label = _safe_text(item.get("label"))
        href = _safe_url(item.get("url"))
        style = str(item.get("style") or "primary").strip().lower()
        css = "site-button site-button-primary" if style != "secondary" else "site-button site-button-secondary"
        parts.append(f'<a class="{css}" href="{href}">{label}</a>')
    parts.append("</div>")
    return "".join(parts)


def _safe_variant(value: Any, *, default: str = "primary") -> str:
    allowed = {"primary", "secondary", "success", "danger", "warning", "info", "light", "dark", "link"}
    variant = str(value or "").strip().lower()
    return variant if variant in allowed else default


def _render_bs_alert(block: dict[str, Any]) -> str:
    title = _safe_text(block.get("title"))
    text = _safe_text(block.get("text"))
    if not title and not text:
        return ""
    parts = ['<aside class="block-notice" role="alert">']
    if title:
        parts.append(f"<strong>{title}</strong>")
    if text:
        parts.append(f"<p>{text}</p>")
    parts.append("</aside>")
    return "".join(parts)


def _render_bs_badge(block: dict[str, Any]) -> str:
    text = _safe_text(block.get("text"))
    if not text:
        return ""
    return f'<span class="site-chip">{text}</span>'


def _render_bs_card(block: dict[str, Any]) -> str:
    title = _safe_text(block.get("title"))
    text = _safe_text(block.get("text"))
    image = _safe_url(block.get("image"))
    button_label = _safe_text(block.get("button_label"))
    button_url = _safe_url(block.get("button_url"))
    button_variant = _safe_variant(block.get("button_style"), default="primary")
    if not title and not text and (not image or image == "#"):
        return ""
    parts = ['<article class="surface-card block-card block-card-static">']
    if image and image != "#":
        parts.append(f'<img src="{image}" class="block-card-image" alt="{title or "Card image"}" loading="lazy" />')
    parts.append('<div class="block-card-body">')
    if title:
        parts.append(f'<h3 class="feature-card-title">{title}</h3>')
    if text:
        parts.append(f'<p class="feature-card-copy">{text}</p>')
    if button_label and button_url and button_url != "#":
        button_cls = "site-button site-button-primary" if button_variant != "secondary" else "site-button site-button-secondary"
        parts.append(f'<a href="{button_url}" class="{button_cls}">{button_label}</a>')
    parts.append("</div></article>")
    return "".join(parts)


def _render_bs_accordion(block: dict[str, Any]) -> str:
    items = block.get("items")
    if not isinstance(items, list) or not items:
        return ""
    parts = ['<div class="block-accordion">']
    for idx, row in enumerate(items):
        if not isinstance(row, dict):
            continue
        title = _safe_text(row.get("title"))
        text = _safe_text(row.get("text"))
        if not title and not text:
            continue
        open_attr = " open" if idx == 0 else ""
        parts.append(f'<details class="block-accordion-item"{open_attr}>')
        parts.append(f'<summary>{title or f"Item {idx + 1}"}</summary>')
        if text:
            parts.append(f"<p>{text}</p>")
        parts.append("</details>")
    parts.append("</div>")
    return "".join(parts)


def _render_bs_tabs(block: dict[str, Any]) -> str:
    items = block.get("items")
    if not isinstance(items, list) or not items:
        return ""
    parts = ['<div class="block-tab-panels">']
    for idx, row in enumerate(items):
        if not isinstance(row, dict):
            continue
        title = _safe_text(row.get("title"))
        text = _safe_text(row.get("text"))
        if not title and not text:
            continue
        parts.append('<section class="block-tab-panel">')
        parts.append(f'<h3>{title or f"Section {idx + 1}"}</h3>')
        if text:
            parts.append(f"<p>{text}</p>")
        parts.append("</section>")
    parts.append("</div>")
    return "".join(parts)


def _render_bs_table(block: dict[str, Any]) -> str:
    headers = block.get("headers")
    rows = block.get("rows")
    if not isinstance(headers, list):
        headers = []
    if not isinstance(rows, list):
        rows = []
    if not headers and not rows:
        return ""
    table_classes = ["table", "mb-0"]
    if bool(block.get("striped", True)):
        table_classes.append("table-striped")
    if bool(block.get("hover", True)):
        table_classes.append("table-hover")
    if bool(block.get("bordered")):
        table_classes.append("table-bordered")
    parts = ['<div class="table-responsive"><table class="{}">'.format(" ".join(table_classes))]
    if headers:
        parts.append("<thead><tr>")
        for cell in headers:
            parts.append(f"<th>{_safe_text(cell)}</th>")
        parts.append("</tr></thead>")
    if rows:
        parts.append("<tbody>")
        for row in rows:
            if not isinstance(row, list):
                continue
            parts.append("<tr>")
            for cell in row:
                parts.append(f"<td>{_safe_text(cell)}</td>")
            parts.append("</tr>")
        parts.append("</tbody>")
    parts.append("</table></div>")
    return "".join(parts)


def _render_bs_figure(block: dict[str, Any]) -> str:
    src = _safe_url(block.get("src"))
    if not src or src == "#":
        return ""
    alt = _safe_text(block.get("alt"))
    caption = _safe_text(block.get("caption"))
    align = str(block.get("align") or "start").strip().lower()
    text_cls = " text-center" if align == "center" else " text-end" if align == "end" else ""
    parts = [f'<figure class="figure block-bs-figure{text_cls}">']
    parts.append(f'<img src="{src}" class="figure-img img-fluid rounded" alt="{alt}" loading="lazy" />')
    if caption:
        parts.append(f'<figcaption class="figure-caption">{caption}</figcaption>')
    parts.append("</figure>")
    return "".join(parts)


def _render_bs_form_control(block: dict[str, Any]) -> str:
    label = _safe_text(block.get("label"))
    placeholder = _safe_text(block.get("placeholder"))
    value = _safe_text(block.get("value"))
    help_text = _safe_text(block.get("help_text"))
    input_type = _safe_text(block.get("input_type") or "text")
    control_as = str(block.get("as") or "input").strip().lower()
    rows = int(block.get("rows") or 4)
    size = str(block.get("size") or "").strip().lower()
    state = str(block.get("validation_state") or "").strip().lower()
    message = _safe_text(block.get("validation_message"))
    disabled = " disabled" if bool(block.get("disabled")) else ""
    readonly = " readonly" if bool(block.get("readonly")) else ""
    size_cls = f" form-control-{size}" if size in {"sm", "lg"} else ""
    state_cls = " is-valid" if state == "valid" else " is-invalid" if state == "invalid" else ""
    parts = ['<div class="mb-3 block-bs-form">']
    if label:
        parts.append(f'<label class="form-label">{label}</label>')
    if control_as == "textarea":
        parts.append(
            f'<textarea class="form-control{size_cls}{state_cls}" rows="{max(2, min(rows, 12))}" '
            f'placeholder="{placeholder}"{disabled}{readonly}>{value}</textarea>'
        )
    else:
        parts.append(
            f'<input type="{input_type}" class="form-control{size_cls}{state_cls}" '
            f'placeholder="{placeholder}" value="{value}"{disabled}{readonly} />'
        )
    if help_text:
        parts.append(f'<div class="form-text">{help_text}</div>')
    if message:
        feedback_cls = "valid-feedback d-block" if state == "valid" else "invalid-feedback d-block" if state == "invalid" else "form-text"
        parts.append(f'<div class="{feedback_cls}">{message}</div>')
    parts.append("</div>")
    return "".join(parts)


def _render_bs_form_select(block: dict[str, Any]) -> str:
    label = _safe_text(block.get("label"))
    options = block.get("options")
    if not isinstance(options, list) or not options:
        return ""
    size = str(block.get("size") or "").strip().lower()
    state = str(block.get("validation_state") or "").strip().lower()
    message = _safe_text(block.get("validation_message"))
    disabled = " disabled" if bool(block.get("disabled")) else ""
    multiple = " multiple" if bool(block.get("multiple")) else ""
    size_cls = f" form-select-{size}" if size in {"sm", "lg"} else ""
    state_cls = " is-valid" if state == "valid" else " is-invalid" if state == "invalid" else ""
    parts = ['<div class="mb-3 block-bs-form">']
    if label:
        parts.append(f'<label class="form-label">{label}</label>')
    parts.append(f'<select class="form-select{size_cls}{state_cls}"{disabled}{multiple}>')
    for option in options:
        if not isinstance(option, dict):
            continue
        option_label = _safe_text(option.get("label"))
        option_value = _safe_text(option.get("value"))
        selected = " selected" if bool(option.get("selected")) else ""
        parts.append(f'<option value="{option_value}"{selected}>{option_label}</option>')
    parts.append("</select>")
    if message:
        feedback_cls = "valid-feedback d-block" if state == "valid" else "invalid-feedback d-block" if state == "invalid" else "form-text"
        parts.append(f'<div class="{feedback_cls}">{message}</div>')
    parts.append("</div>")
    return "".join(parts)


def _render_bs_form_checks(block: dict[str, Any]) -> str:
    items = block.get("items")
    if not isinstance(items, list) or not items:
        return ""
    label = _safe_text(block.get("label"))
    style = str(block.get("style") or "checkbox").strip().lower()
    inline = bool(block.get("inline"))
    name = _safe_text(block.get("name") or "choice-group")
    input_type = "radio" if style == "radio" else "checkbox"
    wrapper_cls = "form-check form-switch" if style == "switch" else "form-check"
    if inline and style != "switch":
        wrapper_cls += " form-check-inline"
    parts = ['<div class="mb-3 block-bs-form">']
    if label:
        parts.append(f'<div class="form-label">{label}</div>')
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        item_label = _safe_text(item.get("label"))
        checked = " checked" if bool(item.get("checked")) else ""
        disabled = " disabled" if bool(item.get("disabled")) else ""
        item_id = f"check-{uuid4().hex[:8]}-{idx}"
        parts.append(f'<div class="{wrapper_cls}">')
        parts.append(
            f'<input class="form-check-input" type="{input_type}" name="{name}" id="{item_id}"{checked}{disabled} />'
        )
        parts.append(f'<label class="form-check-label" for="{item_id}">{item_label}</label>')
        parts.append("</div>")
    parts.append("</div>")
    return "".join(parts)


def _render_bs_form_range(block: dict[str, Any]) -> str:
    label = _safe_text(block.get("label"))
    minimum = _safe_text(block.get("min") or 0)
    maximum = _safe_text(block.get("max") or 100)
    step = _safe_text(block.get("step") or 1)
    value = _safe_text(block.get("value") or 0)
    disabled = " disabled" if bool(block.get("disabled")) else ""
    return (
        '<div class="mb-3 block-bs-form">'
        f'<label class="form-label">{label}</label>'
        f'<input type="range" class="form-range" min="{minimum}" max="{maximum}" step="{step}" value="{value}"{disabled} />'
        "</div>"
    )


def _render_bs_input_group(block: dict[str, Any]) -> str:
    label = _safe_text(block.get("label"))
    prefix = _safe_text(block.get("prefix"))
    suffix = _safe_text(block.get("suffix"))
    button_text = _safe_text(block.get("button_text"))
    placeholder = _safe_text(block.get("placeholder"))
    value = _safe_text(block.get("value"))
    input_type = _safe_text(block.get("input_type") or "text")
    parts = ['<div class="mb-3 block-bs-form">']
    if label:
        parts.append(f'<label class="form-label">{label}</label>')
    parts.append('<div class="input-group">')
    if prefix:
        parts.append(f'<span class="input-group-text">{prefix}</span>')
    parts.append(f'<input type="{input_type}" class="form-control" placeholder="{placeholder}" value="{value}" />')
    if suffix:
        parts.append(f'<span class="input-group-text">{suffix}</span>')
    if button_text:
        parts.append(f'<button class="site-button site-button-secondary" type="button">{button_text}</button>')
    parts.append("</div></div>")
    return "".join(parts)


def _render_bs_floating_label(block: dict[str, Any]) -> str:
    label = _safe_text(block.get("label"))
    placeholder = _safe_text(block.get("placeholder")) or label
    value = _safe_text(block.get("value"))
    control_as = str(block.get("as") or "input").strip().lower()
    rows = int(block.get("rows") or 4)
    input_type = _safe_text(block.get("input_type") or "text")
    parts = ['<div class="form-floating block-bs-form">']
    if control_as == "textarea":
        parts.append(
            f'<textarea class="form-control" placeholder="{placeholder}" rows="{max(2, min(rows, 12))}">{value}</textarea>'
        )
    else:
        parts.append(f'<input type="{input_type}" class="form-control" placeholder="{placeholder}" value="{value}" />')
    parts.append(f"<label>{label}</label></div>")
    return "".join(parts)


def _render_bs_divider(block: dict[str, Any]) -> str:
    spacing = int(block.get("spacing") or 24)
    spacing = 0 if spacing < 0 else min(spacing, 160)
    label = _safe_text(block.get("label"))
    if label:
        return (
            f'<div class="my-3 block-divider-wrap" style="margin-top:{spacing}px;margin-bottom:{spacing}px;">'
            f'<div class="d-flex align-items-center gap-3"><hr class="flex-grow-1 my-0" />'
            f'<small class="text-muted text-nowrap">{label}</small><hr class="flex-grow-1 my-0" /></div></div>'
        )
    return f'<hr style="margin-top:{spacing}px;margin-bottom:{spacing}px;" />'


def _render_bs_list_group(block: dict[str, Any]) -> str:
    items = block.get("items")
    if isinstance(items, str):
        items = [line.strip() for line in items.splitlines() if line.strip()]
    if not isinstance(items, list) or not items:
        return ""
    numbered = bool(block.get("numbered"))
    classes = "block-number-list" if numbered else "block-bullet-list"
    parts = [f'<ul class="{classes}">']
    for item in items:
        parts.append(f"<li>{_safe_text(item)}</li>")
    parts.append("</ul>")
    return "".join(parts)


def _render_bs_progress(block: dict[str, Any]) -> str:
    value = int(block.get("value") or 0)
    value = 0 if value < 0 else 100 if value > 100 else value
    label = _safe_text(block.get("label")) or f"{value}%"
    variant = _safe_variant(block.get("variant"), default="primary")
    striped = bool(block.get("striped"))
    animated = bool(block.get("animated"))
    classes = [f"bg-{variant}"]
    if striped:
        classes.append("progress-bar-striped")
    if animated:
        classes.append("progress-bar-animated")
    return (
        '<div class="progress" role="progressbar" aria-label="Progress" '
        f'aria-valuenow="{value}" aria-valuemin="0" aria-valuemax="100">'
        f'<div class="progress-bar {" ".join(classes)}" style="width:{value}%">{label}</div></div>'
    )


def _render_bs_breadcrumb(block: dict[str, Any]) -> str:
    items = block.get("items")
    if not isinstance(items, list) or not items:
        return ""
    parts = ['<nav aria-label="breadcrumb"><ol class="breadcrumb mb-0">']
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        label = _safe_text(item.get("label"))
        if not label:
            continue
        href = _safe_url(item.get("url"))
        is_active = bool(item.get("active")) or idx == len(items) - 1
        if is_active:
            parts.append(f'<li class="breadcrumb-item active" aria-current="page">{label}</li>')
        elif href and href != "#":
            parts.append(f'<li class="breadcrumb-item"><a href="{href}">{label}</a></li>')
        else:
            parts.append(f'<li class="breadcrumb-item">{label}</li>')
    parts.append("</ol></nav>")
    return "".join(parts)


def _render_bs_pagination(block: dict[str, Any]) -> str:
    items = block.get("items")
    if not isinstance(items, list) or not items:
        return ""

    align = str(block.get("align") or "start").strip().lower()
    align_class = " is-center" if align == "center" else " is-end" if align == "end" else ""

    parts = [f'<nav class="block-pagination{align_class}" aria-label="Pagination">']
    for item in items:
        if not isinstance(item, dict):
            continue
        label = _safe_text(item.get("label"))
        if not label:
            continue
        href = _safe_url(item.get("url"))
        is_active = bool(item.get("active"))
        is_disabled = bool(item.get("disabled"))
        link_classes = ["block-pagination-item"]
        if is_active:
            link_classes.append("is-active")
        if is_disabled:
            link_classes.append("is-disabled")
        cls_attr = " ".join(link_classes)
        if is_active or is_disabled or not href or href == "#":
            parts.append(f'<span class="{cls_attr}">{label}</span>')
        else:
            parts.append(f'<a class="{cls_attr}" href="{href}">{label}</a>')
    parts.append("</nav>")
    return "".join(parts)


def _render_bs_collapse(block: dict[str, Any]) -> str:
    button_text = _safe_text(block.get("button_text")) or "Toggle content"
    text = _safe_text(block.get("text"))
    if not text:
        return ""
    is_open = bool(block.get("open"))
    open_attr = " open" if is_open else ""
    return f'<details class="block-disclosure"{open_attr}><summary>{button_text}</summary><p>{text}</p></details>'


def _render_bs_spinner(block: dict[str, Any]) -> str:
    variant = _safe_variant(block.get("variant"), default="primary")
    spinner_type = str(block.get("spinner_type") or "border").strip().lower()
    spinner_cls = "spinner-grow" if spinner_type == "grow" else "spinner-border"
    size = str(block.get("size") or "").strip().lower()
    size_cls = " spinner-border-sm" if size == "sm" and spinner_cls == "spinner-border" else ""
    if size == "sm" and spinner_cls == "spinner-grow":
        size_cls = " spinner-grow-sm"
    label = _safe_text(block.get("label")) or "Loading..."
    return (
        '<div class="d-inline-flex align-items-center gap-2">'
        f'<div class="{spinner_cls} text-{variant}{size_cls}" role="status" aria-hidden="true"></div>'
        f'<span>{label}</span>'
        "</div>"
    )


def _render_bs_carousel(block: dict[str, Any]) -> str:
    items = block.get("items")
    if not isinstance(items, list):
        return ""
    normalized: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        src = _safe_url(item.get("image"))
        if not src or src == "#":
            continue
        normalized.append(
            {
                "image": src,
                "title": _safe_text(item.get("title")),
                "caption": _safe_text(item.get("caption")),
                "alt": _safe_text(item.get("alt")) or "Slide image",
            }
        )
    if not normalized:
        return ""

    parts = ['<div class="block-gallery" role="list">']
    for item in normalized:
        parts.append('<figure class="block-gallery-item" role="listitem">')
        parts.append(f'<img src="{item["image"]}" alt="{item["alt"]}" loading="lazy" />')
        if item["title"] or item["caption"]:
            parts.append("<figcaption>")
            if item["title"]:
                parts.append(f'<strong>{item["title"]}</strong>')
            if item["caption"]:
                parts.append(f'<p>{item["caption"]}</p>')
            parts.append("</figcaption>")
        parts.append("</figure>")
    parts.append("</div>")
    return "".join(parts)


def _render_bs_nav(block: dict[str, Any]) -> str:
    items = block.get("items")
    if not isinstance(items, list) or not items:
        return ""
    style = str(block.get("style") or "tabs").strip().lower()
    base_cls = "nav nav-tabs" if style == "tabs" else "nav nav-pills"
    if bool(block.get("fill")):
        base_cls += " nav-fill"
    if bool(block.get("justified")):
        base_cls += " nav-justified"
    if bool(block.get("vertical")):
        base_cls += " flex-column"

    parts = [f'<ul class="{base_cls}">']
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        label = _safe_text(item.get("label"))
        href = _safe_url(item.get("url"))
        if not label:
            continue
        is_active = bool(item.get("active")) or idx == 0
        link_cls = "nav-link" + (" active" if is_active else "")
        parts.append(
            f'<li class="nav-item"><a class="{link_cls}" href="{href if href and href != "#" else "#"}">{label}</a></li>'
        )
    parts.append("</ul>")
    return "".join(parts)


def _render_bs_modal(block: dict[str, Any]) -> str:
    button_text = _safe_text(block.get("button_text")) or "Open modal"
    title = _safe_text(block.get("title")) or "Modal title"
    text = _safe_text(block.get("text"))
    if not text:
        return ""
    return (
        '<section class="block-callout">'
        f'<p class="block-callout-eyebrow">{button_text}</p>'
        f'<h3>{title}</h3>'
        f'<p>{text}</p>'
        "</section>"
    )


def _render_bs_toast(block: dict[str, Any]) -> str:
    title = _safe_text(block.get("title")) or "Notification"
    text = _safe_text(block.get("text"))
    if not text:
        return ""
    return f'<aside class="block-notice" role="status"><strong>{title}</strong><p>{text}</p></aside>'


def _render_bs_offcanvas(block: dict[str, Any]) -> str:
    button_text = _safe_text(block.get("button_text")) or "Open panel"
    title = _safe_text(block.get("title")) or "Panel"
    text = _safe_text(block.get("text"))
    if not text:
        return ""
    return f'<details class="block-disclosure"><summary>{button_text}</summary><h3>{title}</h3><p>{text}</p></details>'


def _render_bs_close_button(block: dict[str, Any]) -> str:
    white = " btn-close-white" if bool(block.get("white")) else ""
    disabled = " disabled" if bool(block.get("disabled")) else ""
    return f'<button type="button" class="btn-close{white}" aria-label="Close"{disabled}></button>'


def _render_bs_tooltip(block: dict[str, Any]) -> str:
    text = _safe_text(block.get("text")) or "Hover for tooltip"
    title = _safe_text(block.get("title"))
    if not title:
        return ""
    return f'<span class="block-inline-help"><strong>{text}</strong><small>{title}</small></span>'


def _render_bs_popover(block: dict[str, Any]) -> str:
    button_text = _safe_text(block.get("button_text")) or "Open popover"
    content = _safe_text(block.get("content"))
    if not content:
        return ""
    title = _safe_text(block.get("title"))
    return f'<details class="block-disclosure"><summary>{button_text}</summary><h3>{title}</h3><p>{content}</p></details>'


def _render_bs_scrollspy(block: dict[str, Any]) -> str:
    items = block.get("items")
    if not isinstance(items, list) or not items:
        return ""
    scroll_height = int(block.get("height") or 260)
    scroll_height = 180 if scroll_height < 180 else 600 if scroll_height > 600 else scroll_height
    spy_id = f"scrollspy-{uuid4().hex[:8]}"
    nav_id = f"{spy_id}-nav"
    parts = ['<div class="block-anchor-layout">']
    parts.append('<nav id="{}" class="block-anchor-nav" aria-label="Section navigation">'.format(nav_id))
    section_parts: list[str] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        label = _safe_text(item.get("label")) or f"Section {idx + 1}"
        title = _safe_text(item.get("title")) or label
        text = _safe_text(item.get("text"))
        section_id = f"{spy_id}-section-{idx}"
        parts.append(f'<a href="#{section_id}">{label}</a>')
        section_parts.append(
            f'<section id="{section_id}" class="block-anchor-section">'
            f'<h3>{title}</h3><p>{text}</p></section>'
        )
    parts.append("</nav>")
    parts.append(
        f'<div class="block-anchor-content" tabindex="0" style="max-height:{scroll_height}px;overflow:auto;">'
        f'{"".join(section_parts)}</div>'
    )
    parts.append("</div>")
    return "".join(parts)


def _render_bs_timeline(block: dict[str, Any]) -> str:
    items = block.get("items")
    if not isinstance(items, list):
        return ""
    normalized: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        date = _safe_text(item.get("date"))
        title = _safe_text(item.get("title"))
        text = _safe_text(item.get("text"))
        if not title and not text:
            continue
        normalized.append({"date": date, "title": title, "text": text})
    if not normalized:
        return ""
    section_title = _safe_text(block.get("title"))
    parts = ['<section class="block-bs-timeline">']
    if section_title:
        parts.append(f'<h3 class="mb-3">{section_title}</h3>')
    parts.append('<ol class="timeline-list">')
    for item in normalized:
        parts.append('<li class="timeline-item">')
        if item["date"]:
            parts.append(f'<small class="timeline-date">{item["date"]}</small>')
        if item["title"]:
            parts.append(f'<h4 class="timeline-title">{item["title"]}</h4>')
        if item["text"]:
            parts.append(f'<p class="timeline-text">{item["text"]}</p>')
        parts.append("</li>")
    parts.append("</ol></section>")
    return "".join(parts)


def _render_bs_pricing_table(block: dict[str, Any]) -> str:
    plans = block.get("plans")
    if not isinstance(plans, list):
        return ""
    normalized: list[dict[str, Any]] = []
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        title = _safe_text(plan.get("title"))
        price = _safe_text(plan.get("price"))
        period = _safe_text(plan.get("period"))
        features_raw = plan.get("features")
        features: list[str] = []
        if isinstance(features_raw, list):
            features = [_safe_text(x) for x in features_raw if str(x).strip()]
        if not title and not price and not features:
            continue
        normalized.append(
            {
                "title": title,
                "price": price,
                "period": period,
                "features": features,
                "button_label": _safe_text(plan.get("button_label")) or "Choose",
                "button_url": _safe_url(plan.get("button_url")),
                "recommended": bool(plan.get("recommended")),
            }
        )
    if not normalized:
        return ""

    section_title = _safe_text(block.get("title"))
    section_subtitle = _safe_text(block.get("subtitle"))
    parts = ['<section class="block-bs-pricing">']
    if section_title:
        parts.append(f'<h3 class="feature-card-title">{section_title}</h3>')
    if section_subtitle:
        parts.append(f'<p class="feature-card-copy">{section_subtitle}</p>')
    parts.append('<div class="block-pricing-grid">')
    for plan in normalized:
        card_cls = "surface-card block-card block-card-static"
        if plan["recommended"]:
            card_cls += " is-recommended"
        parts.append(f'<article class="{card_cls}"><div class="block-card-body">')
        if plan["recommended"]:
            parts.append('<span class="site-chip">Popular</span>')
        if plan["title"]:
            parts.append(f'<h4 class="feature-card-title">{plan["title"]}</h4>')
        if plan["price"]:
            parts.append(f'<p class="block-pricing-price">{plan["price"]}</p>')
        if plan["period"]:
            parts.append(f'<p class="feature-card-copy">{plan["period"]}</p>')
        if plan["features"]:
            parts.append('<ul class="block-bullet-list">')
            for feature in plan["features"]:
                parts.append(f'<li>{feature}</li>')
            parts.append("</ul>")
        btn_url = plan["button_url"]
        btn_href = btn_url if btn_url and btn_url != "#" else "#"
        btn_cls = "site-button site-button-primary" if plan["recommended"] else "site-button site-button-secondary"
        parts.append(f'<a class="{btn_cls}" href="{btn_href}">{plan["button_label"]}</a>')
        parts.append('</div></article>')
    parts.append('</div></section>')
    return "".join(parts)


def _normalize_bs_columns(raw_columns: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_columns, list):
        return []
    normalized: list[dict[str, Any]] = []
    for col in raw_columns:
        if not isinstance(col, dict):
            continue
        width = int(col.get("width") or 6)
        width = 1 if width < 1 else 12 if width > 12 else width
        blocks = col.get("blocks")
        if not isinstance(blocks, list):
            blocks = []
        normalized.append({"width": width, "blocks": blocks})
    return normalized


def _render_bs_row(block: dict[str, Any]) -> str:
    columns = _normalize_bs_columns(block.get("columns"))
    if not columns:
        return ""
    gutter = int(block.get("gutter") or 3)
    gutter = 0 if gutter < 0 else 5 if gutter > 5 else gutter
    align = str(block.get("align") or "start").strip().lower()
    align_class = (
        "align-items-center"
        if align == "center"
        else "align-items-end"
        if align == "end"
        else "align-items-stretch"
        if align == "stretch"
        else "align-items-start"
    )

    rendered_columns: list[str] = []
    for col in columns:
        col_html = str(render_content_blocks(col.get("blocks") or [], ""))
        if col_html.strip():
            rendered_columns.append(f'<div class="col-12 col-md-{col["width"]}">{col_html}</div>')
    if not rendered_columns:
        return ""
    return f'<div class="row g-{gutter} {align_class}">{"".join(rendered_columns)}</div>'


def _render_bs_container(block: dict[str, Any]) -> str:
    rows = block.get("rows")
    if not isinstance(rows, list) or not rows:
        return ""
    fluid = bool(block.get("fluid"))
    container_cls = "container-fluid" if fluid else "container"
    rendered_rows: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rendered = _render_bs_row(row)
        if rendered:
            rendered_rows.append(rendered)
    if not rendered_rows:
        return ""
    return f'<section class="block-bs-container {container_cls}">{"".join(rendered_rows)}</section>'


def _render_bs_dropdown(block: dict[str, Any]) -> str:
    button_label = _safe_text(block.get("button_text") or block.get("button_label")) or "Open menu"
    items = block.get("items")
    if not isinstance(items, list):
        return ""
    menu_items: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = _safe_text(item.get("label"))
        href = _safe_url(item.get("url"))
        if not label:
            continue
        if bool(item.get("divider_before")):
            menu_items.append('<li class="block-menu-separator" aria-hidden="true"></li>')
        menu_items.append(f'<li><a href="{href}">{label}</a></li>')
    if not menu_items:
        return ""
    return (
        '<details class="block-menu">'
        f'<summary>{button_label}</summary>'
        f'<ul>{"".join(menu_items)}</ul>'
        "</details>"
    )


def _render_bs_navbar(block: dict[str, Any]) -> str:
    brand = _safe_text(block.get("brand")) or "VXcloud"
    brand_url = _safe_url(block.get("brand_url"))
    items = block.get("items")
    if not isinstance(items, list):
        items = []
    nav_items: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = _safe_text(item.get("label"))
        href = _safe_url(item.get("url"))
        active = " active" if bool(item.get("active")) else ""
        if not label:
            continue
        nav_items.append(f'<li><a class="site-nav-link{active}" href="{href}">{label}</a></li>')
    return (
        '<nav class="block-inline-nav">'
        f'<a class="block-inline-nav-brand" href="{brand_url if brand_url and brand_url != "#" else "#"}">{brand}</a>'
        f'<ul class="block-inline-nav-links">{"".join(nav_items)}</ul>'
        "</nav>"
    )


def _render_bs_ratio(block: dict[str, Any]) -> str:
    ratio = str(block.get("ratio") or "16x9").strip().lower()
    allowed = {"1x1", "4x3", "16x9", "21x9"}
    ratio = ratio if ratio in allowed else "16x9"
    src = _safe_url(block.get("url"))
    raw_html = str(block.get("html") or "").strip()
    embed_type = str(block.get("embed_type") or "iframe").strip().lower()
    if raw_html:
        inner = raw_html
    elif src and src != "#":
        if embed_type == "video":
            inner = f'<video src="{src}" controls class="w-100 h-100"></video>'
        else:
            inner = f'<iframe src="{src}" title="Embedded media" allowfullscreen loading="lazy"></iframe>'
    else:
        return ""
    return (
        f'<div class="ratio ratio-{ratio}">'
        f"{inner}"
        f"</div>"
    )


def _render_bs_placeholder(block: dict[str, Any]) -> str:
    lines = int(block.get("lines") or 3)
    lines = 1 if lines < 1 else 8 if lines > 8 else lines
    width = int(block.get("width") or 100)
    width = 10 if width < 10 else 100 if width > 100 else width
    size = str(block.get("size") or "").strip().lower()
    size_cls = " placeholder-lg" if size == "lg" else " placeholder-sm" if size == "sm" else ""
    animation = str(block.get("animation") or "").strip().lower()
    wrapper_cls = "placeholder-wave" if animation == "wave" else "placeholder-glow" if animation == "glow" else ""
    parts = [f'<div class="{wrapper_cls}">']
    for _ in range(lines):
        parts.append(f'<span class="placeholder{size_cls} col-{max(1, min(12, round(width / 8.33)))}"></span>')
    parts.append("</div>")
    return "".join(parts)


def _render_bs_icon_link(block: dict[str, Any]) -> str:
    label = _safe_text(block.get("label"))
    href = _safe_url(block.get("url"))
    if not label:
        return ""
    return f'<a class="icon-link" href="{href}">{label}<span aria-hidden="true">→</span></a>'


def _render_bs_stretched_link(block: dict[str, Any]) -> str:
    title = _safe_text(block.get("title"))
    text = _safe_text(block.get("text"))
    label = _safe_text(block.get("label")) or "Read more"
    href = _safe_url(block.get("url"))
    if not title and not text:
        return ""
    return (
        '<article class="surface-card block-card block-card-static block-bs-stretched-link"><div class="block-card-body">'
        f'<h5 class="feature-card-title">{title}</h5><p class="feature-card-copy">{text}</p>'
        f'<a class="post-inline-link" href="{href}">{label}</a>'
        "</div></article>"
    )


def _render_bs_text_truncation(block: dict[str, Any]) -> str:
    text = _safe_text(block.get("text"))
    if not text:
        return ""
    width = int(block.get("width") or 220)
    width = 80 if width < 80 else 640 if width > 640 else width
    return f'<div class="text-truncate" style="max-width:{width}px;">{text}</div>'


def _render_bs_vertical_rule(block: dict[str, Any]) -> str:
    before_text = _safe_text(block.get("before_text"))
    after_text = _safe_text(block.get("after_text"))
    return (
        '<div class="hstack gap-3 block-bs-vr">'
        f'<div>{before_text}</div><div class="vr"></div><div>{after_text}</div>'
        "</div>"
    )


def _render_bs_visually_hidden(block: dict[str, Any]) -> str:
    text = _safe_text(block.get("text"))
    if not text:
        return ""
    focusable = "-focusable" if bool(block.get("focusable")) else ""
    return f'<a class="visually-hidden{focusable}" href="#main-content">{text}</a>'


def _render_bs_stacks(block: dict[str, Any]) -> str:
    items = block.get("items")
    if not isinstance(items, list):
        return ""
    direction = str(block.get("direction") or "horizontal").strip().lower()
    gap = int(block.get("gap") or 3)
    gap = 1 if gap < 1 else 5 if gap > 5 else gap
    stack_cls = "vstack" if direction == "vertical" else "hstack"
    rendered_items = []
    for item in items:
        item_text = _safe_text(item)
        if item_text:
            rendered_items.append(f'<div class="p-2 border rounded bg-body-tertiary">{item_text}</div>')
    if not rendered_items:
        return ""
    return f'<div class="{stack_cls} gap-{gap} block-bs-stacks">{"".join(rendered_items)}</div>'


def _render_cards_slider(block: dict[str, Any]) -> str:
    title = _safe_text(block.get("title"))
    subtitle = _safe_text(block.get("subtitle"))
    raw_items = block.get("items")
    if not raw_items:
        raw_items = block.get("lines")
    if not raw_items:
        raw_items = block.get("line")
    if not raw_items:
        raw_items = block.get("text")
    items = _normalize_slider_items(raw_items)
    if not items:
        return ""

    parts: list[str] = ['<section class="block-cards-slider">']
    if title or subtitle:
        parts.append('<div class="block-cards-slider-head">')
        if title:
            parts.append(f"<h2>{title}</h2>")
        if subtitle:
            parts.append(f"<p>{subtitle}</p>")
        parts.append("</div>")

    parts.append('<div class="block-cards-viewport">')
    parts.append('<div class="block-cards-track" role="list">')
    for item in items:
        item_title = _safe_text(item["title"])
        item_text = _safe_text(item["text"])
        if not item_title and not item_text:
            continue
        parts.append('<article class="block-card" role="listitem">')
        if item_title:
            parts.append(f"<h3>{item_title}</h3>")
        if item_text:
            parts.append(f"<p>{item_text}</p>")
        parts.append("</article>")
    parts.append("</div></div></section>")
    return "".join(parts)


def _normalize_slider_items(raw_items: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []

    if isinstance(raw_items, list):
        for row in raw_items:
            if isinstance(row, dict):
                title = str(row.get("title") or "").strip()
                text = str(row.get("text") or "").strip()
                if title or text:
                    normalized.append({"title": title, "text": text})
            elif isinstance(row, str):
                parsed = _parse_slider_line(row)
                if parsed["title"] or parsed["text"]:
                    normalized.append(parsed)
        return normalized

    if not isinstance(raw_items, str):
        return normalized

    raw = raw_items.replace("\r", "\n")
    lines = [line.strip() for line in raw.split("\n") if line.strip()]

    # Backward compatibility: single collapsed string "title|text|title|text|..."
    if len(lines) == 1 and raw.count("|") >= 2:
        chunks = [chunk.strip() for chunk in raw.split("|") if chunk.strip()]
        paired: list[str] = []
        i = 0
        while i < len(chunks):
            left = chunks[i]
            right = chunks[i + 1] if i + 1 < len(chunks) else ""
            paired.append(f"{left}|{right}")
            i += 2
        lines = paired

    for line in lines:
        parsed = _parse_slider_line(line)
        if parsed["title"] or parsed["text"]:
            normalized.append(parsed)
    return normalized


def _parse_slider_line(line: str) -> dict[str, str]:
    if "|" not in line:
        return {"title": line.strip(), "text": ""}
    left, right = line.split("|", 1)
    return {"title": left.strip(), "text": right.strip()}


def _parse_legacy_json_blocks(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, str):
        return []
    payload = raw.strip()
    if not payload or payload[0] not in "[{":
        return []
    try:
        parsed = json.loads(payload)
    except Exception:
        return []
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return []


def render_content_blocks(blocks: Any, legacy_html: str = ""):
    if not isinstance(blocks, list) or not blocks:
        parsed_legacy_blocks = _parse_legacy_json_blocks(legacy_html)
        if parsed_legacy_blocks:
            return render_content_blocks(parsed_legacy_blocks, "")
        return mark_safe(legacy_html or "")

    output: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "").strip().lower()

        if block_type in {"paragraph", "bs_paragraph"}:
            text = _safe_text(block.get("text"))
            if text:
                output.append(f"<p>{text}</p>")
        elif block_type in {"heading", "bs_heading"}:
            text = _safe_text(block.get("text"))
            level = int(block.get("level") or 2)
            level = 2 if level < 1 or level > 6 else level
            if text:
                output.append(f"<h{level}>{text}</h{level}>")
        elif block_type in {"list", "bs_list"}:
            items = [str(x).strip() for x in (block.get("items") or []) if str(x).strip()]
            ordered = bool(block.get("ordered"))
            if items:
                tag = "ol" if ordered else "ul"
                rendered = "".join(f"<li>{_safe_text(item)}</li>" for item in items)
                output.append(f"<{tag}>{rendered}</{tag}>")
        elif block_type in {"quote", "bs_quote"}:
            text = _safe_text(block.get("text"))
            cite = _safe_text(block.get("cite"))
            if text:
                if cite:
                    output.append(f"<blockquote><p>{text}</p><cite>{cite}</cite></blockquote>")
                else:
                    output.append(f"<blockquote><p>{text}</p></blockquote>")
        elif block_type in {"image", "bs_image"}:
            src = _safe_url(block.get("src"))
            alt = _safe_text(block.get("alt"))
            caption = _safe_text(block.get("caption"))
            if src and src != "#":
                figure = [f'<figure class="block-image"><img src="{src}" alt="{alt}" loading="lazy" />']
                if caption:
                    figure.append(f"<figcaption>{caption}</figcaption>")
                figure.append("</figure>")
                output.append("".join(figure))
        elif block_type == "bs_figure":
            rendered = _render_bs_figure(block)
            if rendered:
                output.append(rendered)
        elif block_type in {"embed", "bs_embed"}:
            url = _safe_url(block.get("url"))
            if url and url != "#":
                output.append(
                    '<div class="block-embed">'
                    f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'
                    "</div>"
                )
        elif block_type in {"button", "bs_button"}:
            label = _safe_text(block.get("label"))
            href = _safe_url(block.get("url"))
            style = str(block.get("style") or "primary").strip().lower()
            css = "site-button site-button-primary" if style != "secondary" else "site-button site-button-secondary"
            if label:
                output.append(f'<div class="block-buttons"><a class="{css}" href="{href}">{label}</a></div>')
        elif block_type in {"buttons", "bs_button_group"}:
            items = block.get("items") or []
            if isinstance(items, list):
                output.append(_render_buttons(items))
        elif block_type in {"spacer", "bs_spacer"}:
            px = int(block.get("height") or 24)
            px = 16 if px < 8 else min(px, 180)
            output.append(f'<div class="block-spacer" style="height:{px}px"></div>')
        elif block_type in {"faq", "bs_faq"}:
            q = _safe_text(block.get("question"))
            a = _safe_text(block.get("answer"))
            if q:
                output.append(f'<details class="block-faq"><summary>{q}</summary><p>{a}</p></details>')
        elif block_type == "bs_alert":
            rendered = _render_bs_alert(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_badge":
            rendered = _render_bs_badge(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_card":
            rendered = _render_bs_card(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_accordion":
            rendered = _render_bs_accordion(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_tabs":
            rendered = _render_bs_tabs(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_table":
            rendered = _render_bs_table(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_form_control":
            rendered = _render_bs_form_control(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_form_select":
            rendered = _render_bs_form_select(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_form_checks":
            rendered = _render_bs_form_checks(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_form_range":
            rendered = _render_bs_form_range(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_input_group":
            rendered = _render_bs_input_group(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_floating_label":
            rendered = _render_bs_floating_label(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_divider":
            rendered = _render_bs_divider(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_list_group":
            rendered = _render_bs_list_group(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_progress":
            rendered = _render_bs_progress(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_breadcrumb":
            rendered = _render_bs_breadcrumb(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_pagination":
            rendered = _render_bs_pagination(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_collapse":
            rendered = _render_bs_collapse(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_spinner":
            rendered = _render_bs_spinner(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_carousel":
            rendered = _render_bs_carousel(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_nav":
            rendered = _render_bs_nav(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_modal":
            rendered = _render_bs_modal(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_toast":
            rendered = _render_bs_toast(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_offcanvas":
            rendered = _render_bs_offcanvas(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_close_button":
            rendered = _render_bs_close_button(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_tooltip":
            rendered = _render_bs_tooltip(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_popover":
            rendered = _render_bs_popover(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_scrollspy":
            rendered = _render_bs_scrollspy(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_timeline":
            rendered = _render_bs_timeline(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_pricing_table":
            rendered = _render_bs_pricing_table(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_dropdown":
            rendered = _render_bs_dropdown(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_navbar":
            rendered = _render_bs_navbar(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_ratio":
            rendered = _render_bs_ratio(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_placeholder":
            rendered = _render_bs_placeholder(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_icon_link":
            rendered = _render_bs_icon_link(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_stretched_link":
            rendered = _render_bs_stretched_link(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_text_truncation":
            rendered = _render_bs_text_truncation(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_vertical_rule":
            rendered = _render_bs_vertical_rule(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_visually_hidden":
            rendered = _render_bs_visually_hidden(block)
            if rendered:
                output.append(rendered)
        elif block_type == "bs_stacks":
            rendered = _render_bs_stacks(block)
            if rendered:
                output.append(rendered)
        elif block_type == "columns":
            left_html = ""
            right_html = ""

            left_blocks = block.get("left_blocks")
            if isinstance(left_blocks, list):
                left_html = str(render_content_blocks(left_blocks, ""))
            if not left_html:
                left = _safe_text(block.get("left"))
                if left:
                    left_html = f"<p>{left}</p>"

            right_blocks = block.get("right_blocks")
            if isinstance(right_blocks, list):
                right_html = str(render_content_blocks(right_blocks, ""))
            if not right_html:
                right = _safe_text(block.get("right"))
                if right:
                    right_html = f"<p>{right}</p>"

            output.append(
                '<div class="block-columns">'
                f'<div class="block-column">{left_html}</div>'
                f'<div class="block-column">{right_html}</div>'
                "</div>"
            )
        elif block_type in {"rows", "raws", "bs_container", "bs_rows", "bs_columns"}:
            if block_type in {"bs_container", "bs_rows", "bs_columns"}:
                rendered = _render_bs_container(block)
                if rendered:
                    output.append(rendered)
                continue
            rows = block.get("rows")
            rendered_rows: list[str] = []

            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    columns = row.get("columns")
                    if not isinstance(columns, list):
                        continue

                    rendered_columns: list[str] = []
                    for col in columns:
                        if not isinstance(col, dict):
                            continue
                        col_html = ""
                        col_blocks = col.get("blocks")
                        if isinstance(col_blocks, list):
                            col_html = str(render_content_blocks(col_blocks, ""))
                        if not col_html:
                            legacy_col_text = _safe_text(col.get("text"))
                            if legacy_col_text:
                                col_html = f"<p>{legacy_col_text}</p>"
                        if col_html:
                            width = int(col.get("width") or 6)
                            width = 1 if width < 1 else 12 if width > 12 else width
                            rendered_columns.append(
                                f'<div class="block-row-column col-12 col-md-{width}">{col_html}</div>'
                            )

                    if rendered_columns:
                        gutter = int(row.get("gutter") or 3)
                        gutter = 0 if gutter < 0 else 5 if gutter > 5 else gutter
                        align = str(row.get("align") or "start").strip().lower()
                        align_class = (
                            "align-items-center"
                            if align == "center"
                            else "align-items-end"
                            if align == "end"
                            else "align-items-stretch"
                            if align == "stretch"
                            else "align-items-start"
                        )
                        rendered_rows.append(
                            f'<div class="block-row-layout row gx-{gutter} gy-{gutter} {align_class}">'
                            f'{"".join(rendered_columns)}'
                            "</div>"
                        )

            if rendered_rows:
                output.append(f'<div class="block-rows-layout">{"".join(rendered_rows)}</div>')
            else:
                # Legacy fallback: one line = one row
                items = [str(x).strip() for x in (block.get("items") or []) if str(x).strip()]
                if items:
                    rendered = "".join(f'<div class="block-row"><p>{_safe_text(item)}</p></div>' for item in items)
                    output.append(f'<div class="block-rows">{rendered}</div>')
        elif block_type in {"html", "bs_html"}:
            custom = str(block.get("html") or "").strip()
            if custom:
                output.append(custom)
        elif block_type in {"cards_slider", "cards-slider", "cards slider", "cs_cards_slider", "bs_cards_slider"}:
            rendered = _render_cards_slider(block)
            if rendered:
                output.append(rendered)

    if not output:
        return mark_safe(legacy_html or "")
    return mark_safe("".join(output))
