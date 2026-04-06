from __future__ import annotations

import re
import unicodedata


def _ascii_slug(value: str | None, *, fallback: str = "") -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").strip())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return slug or fallback


def build_xui_client_name(
    *,
    user_id: int,
    client_uuid: str,
    username: str | None = None,
    first_name: str | None = None,
    client_code: str | None = None,
    prefix: str = "",
) -> str:
    readable_name = (
        _ascii_slug(username)
        or _ascii_slug(first_name)
        or f"user-{int(user_id)}"
    )
    normalized_code = _ascii_slug(client_code, fallback=f"u-{int(user_id)}")
    normalized_prefix = _ascii_slug(prefix)
    config_suffix = re.sub(r"[^a-z0-9]+", "", str(client_uuid).lower())[:8] or str(int(user_id))

    parts: list[str] = []
    if normalized_prefix:
        parts.append(normalized_prefix)
    parts.extend([readable_name, normalized_code, f"cfg-{config_suffix}"])

    return "_".join(parts)[:64]
