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
    parts: list[str] = ['<div class="block-buttons">']
    for item in items:
        label = _safe_text(item.get("label"))
        href = _safe_url(item.get("url"))
        style = str(item.get("style") or "primary").strip().lower()
        css = "btn btn-primary" if style != "secondary" else "btn btn-secondary"
        parts.append(f'<a class="{css}" href="{href}">{label}</a>')
    parts.append("</div>")
    return "".join(parts)


def _safe_variant(value: Any, *, default: str = "primary") -> str:
    allowed = {"primary", "secondary", "success", "danger", "warning", "info", "light", "dark", "link"}
    variant = str(value or "").strip().lower()
    return variant if variant in allowed else default


def _render_bs_alert(block: dict[str, Any]) -> str:
    variant = _safe_variant(block.get("variant"), default="info")
    title = _safe_text(block.get("title"))
    text = _safe_text(block.get("text"))
    if not title and not text:
        return ""
    parts = [f'<div class="alert alert-{variant}" role="alert">']
    if title:
        parts.append(f'<h5 class="alert-heading mb-2">{title}</h5>')
    if text:
        parts.append(f"<p class='mb-0'>{text}</p>")
    parts.append("</div>")
    return "".join(parts)


def _render_bs_badge(block: dict[str, Any]) -> str:
    text = _safe_text(block.get("text"))
    if not text:
        return ""
    variant = _safe_variant(block.get("variant"), default="primary")
    pill = " rounded-pill" if bool(block.get("pill", True)) else ""
    return f'<span class="badge text-bg-{variant}{pill}">{text}</span>'


def _render_bs_card(block: dict[str, Any]) -> str:
    title = _safe_text(block.get("title"))
    text = _safe_text(block.get("text"))
    image = _safe_url(block.get("image"))
    button_label = _safe_text(block.get("button_label"))
    button_url = _safe_url(block.get("button_url"))
    button_variant = _safe_variant(block.get("button_style"), default="primary")
    if not title and not text and (not image or image == "#"):
        return ""
    parts = ['<article class="card shadow-sm border-0">']
    if image and image != "#":
        parts.append(f'<img src="{image}" class="card-img-top" alt="{title or "Card image"}" loading="lazy" />')
    parts.append('<div class="card-body">')
    if title:
        parts.append(f'<h5 class="card-title">{title}</h5>')
    if text:
        parts.append(f'<p class="card-text">{text}</p>')
    if button_label and button_url and button_url != "#":
        parts.append(f'<a href="{button_url}" class="btn btn-{button_variant}">{button_label}</a>')
    parts.append("</div></article>")
    return "".join(parts)


def _render_bs_accordion(block: dict[str, Any]) -> str:
    items = block.get("items")
    if not isinstance(items, list) or not items:
        return ""
    acc_id = f"acc-{uuid4().hex[:8]}"
    flush = " accordion-flush" if bool(block.get("flush")) else ""
    parts = [f'<div class="accordion{flush}" id="{acc_id}">']
    for idx, row in enumerate(items):
        if not isinstance(row, dict):
            continue
        title = _safe_text(row.get("title"))
        text = _safe_text(row.get("text"))
        if not title and not text:
            continue
        item_id = f"{acc_id}-{idx}"
        is_open = idx == 0
        btn_cls = "accordion-button" + ("" if is_open else " collapsed")
        collapse_cls = "accordion-collapse collapse" + (" show" if is_open else "")
        parts.append('<div class="accordion-item">')
        parts.append(
            f'<h2 class="accordion-header" id="head-{item_id}">'
            f'<button class="{btn_cls}" type="button" data-bs-toggle="collapse" '
            f'data-bs-target="#{item_id}" aria-expanded="{str(is_open).lower()}" '
            f'aria-controls="{item_id}">{title or f"Item {idx + 1}"}</button></h2>'
        )
        parts.append(
            f'<div id="{item_id}" class="{collapse_cls}" aria-labelledby="head-{item_id}" '
            f'data-bs-parent="#{acc_id}"><div class="accordion-body">{text}</div></div>'
        )
        parts.append("</div>")
    parts.append("</div>")
    return "".join(parts)


