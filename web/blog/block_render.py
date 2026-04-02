from __future__ import annotations

from html import escape
from typing import Any

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
    parts.append("</div></section>")
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


def render_content_blocks(blocks: Any, legacy_html: str = ""):
    if not isinstance(blocks, list) or not blocks:
        return mark_safe(legacy_html or "")

    output: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "").strip().lower()

        if block_type == "paragraph":
            text = _safe_text(block.get("text"))
            if text:
                output.append(f"<p>{text}</p>")
        elif block_type == "heading":
            text = _safe_text(block.get("text"))
            level = int(block.get("level") or 2)
            level = 2 if level < 1 or level > 6 else level
            if text:
                output.append(f"<h{level}>{text}</h{level}>")
        elif block_type == "list":
            items = [str(x).strip() for x in (block.get("items") or []) if str(x).strip()]
            ordered = bool(block.get("ordered"))
            if items:
                tag = "ol" if ordered else "ul"
                rendered = "".join(f"<li>{_safe_text(item)}</li>" for item in items)
                output.append(f"<{tag}>{rendered}</{tag}>")
        elif block_type == "quote":
            text = _safe_text(block.get("text"))
            cite = _safe_text(block.get("cite"))
            if text:
                if cite:
                    output.append(f"<blockquote><p>{text}</p><cite>{cite}</cite></blockquote>")
                else:
                    output.append(f"<blockquote><p>{text}</p></blockquote>")
        elif block_type == "image":
            src = _safe_url(block.get("src"))
            alt = _safe_text(block.get("alt"))
            caption = _safe_text(block.get("caption"))
            if src and src != "#":
                figure = [f'<figure class="block-image"><img src="{src}" alt="{alt}" loading="lazy" />']
                if caption:
                    figure.append(f"<figcaption>{caption}</figcaption>")
                figure.append("</figure>")
                output.append("".join(figure))
        elif block_type == "embed":
            url = _safe_url(block.get("url"))
            if url and url != "#":
                output.append(
                    '<div class="block-embed">'
                    f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'
                    "</div>"
                )
        elif block_type == "button":
            label = _safe_text(block.get("label"))
            href = _safe_url(block.get("url"))
            style = str(block.get("style") or "primary").strip().lower()
            css = "btn btn-primary" if style != "secondary" else "btn btn-secondary"
            if label:
                output.append(f'<div class="block-buttons"><a class="{css}" href="{href}">{label}</a></div>')
        elif block_type == "buttons":
            items = block.get("items") or []
            if isinstance(items, list):
                output.append(_render_buttons(items))
        elif block_type == "spacer":
            px = int(block.get("height") or 24)
            px = 16 if px < 8 else min(px, 180)
            output.append(f'<div class="block-spacer" style="height:{px}px"></div>')
        elif block_type == "faq":
            q = _safe_text(block.get("question"))
            a = _safe_text(block.get("answer"))
            if q:
                output.append(f'<details class="block-faq"><summary>{q}</summary><p>{a}</p></details>')
        elif block_type == "columns":
            left = _safe_text(block.get("left"))
            right = _safe_text(block.get("right"))
            output.append(
                '<div class="block-columns">'
                f'<div class="block-column"><p>{left}</p></div>'
                f'<div class="block-column"><p>{right}</p></div>'
                "</div>"
            )
        elif block_type == "html":
            custom = str(block.get("html") or "").strip()
            if custom:
                output.append(custom)
        elif block_type in {"cards_slider", "cards-slider", "cards slider", "cs_cards_slider"}:
            rendered = _render_cards_slider(block)
            if rendered:
                output.append(rendered)

    if not output:
        return mark_safe(legacy_html or "")
    return mark_safe("".join(output))
