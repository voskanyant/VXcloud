#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/srv/apps/vxcloud/app"
cd "$APP_DIR"

wait_for_http() {
  local url="$1"
  local max_attempts="${2:-45}"
  local sleep_seconds="${3:-2}"
  local code=""
  local attempt=1

  while [[ "$attempt" -le "$max_attempts" ]]; do
    code="$(curl -sS -o /dev/null -w "%{http_code}" "$url" || true)"
    if [[ -n "$code" && "$code" != "000" && "$code" -lt 500 ]]; then
      echo "healthcheck OK for $url (HTTP=$code)"
      return 0
    fi
    sleep "$sleep_seconds"
    attempt=$((attempt + 1))
  done

  echo "ERROR: healthcheck failed for $url, HTTP=${code:-000}"
  return 1
}

port_in_use() {
  ss -lntH "( sport = :8088 )" | grep -q .
}

show_port_occupant() {
  echo "---- ss (8088) ----"
  ss -lntp "( sport = :8088 )" || true
  echo "---- docker publish 8088 ----"
  docker ps --format 'table {{.Names}}\t{{.Ports}}' | grep '127.0.0.1:8088->' || true
}

stop_legacy_systemd_unit() {
  if ! systemctl list-unit-files | grep -q '^vxcloud-web\.service'; then
    return 0
  fi

  echo "Stopping legacy systemd unit vxcloud-web.service..."
  if systemctl stop vxcloud-web.service 2>/dev/null; then
    return 0
  fi
  if sudo -n systemctl stop vxcloud-web.service 2>/dev/null; then
    return 0
  fi
  echo "Could not stop vxcloud-web.service via systemctl (no non-interactive privileges)."
}

kill_any_on_8088() {
  local pids pid
  pids="$(ss -lntp "( sport = :8088 )" 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)"
  [[ -z "$pids" ]] && return 0

  for pid in $pids; do
    echo "Stopping listener on 8088: pid=$pid"
    kill -TERM "$pid" 2>/dev/null || true
  done

  sleep 1
  pids="$(ss -lntp "( sport = :8088 )" 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)"
  for pid in $pids; do
    kill -KILL "$pid" 2>/dev/null || true
  done
}

cleanup_legacy_bindings() {
  stop_legacy_systemd_unit
  kill_any_on_8088
  docker compose --env-file .env down --remove-orphans || true
}

ensure_frontdoor_port_available() {
  if port_in_use; then
    echo "Port 8088 is busy before deploy, trying cleanup..."
    cleanup_legacy_bindings
  fi

  if port_in_use; then
    echo "Port 8088 is still in use after cleanup."
    show_port_occupant
  fi
}

start_proxy_with_port_takeover() {
  local max_attempts=6
  local attempt=1

  while [[ "$attempt" -le "$max_attempts" ]]; do
    echo "Starting proxy container (attempt $attempt/$max_attempts)..."
    kill_any_on_8088

    if docker compose --env-file .env up -d proxy; then
      echo "vxcloud-proxy started."
      return 0
    fi

    echo "proxy start failed on attempt $attempt; retrying..."
    docker compose --env-file .env rm -fsv proxy >/dev/null 2>&1 || true
    show_port_occupant
    sleep 1
    attempt=$((attempt + 1))
  done

  echo "ERROR: failed to start vxcloud-proxy after $max_attempts attempts."
  return 1
}

echo "[1/11] Fetch latest..."
git fetch origin main

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse origin/main)"
echo "LOCAL=$LOCAL"
echo "REMOTE=$REMOTE"

echo "[2/11] Auto-stash local/untracked changes (if any)..."
git stash push -u -m "auto-stash-before-deploy-$(date +%F_%H%M%S)" >/dev/null || true

echo "[3/11] Fast-forward pull..."
git pull --ff-only origin main

echo "[4/11] Preflight checks..."
ensure_frontdoor_port_available

echo "[5/11] Build custom images..."
docker compose --env-file .env build web bot

echo "[6/11] Start data services..."
docker compose --env-file .env up -d db wpdb

echo "[7/11] Start app services..."
docker compose --env-file .env up -d wordpress web
start_proxy_with_port_takeover
docker compose --env-file .env --profile bot up -d bot

echo "[8/11] Apply Django migrations + static..."
docker compose --env-file .env exec -T web python /app/web/manage.py migrate --noinput
docker compose --env-file .env exec -T web python /app/web/manage.py collectstatic --noinput

echo "[9/11] Check migration drift (makemigrations --check)..."
if ! docker compose --env-file .env exec -T web python /app/web/manage.py makemigrations --check --dry-run; then
  echo "ERROR: model changes detected without migration files."
  echo "Create and commit migrations first (manage.py makemigrations), then redeploy."
  exit 1
fi

echo "[10/11] Health checks..."
wait_for_http "http://127.0.0.1:8088/"
wait_for_http "http://127.0.0.1:8088/account/"
docker compose --env-file .env ps

echo "[11/11] Done."
echo "If needed, stashes are here:"
git stash list | head -n 3 || true