def _render_bs_tabs(block: dict[str, Any]) -> str:
    items = block.get("items")
    if not isinstance(items, list) or not items:
        return ""
    tabs_id = f"tabs-{uuid4().hex[:8]}"
    style = str(block.get("style") or "tabs").strip().lower()
    nav_cls = "nav nav-pills mb-3" if style == "pills" else "nav nav-tabs mb-3"
    parts = [f'<div class="block-bs-tabs" id="{tabs_id}">', f'<ul class="{nav_cls}" role="tablist">']
    panes: list[str] = []
    for idx, row in enumerate(items):
        if not isinstance(row, dict):
            continue
        title = _safe_text(row.get("title"))
        text = _safe_text(row.get("text"))
        tab_id = f"{tabs_id}-tab-{idx}"
        pane_id = f"{tabs_id}-pane-{idx}"
        is_active = idx == 0
        btn_cls = "nav-link" + (" active" if is_active else "")
        pane_cls = "tab-pane fade" + (" show active" if is_active else "")
        parts.append(
            f'<li class="nav-item" role="presentation"><button class="{btn_cls}" id="{tab_id}" '
            f'data-bs-toggle="tab" data-bs-target="#{pane_id}" type="button" role="tab" '
            f'aria-controls="{pane_id}" aria-selected="{str(is_active).lower()}">{title or f"Tab {idx + 1}"}</button></li>'
        )
        panes.append(f'<div class="{pane_cls}" id="{pane_id}" role="tabpanel" aria-labelledby="{tab_id}"><p class="mb-0">{text}</p></div>')
    parts.append("</ul>")
    parts.append(f'<div class="tab-content border border-top-0 rounded-bottom p-3">{"".join(panes)}</div></div>')
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
    flush = bool(block.get("flush"))
    classes = ["list-group"]
    if numbered:
        classes.append("list-group-numbered")
    if flush:
        classes.append("list-group-flush")
    parts = [f'<ul class="{" ".join(classes)}">']
    for item in items:
        parts.append(f'<li class="list-group-item">{_safe_text(item)}</li>')
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

    size = str(block.get("size") or "").strip().lower()
    size_class = " pagination-sm" if size == "sm" else " pagination-lg" if size == "lg" else ""
    align = str(block.get("align") or "start").strip().lower()
    align_class = " justify-content-center" if align == "center" else " justify-content-end" if align == "end" else ""

    parts = [f'<nav aria-label="Pagination"><ul class="pagination{size_class}{align_class}">']
    for item in items:
        if not isinstance(item, dict):
            continue
        label = _safe_text(item.get("label"))
        if not label:
            continue
        href = _safe_url(item.get("url"))
        is_active = bool(item.get("active"))
        is_disabled = bool(item.get("disabled"))
        li_classes = []
        if is_active:
            li_classes.append("active")
        if is_disabled:
            li_classes.append("disabled")
        li_cls = f' class="page-item {" ".join(li_classes)}"' if li_classes else ' class="page-item"'
        if is_active or is_disabled or not href or href == "#":
            parts.append(f"<li{li_cls}><span class=\"page-link\">{label}</span></li>")
        else:
            parts.append(f"<li{li_cls}><a class=\"page-link\" href=\"{href}\">{label}</a></li>")
    parts.append("</ul></nav>")
    return "".join(parts)


