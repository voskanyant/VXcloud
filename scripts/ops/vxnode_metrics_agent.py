#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


TOKEN = os.getenv("VXNODE_METRICS_TOKEN", "").strip()
BIND_HOST = os.getenv("VXNODE_METRICS_BIND", "0.0.0.0").strip() or "0.0.0.0"
PORT = int(os.getenv("VXNODE_METRICS_PORT", "9109"))
ROOT_PATH = os.getenv("VXNODE_METRICS_DISK_PATH", "/")
INTERFACE_PREFIXES = tuple(
    item.strip() for item in os.getenv("VXNODE_METRICS_INTERFACE_PREFIXES", "e,eth,en").split(",") if item.strip()
)


def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _parse_meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    for line in _read_text("/proc/meminfo").splitlines():
        key, _, rest = line.partition(":")
        amount = rest.strip().split()[0]
        try:
            values[key] = int(amount) * 1024
        except (IndexError, ValueError):
            continue
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    swap_total = values.get("SwapTotal", 0)
    swap_free = values.get("SwapFree", 0)
    return {
        "memory_total": total,
        "memory_used": max(total - available, 0),
        "swap_total": swap_total,
        "swap_used": max(swap_total - swap_free, 0),
    }


def _cpu_jiffies() -> tuple[int, int]:
    first = _read_text("/proc/stat").splitlines()[0].split()
    values = [int(value) for value in first[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    return total, idle


def _cpu_percent() -> float:
    total_a, idle_a = _cpu_jiffies()
    time.sleep(0.12)
    total_b, idle_b = _cpu_jiffies()
    total_delta = max(total_b - total_a, 1)
    idle_delta = max(idle_b - idle_a, 0)
    return round(max(0.0, min(100.0, (1.0 - idle_delta / total_delta) * 100.0)), 2)


def _load() -> dict[str, float]:
    load1, load5, load15 = os.getloadavg()
    return {"load1": round(load1, 4), "load5": round(load5, 4), "load15": round(load15, 4)}


def _disk() -> dict[str, int]:
    usage = shutil.disk_usage(ROOT_PATH)
    return {"total_bytes": usage.total, "used_bytes": usage.used, "free_bytes": usage.free}


def _network() -> dict[str, int]:
    rx = 0
    tx = 0
    for line in _read_text("/proc/net/dev").splitlines()[2:]:
        name, _, rest = line.partition(":")
        interface = name.strip()
        if INTERFACE_PREFIXES and not interface.startswith(INTERFACE_PREFIXES):
            continue
        parts = rest.split()
        if len(parts) < 16:
            continue
        try:
            rx += int(parts[0])
            tx += int(parts[8])
        except ValueError:
            continue
    return {"rx_bytes": rx, "tx_bytes": tx}


def _count_socket_rows(path: str) -> int:
    try:
        lines = _read_text(path).splitlines()
    except OSError:
        return 0
    return max(len(lines) - 1, 0)


def _uptime_seconds() -> int:
    try:
        return int(float(_read_text("/proc/uptime").split()[0]))
    except (IndexError, ValueError, OSError):
        return 0


def collect() -> dict[str, object]:
    mem = _parse_meminfo()
    return {
        "source": "vxnode-agent",
        "hostname": socket.gethostname(),
        "observed_at": int(time.time()),
        "cpu_percent": _cpu_percent(),
        "load": _load(),
        "memory": {"used_bytes": mem["memory_used"], "total_bytes": mem["memory_total"]},
        "swap": {"used_bytes": mem["swap_used"], "total_bytes": mem["swap_total"]},
        "disk": _disk(),
        "network": _network(),
        "sockets": {
            "tcp_connections": _count_socket_rows("/proc/net/tcp") + _count_socket_rows("/proc/net/tcp6"),
            "udp_sockets": _count_socket_rows("/proc/net/udp") + _count_socket_rows("/proc/net/udp6"),
        },
        "uptime_seconds": _uptime_seconds(),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "VXNodeMetrics/1.0"

    def _authorized(self) -> bool:
        if not TOKEN:
            return True
        header = self.headers.get("Authorization", "")
        if header == f"Bearer {TOKEN}":
            return True
        query_token = parse_qs(urlparse(self.path).query).get("token", [""])[0]
        return query_token == TOKEN

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/", "/metrics", "/health"}:
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        if not self._authorized():
            self._send_json(401, {"ok": False, "error": "unauthorized"})
            return
        if path == "/health":
            self._send_json(200, {"ok": True})
            return
        self._send_json(200, collect())

    def log_message(self, fmt: str, *args: object) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer((BIND_HOST, PORT), Handler)
    print(f"vxnode metrics agent listening on {BIND_HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
