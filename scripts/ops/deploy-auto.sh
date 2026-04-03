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
      echo "web healthcheck OK (HTTP=$code)"
      return 0
    fi
    sleep "$sleep_seconds"
    attempt=$((attempt + 1))
  done

  echo "ERROR: web healthcheck failed, HTTP=${code:-000}"
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
  # 1) try direct stop (works if current user is privileged)
  if systemctl stop vxcloud-web.service 2>/dev/null; then
    return 0
  fi
  # 2) try non-interactive sudo (works if NOPASSWD is configured)
  if sudo -n systemctl stop vxcloud-web.service 2>/dev/null; then
    return 0
  fi
  echo "Could not stop vxcloud-web.service via systemctl (no non-interactive privileges)."
}

kill_gunicorn_on_8088() {
  local pids pid cmdline killed_any=0
  pids="$(ss -lntp "( sport = :8088 )" 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)"
  [[ -z "$pids" ]] && return 0

  for pid in $pids; do
    cmdline="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    if [[ "$cmdline" == *gunicorn* ]]; then
      echo "Stopping process on 8088: pid=$pid ($cmdline)"
      kill -TERM "$pid" 2>/dev/null || true
      killed_any=1
    fi
  done

  if [[ "$killed_any" -eq 1 ]]; then
    sleep 2
    # Force-kill remaining gunicorn listeners on the port if needed.
    pids="$(ss -lntp "( sport = :8088 )" 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)"
    for pid in $pids; do
      cmdline="$(ps -p "$pid" -o args= 2>/dev/null || true)"
      if [[ "$cmdline" == *gunicorn* ]]; then
        kill -KILL "$pid" 2>/dev/null || true
      fi
    done
  fi
}

cleanup_legacy_bindings() {
  # Older installs used a host systemd service on the same port.
  stop_legacy_systemd_unit
  kill_gunicorn_on_8088

  # Stop previous compose containers from this project and remove orphans.
  docker compose --env-file .env down --remove-orphans || true
}

ensure_web_port_available() {
  if port_in_use; then
    echo "Port 8088 is busy before deploy, trying cleanup..."
    cleanup_legacy_bindings
  fi

  if port_in_use; then
    echo "ERROR: 127.0.0.1:8088 is still in use. Cannot start vxcloud-web."
    show_port_occupant
    return 1
  fi

  return 0
}

echo "[1/9] Fetch latest..."
git fetch origin main

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse origin/main)"
echo "LOCAL=$LOCAL"
echo "REMOTE=$REMOTE"

echo "[2/9] Auto-stash local/untracked changes (if any)..."
git stash push -u -m "auto-stash-before-deploy-$(date +%F_%H%M%S)" >/dev/null || true

echo "[3/9] Fast-forward pull..."
git pull --ff-only origin main

echo "[4/9] Preflight checks..."
ensure_web_port_available

echo "[5/9] Rebuild/start containers..."
docker compose --env-file .env up -d --build db web
docker compose --env-file .env --profile bot up -d --build bot

echo "[6/9] Apply Django migrations + static..."
docker compose --env-file .env exec -T web python /app/web/manage.py migrate --noinput
docker compose --env-file .env exec -T web python /app/web/manage.py collectstatic --noinput

echo "[7/9] Check migration drift (makemigrations --check)..."
if ! docker compose --env-file .env exec -T web python /app/web/manage.py makemigrations --check --dry-run; then
  echo "ERROR: model changes detected without migration files."
  echo "Create and commit migrations first (manage.py makemigrations), then redeploy."
  exit 1
fi

echo "[8/9] Health checks..."
wait_for_http "http://127.0.0.1:8088/"
docker compose --env-file .env ps

echo "[9/9] Done."
echo "If needed, stashes are here:"
git stash list | head -n 3 || true