def _render_bs_collapse(block: dict[str, Any]) -> str:
    button_text = _safe_text(block.get("button_text")) or "Toggle content"
    text = _safe_text(block.get("text"))
    if not text:
        return ""
    collapse_id = f"collapse-{uuid4().hex[:8]}"
    variant = _safe_variant(block.get("variant"), default="primary")
    is_open = bool(block.get("open"))
    btn_cls = f"btn btn-{variant}"
    aria_expanded = "true" if is_open else "false"
    collapse_cls = "collapse show" if is_open else "collapse"
    return (
        f'<p><button class="{btn_cls}" type="button" data-bs-toggle="collapse" '
        f'data-bs-target="#{collapse_id}" aria-expanded="{aria_expanded}" aria-controls="{collapse_id}">{button_text}</button></p>'
        f'<div class="{collapse_cls}" id="{collapse_id}"><div class="card card-body">{text}</div></div>'
    )


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

    carousel_id = f"carousel-{uuid4().hex[:8]}"
    show_controls = bool(block.get("controls", True))
    show_indicators = bool(block.get("indicators", True))
    fade = bool(block.get("fade"))
    ride = bool(block.get("auto", False))
    carousel_cls = "carousel slide" + (" carousel-fade" if fade else "")
    ride_attr = ' data-bs-ride="carousel"' if ride else ""

    parts = [f'<div id="{carousel_id}" class="{carousel_cls}"{ride_attr}>']
    if show_indicators:
        parts.append('<div class="carousel-indicators">')
        for idx, _ in enumerate(normalized):
            active = ' class="active"' if idx == 0 else ""
            current = ' aria-current="true"' if idx == 0 else ""
            parts.append(
                f'<button type="button" data-bs-target="#{carousel_id}" data-bs-slide-to="{idx}"'
                f'{active}{current} aria-label="Slide {idx + 1}"></button>'
            )
        parts.append("</div>")
    parts.append('<div class="carousel-inner rounded-3 overflow-hidden">')
    for idx, item in enumerate(normalized):
        active = " active" if idx == 0 else ""
        parts.append(f'<div class="carousel-item{active}">')
        parts.append(f'<img src="{item["image"]}" class="d-block w-100" alt="{item["alt"]}" loading="lazy" />')
        if item["title"] or item["caption"]:
            parts.append('<div class="carousel-caption d-none d-md-block">')
            if item["title"]:
                parts.append(f'<h5>{item["title"]}</h5>')
            if item["caption"]:
                parts.append(f'<p>{item["caption"]}</p>')
            parts.append("</div>")
        parts.append("</div>")
    parts.append("</div>")
    if show_controls:
        parts.append(
            f'<button class="carousel-control-prev" type="button" data-bs-target="#{carousel_id}" data-bs-slide="prev">'
            '<span class="carousel-control-prev-icon" aria-hidden="true"></span><span class="visually-hidden">Previous</span></button>'
        )
        parts.append(
            f'<button class="carousel-control-next" type="button" data-bs-target="#{carousel_id}" data-bs-slide="next">'
            '<span class="carousel-control-next-icon" aria-hidden="true"></span><span class="visually-hidden">Next</span></button>'
        )
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
    button_variant = _safe_variant(block.get("button_variant"), default="primary")
    size = str(block.get("size") or "").strip().lower()
    size_cls = " modal-sm" if size == "sm" else " modal-lg" if size == "lg" else " modal-xl" if size == "xl" else ""
    dialog_classes = []
    if bool(block.get("scrollable")):
        dialog_classes.append("modal-dialog-scrollable")
    if bool(block.get("centered")):
        dialog_classes.append("modal-dialog-centered")
    if bool(block.get("fullscreen")):
        dialog_classes.append("modal-fullscreen")
    modal_id = f"modal-{uuid4().hex[:8]}"
    dialog = f'modal-dialog{size_cls} {" ".join(dialog_classes)}'.strip()
    secondary = _safe_text(block.get("footer_secondary_text")) or "Close"
    primary = _safe_text(block.get("footer_primary_text")) or "Got it"

    return (
        f'<div class="block-bs-modal"><button type="button" class="btn btn-{button_variant}" '
        f'data-bs-toggle="modal" data-bs-target="#{modal_id}">{button_text}</button>'
        f'<div class="modal fade" id="{modal_id}" tabindex="-1" aria-hidden="true">'
        f'<div class="{dialog}"><div class="modal-content">'
        f'<div class="modal-header"><h5 class="modal-title">{title}</h5>'
        f'<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>'
        f'<div class="modal-body"><p class="mb-0">{text}</p></div>'
        f'<div class="modal-footer"><button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">{secondary}</button>'
        f'<button type="button" class="btn btn-{button_variant}" data-bs-dismiss="modal">{primary}</button></div>'
        "</div></div></div></div>"
    )


