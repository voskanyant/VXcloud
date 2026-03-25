#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Config:
    base_url: str
    token: str
    buttons_collection: str
    content_collection: str


def parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    # utf-8-sig tolerates accidental BOM from editors/Windows tooling.
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def load_json_rows(path: Path, required_fields: tuple[str, ...]) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Seed file not found: {path}")
    # utf-8-sig tolerates accidental BOM in seed files.
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError(f"Seed file must be a JSON array: {path}")

    rows: list[dict[str, str]] = []
    seen_keys: set[str] = set()
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Row #{idx} in {path} is not an object")
        row: dict[str, str] = {}
        for field in required_fields:
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Row #{idx} in {path} has invalid '{field}'")
            row[field] = value.strip()
        key = row["key"]
        if key in seen_keys:
            raise ValueError(f"Duplicate key '{key}' in {path}")
        seen_keys.add(key)
        rows.append(row)
    return rows


def http_json(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body: bytes | None = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, method=method, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {method} {url}: {detail}") from exc

    if not raw:
        return {}
    return json.loads(raw)


def fetch_existing(base_url: str, token: str, collection: str, fields: str) -> dict[str, dict[str, Any]]:
    query = urllib.parse.urlencode({"fields": fields, "limit": "-1"})
    url = f"{base_url}/items/{collection}?{query}"
    data = http_json("GET", url, token)
    rows = data.get("data")
    if not isinstance(rows, list):
        raise RuntimeError(f"Unexpected response for {collection}: {data}")

    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = row.get("key")
        if isinstance(key, str) and key.strip():
            out[key.strip()] = row
    return out


def upsert_rows(
    cfg: Config,
    collection: str,
    desired_rows: list[dict[str, str]],
    value_field: str,
    dry_run: bool,
) -> tuple[int, int, int]:
    existing = fetch_existing(cfg.base_url, cfg.token, collection, f"id,key,{value_field}")
    created = 0
    updated = 0
    unchanged = 0

    for row in desired_rows:
        key = row["key"]
        value = row[value_field]
        current = existing.get(key)
        if current is None:
            created += 1
            if not dry_run:
                http_json(
                    "POST",
                    f"{cfg.base_url}/items/{collection}",
                    cfg.token,
                    payload={"key": key, value_field: value},
                )
            continue

        current_value = current.get(value_field)
        if isinstance(current_value, str) and current_value == value:
            unchanged += 1
            continue

        updated += 1
        if not dry_run:
            row_id = current.get("id")
            if row_id is None:
                raise RuntimeError(f"Missing id for existing key '{key}' in {collection}")
            http_json(
                "PATCH",
                f"{cfg.base_url}/items/{collection}/{row_id}",
                cfg.token,
                payload={value_field: value},
            )

    return created, updated, unchanged


def prune_rows(
    cfg: Config,
    collection: str,
    desired_keys: set[str],
    value_field: str,
    should_prune_key: callable,
    dry_run: bool,
) -> int:
    existing = fetch_existing(cfg.base_url, cfg.token, collection, f"id,key,{value_field}")
    deleted = 0
    for key, row in existing.items():
        if key in desired_keys:
            continue
        if not should_prune_key(key):
            continue
        deleted += 1
        if not dry_run:
            row_id = row.get("id")
            if row_id is None:
                raise RuntimeError(f"Missing id for existing key '{key}' in {collection}")
            http_json("DELETE", f"{cfg.base_url}/items/{collection}/{row_id}", cfg.token)
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Directus content from repo seed files")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--buttons-file", default="directus_seed/bot_buttons.json")
    parser.add_argument("--content-file", default="directus_seed/bot_content.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env = dict(os.environ)
    env.update(parse_env_file(Path(args.env_file)))

    base_url = env.get("CMS_BASE_URL", "").strip().rstrip("/")
    token = env.get("CMS_TOKEN", "").strip()
    buttons_collection = env.get("CMS_BUTTON_COLLECTION", "bot_buttons").strip()
    content_collection = env.get("CMS_CONTENT_COLLECTION", "bot_content").strip()

    if not base_url or not token:
        print("CMS_BASE_URL or CMS_TOKEN is missing; skipping Directus sync.")
        return 0

    cfg = Config(
        base_url=base_url,
        token=token,
        buttons_collection=buttons_collection,
        content_collection=content_collection,
    )

    buttons_rows = load_json_rows(Path(args.buttons_file), ("key", "label"))
    content_rows = load_json_rows(Path(args.content_file), ("key", "value"))

    b_created, b_updated, b_unchanged = upsert_rows(
        cfg,
        cfg.buttons_collection,
        buttons_rows,
        value_field="label",
        dry_run=args.dry_run,
    )
    c_created, c_updated, c_unchanged = upsert_rows(
        cfg,
        cfg.content_collection,
        content_rows,
        value_field="value",
        dry_run=args.dry_run,
    )
    b_deleted = prune_rows(
        cfg,
        cfg.buttons_collection,
        desired_keys={r["key"] for r in buttons_rows},
        value_field="label",
        should_prune_key=lambda k: k.startswith("menu_"),
        dry_run=args.dry_run,
    )
    c_deleted = prune_rows(
        cfg,
        cfg.content_collection,
        desired_keys={r["key"] for r in content_rows},
        value_field="value",
        should_prune_key=lambda k: k.endswith("_response") or k.endswith("_buttons"),
        dry_run=args.dry_run,
    )

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(
        f"[{mode}] buttons: created={b_created}, updated={b_updated}, unchanged={b_unchanged}; "
        f"content: created={c_created}, updated={c_updated}, unchanged={c_unchanged}; "
        f"deleted: buttons={b_deleted}, content={c_deleted}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Directus sync failed: {exc}", file=sys.stderr)
        raise
