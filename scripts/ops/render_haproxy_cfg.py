#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import os
import re
import subprocess
import sys
from pathlib import Path
from string import Template
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


DEFAULT_TEMPLATE_PATH = "ops/haproxy/haproxy.cfg.tpl"
DEFAULT_OUTPUT_PATH = "/etc/haproxy/haproxy.cfg"


def _env_int(name: str, fallback: int) -> int:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return fallback
    return int(raw)


def _env_bool(name: str, fallback: bool = False) -> bool:
    raw = (os.getenv(name, "1" if fallback else "0") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _clean_server_name(node_id: int, raw_name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", (raw_name or "").strip().lower()).strip("-_")
    if not slug:
        slug = "node"
    slug = slug[:40]
    return f"node_{node_id}_{slug}"


def _load_healthy_lb_nodes(database_url: str) -> list[dict[str, Any]]:
    query = """
    SELECT
        id,
        name,
        backend_host,
        backend_port,
        COALESCE(backend_weight, 100) AS backend_weight,
        last_reality_public_key,
        last_reality_short_id,
        last_reality_sni,
        last_reality_fingerprint
    FROM vpn_nodes
    WHERE lb_enabled = TRUE
      AND is_active = TRUE
      AND COALESCE(needs_backfill, FALSE) = FALSE
      AND COALESCE(last_health_ok, FALSE) = TRUE
    ORDER BY id
    """
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def _reality_signature(node: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(node.get("last_reality_public_key") or "").strip(),
        str(node.get("last_reality_short_id") or "").strip(),
        str(node.get("last_reality_sni") or "").strip(),
        str(node.get("last_reality_fingerprint") or "").strip(),
    )


def _filter_nodes_with_matching_reality(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not nodes:
        return []
    signatures = [_reality_signature(node) for node in nodes]
    non_empty = [signature for signature in signatures if any(signature)]
    if not non_empty:
        return nodes
    baseline, _ = Counter(non_empty).most_common(1)[0]
    return [node for node in nodes if _reality_signature(node) == baseline]


def _render_backend_servers(nodes: list[dict[str, Any]], *, send_proxy: bool = False) -> str:
    lines: list[str] = []
    server_suffix = " send-proxy check-send-proxy" if send_proxy else ""
    for node in nodes:
        node_id = int(node["id"])
        server_name = _clean_server_name(node_id, str(node.get("name") or "node"))
        backend_host = str(node["backend_host"]).strip()
        backend_port = int(node["backend_port"])
        backend_weight = max(1, int(node.get("backend_weight") or 100))
        lines.append(
            f"  server {server_name} {backend_host}:{backend_port} check weight {backend_weight}{server_suffix}"
        )

    if not lines:
        lines.append("  # No lb_enabled + healthy nodes found.")
        lines.append("  # Keep backend valid, but do not route traffic to unavailable backends.")
        lines.append("  server cluster_empty 127.0.0.1:65535 disabled")

    return "\n".join(lines)


def _render_config(
    *,
    template_path: Path,
    frontend_bind_addr: str,
    frontend_port: int,
    backend_servers: str,
) -> str:
    template_text = template_path.read_text(encoding="utf-8")
    return Template(template_text).safe_substitute(
        FRONTEND_BIND_ADDR=frontend_bind_addr,
        FRONTEND_PORT=str(frontend_port),
        BACKEND_SERVERS=backend_servers,
    )


def _validate_config(haproxy_bin: str, cfg_path: Path) -> None:
    result = subprocess.run(
        [haproxy_bin, "-c", "-f", str(cfg_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"HAProxy config validation failed ({result.returncode}).\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def _reload_haproxy(reload_cmd: str) -> None:
    result = subprocess.run(reload_cmd, shell=True, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"HAProxy reload command failed ({result.returncode}).\n"
            f"command: {reload_cmd}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render HAProxy TCP config from vpn_nodes table")
    parser.add_argument("--env-file", default=".env", help="Path to env file (default: .env)")
    parser.add_argument("--template-path", default=None, help="Path to haproxy template file")
    parser.add_argument("--output-path", default=None, help="Where to write rendered haproxy.cfg")
    parser.add_argument("--frontend-bind-addr", default=None, help="Frontend bind address")
    parser.add_argument("--frontend-port", type=int, default=None, help="Frontend bind port")
    parser.add_argument("--reload-cmd", default=None, help="Command to reload haproxy")
    parser.add_argument("--haproxy-bin", default=None, help="HAProxy binary path/name used for validation")
    parser.add_argument("--dry-run", action="store_true", help="Print config to stdout, skip write/validate/reload")
    parser.add_argument("--skip-validate", action="store_true", help="Skip `haproxy -c -f ...` validation")
    parser.add_argument("--skip-reload", action="store_true", help="Skip reload command")
    args = parser.parse_args()

    load_dotenv(args.env_file)

    database_url = (os.getenv("DATABASE_URL", "") or "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required (env or .env)")

    template_path = Path(
        args.template_path or os.getenv("HAPROXY_TEMPLATE_PATH", DEFAULT_TEMPLATE_PATH)
    ).expanduser()
    output_path = Path(
        args.output_path or os.getenv("HAPROXY_OUTPUT_PATH", DEFAULT_OUTPUT_PATH)
    ).expanduser()
    frontend_bind_addr = (args.frontend_bind_addr or os.getenv("HAPROXY_FRONTEND_BIND_ADDR", "0.0.0.0")).strip()
    frontend_port = args.frontend_port or _env_int(
        "HAPROXY_FRONTEND_PORT",
        _env_int("VPN_PUBLIC_PORT", 29940),
    )
    reload_cmd = (args.reload_cmd if args.reload_cmd is not None else os.getenv("HAPROXY_RELOAD_CMD", "")).strip()
    haproxy_bin = (args.haproxy_bin or os.getenv("HAPROXY_BIN", "haproxy")).strip()

    if not template_path.exists():
        raise RuntimeError(f"Template file does not exist: {template_path}")

    nodes = _load_healthy_lb_nodes(database_url)
    nodes = _filter_nodes_with_matching_reality(nodes)
    backend_servers = _render_backend_servers(
        nodes,
        send_proxy=_env_bool("HAPROXY_BACKEND_SEND_PROXY", False),
    )
    rendered = _render_config(
        template_path=template_path,
        frontend_bind_addr=frontend_bind_addr,
        frontend_port=frontend_port,
        backend_servers=backend_servers,
    )

    if args.dry_run:
        print(rendered)
        print(f"\n# Nodes in pool: {len(nodes)}", file=sys.stderr)
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    print(f"Rendered HAProxy config: {output_path} (nodes={len(nodes)})")

    if not args.skip_validate:
        _validate_config(haproxy_bin, output_path)
        print("HAProxy config validation: OK")

    if reload_cmd and not args.skip_reload:
        _reload_haproxy(reload_cmd)
        print("HAProxy reloaded successfully")
    elif not reload_cmd:
        print("HAPROXY_RELOAD_CMD is empty: skipped reload")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"render_haproxy_cfg failed: {exc}", file=sys.stderr)
        raise