def _render_bs_toast(block: dict[str, Any]) -> str:
    title = _safe_text(block.get("title")) or "Notification"
    text = _safe_text(block.get("text"))
    if not text:
        return ""
    delay = int(block.get("delay") or 5000)
    delay = 1000 if delay < 1000 else 20000 if delay > 20000 else delay
    autohide = "true" if bool(block.get("autohide", True)) else "false"
    variant = _safe_variant(block.get("variant"), default="primary")
    toast_id = f"toast-{uuid4().hex[:8]}"

    return (
        f'<div class="block-bs-toast toast align-items-center border-0 text-bg-{variant}" id="{toast_id}" role="alert" '
        f'aria-live="assertive" aria-atomic="true" data-bs-autohide="{autohide}" data-bs-delay="{delay}">'
        f'<div class="d-flex"><div class="toast-body"><strong class="d-block">{title}</strong>{text}</div>'
        '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>'
        "</div></div>"
        '<script>document.addEventListener("DOMContentLoaded",function(){try{var el=document.getElementById("'
        f'{toast_id}'
        '");if(el&&window.bootstrap&&window.bootstrap.Toast){new window.bootstrap.Toast(el).show();}}catch(e){}});</script>'
    )


def _render_bs_offcanvas(block: dict[str, Any]) -> str:
    button_text = _safe_text(block.get("button_text")) or "Open panel"
    title = _safe_text(block.get("title")) or "Panel"
    text = _safe_text(block.get("text"))
    if not text:
        return ""
    button_variant = _safe_variant(block.get("button_variant"), default="primary")
    placement = str(block.get("placement") or "end").strip().lower()
    if placement not in {"start", "end", "top", "bottom"}:
        placement = "end"
    panel_id = f"offcanvas-{uuid4().hex[:8]}"
    return (
        f'<div class="block-bs-offcanvas"><button class="btn btn-{button_variant}" type="button" data-bs-toggle="offcanvas" '
        f'data-bs-target="#{panel_id}" aria-controls="{panel_id}">{button_text}</button>'
        f'<div class="offcanvas offcanvas-{placement}" tabindex="-1" id="{panel_id}" aria-labelledby="{panel_id}-label">'
        f'<div class="offcanvas-header"><h5 class="offcanvas-title" id="{panel_id}-label">{title}</h5>'
        '<button type="button" class="btn-close text-reset" data-bs-dismiss="offcanvas" aria-label="Close"></button></div>'
        f'<div class="offcanvas-body"><p class="mb-0">{text}</p></div></div></div>'
    )


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
        parts.append(f'<h3 class="mb-2">{section_title}</h3>')
    if section_subtitle:
        parts.append(f'<p class="text-muted mb-3">{section_subtitle}</p>')
    parts.append('<div class="row g-3">')
    for plan in normalized:
        card_cls = "card h-100 shadow-sm"
        if plan["recommended"]:
            card_cls += " border-primary"
        parts.append('<div class="col-12 col-md-6 col-xl-4">')
        parts.append(f'<article class="{card_cls}"><div class="card-body d-flex flex-column">')
        if plan["recommended"]:
            parts.append('<span class="badge text-bg-primary mb-2 align-self-start">Popular</span>')
        if plan["title"]:
            parts.append(f'<h4 class="h5 card-title">{plan["title"]}</h4>')
        if plan["price"]:
            parts.append(f'<p class="display-6 fw-bold mb-1">{plan["price"]}</p>')
        if plan["period"]:
            parts.append(f'<p class="text-muted mb-3">{plan["period"]}</p>')
        if plan["features"]:
            parts.append('<ul class="list-unstyled small mb-4">')
            for feature in plan["features"]:
                parts.append(f'<li class="mb-2">• {feature}</li>')
            parts.append("</ul>")
        btn_url = plan["button_url"]
        btn_variant = "primary" if plan["recommended"] else "outline-primary"
        parts.append(
            f'<a class="btn btn-{btn_variant} mt-auto" href="{btn_url if btn_url and btn_url != "#" else "#"}">{plan["button_label"]}</a>'
        )
        parts.append("</div></article></div>")
    parts.append("</div></section>")
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
    button_label = _safe_text(block.get("button_label")) or "Open menu"
    button_variant = _safe_variant(block.get("button_variant"), default="primary")
    align = str(block.get("align") or "start").strip().lower()
    align_cls = " dropdown-menu-end" if align == "end" else ""
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
        menu_items.append(f'<li><a class="dropdown-item" href="{href}">{label}</a></li>')
    if not menu_items:
        return ""
    dd_id = f"dd-{uuid4().hex[:8]}"
    return (
        f'<div class="dropdown">'
        f'<button class="btn btn-{button_variant} dropdown-toggle" type="button" id="{dd_id}" '
        f'data-bs-toggle="dropdown" aria-expanded="false">{button_label}</button>'
        f'<ul class="dropdown-menu{align_cls}" aria-labelledby="{dd_id}">{"".join(menu_items)}</ul>'
        f"</div>"
    )


