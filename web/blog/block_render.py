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

    if not output:
        return mark_safe(legacy_html or "")
    return mark_safe("".join(output))