def _render_bs_navbar(block: dict[str, Any]) -> str:
    brand = _safe_text(block.get("brand")) or "VXcloud"
    expand = str(block.get("expand") or "lg").strip().lower()
    variant = str(block.get("variant") or "dark").strip().lower()
    bg = str(block.get("bg") or "dark").strip().lower()
    items = block.get("items")
    if not isinstance(items, list):
        items = []
    nav_id = f"nav-{uuid4().hex[:8]}"
    nav_items: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = _safe_text(item.get("label"))
        href = _safe_url(item.get("url"))
        active = " active" if bool(item.get("active")) else ""
        if not label:
            continue
        nav_items.append(f'<li class="nav-item"><a class="nav-link{active}" href="{href}">{label}</a></li>')
    return (
        f'<nav class="navbar navbar-expand-{expand} navbar-{variant} bg-{bg} rounded-3 mb-3">'
        f'<div class="container-fluid">'
        f'<a class="navbar-brand" href="#">{brand}</a>'
        f'<button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#{nav_id}" '
        f'aria-controls="{nav_id}" aria-expanded="false" aria-label="Toggle navigation"><span class="navbar-toggler-icon"></span></button>'
        f'<div class="collapse navbar-collapse" id="{nav_id}">'
        f'<ul class="navbar-nav me-auto mb-2 mb-lg-0">{"".join(nav_items)}</ul>'
        f"</div></div></nav>"
    )


def _render_bs_ratio(block: dict[str, Any]) -> str:
    ratio = str(block.get("ratio") or "16x9").strip().lower()
    allowed = {"1x1", "4x3", "16x9", "21x9"}
    ratio = ratio if ratio in allowed else "16x9"
    src = _safe_url(block.get("url"))
    if not src or src == "#":
        return ""
    return (
        f'<div class="ratio ratio-{ratio}">'
        f'<iframe src="{src}" title="Embedded media" allowfullscreen loading="lazy"></iframe>'
        f"</div>"
    )


def _render_bs_placeholder(block: dict[str, Any]) -> str:
    lines = int(block.get("lines") or 3)
    lines = 1 if lines < 1 else 8 if lines > 8 else lines
    width = int(block.get("width") or 100)
    width = 10 if width < 10 else 100 if width > 100 else width
    parts = ['<div class="placeholder-glow">']
    for _ in range(lines):
        parts.append(f'<span class="placeholder col-{max(1, min(12, round(width / 8.33)))}"></span>')
    parts.append("</div>")
    return "".join(parts)


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
            css = "btn btn-primary" if style != "secondary" else "btn btn-secondary"
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
