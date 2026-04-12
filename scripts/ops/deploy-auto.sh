#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/srv/apps/vxcloud/app"
cd "$APP_DIR"

if [[ ! -f .env && -f /srv/secrets/vxcloud.env ]]; then
  cp /srv/secrets/vxcloud.env .env
  chmod 600 .env
fi

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

run_in_web_with_retry() {
  local max_attempts="${1:-15}"
  local sleep_seconds="${2:-2}"
  shift 2
  local attempt=1

  while [[ "$attempt" -le "$max_attempts" ]]; do
    if docker compose --env-file .env exec -T web "$@"; then
      return 0
    fi
    sleep "$sleep_seconds"
    attempt=$((attempt + 1))
  done

  echo "ERROR: failed to run command in web container after $max_attempts attempts: $*"
  return 1
}

set_env_value() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" .env 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}

haproxy_frontend_port() {
  local port
  port="$(grep -E '^HAPROXY_FRONTEND_PORT=' .env 2>/dev/null | tail -n 1 | cut -d= -f2- || true)"
  if [[ -z "$port" ]]; then
    port="$(grep -E '^VPN_PUBLIC_PORT=' .env 2>/dev/null | tail -n 1 | cut -d= -f2- || true)"
  fi
  if [[ -z "$port" ]]; then
    port="29940"
  fi
  printf '%s' "$port"
}

port_in_use() {
  ss -lntH "( sport = :8088 )" | grep -q .
}

port_in_use_exact() {
  local port="$1"
  ss -lntH "( sport = :${port} )" | grep -q .
}

show_port_occupant() {
  echo "---- ss (8088) ----"
  ss -lntp "( sport = :8088 )" || true
  echo "---- docker publish 8088 ----"
  docker ps --format 'table {{.Names}}\t{{.Ports}}' | grep '127.0.0.1:8088->' || true
}

show_port_occupant_exact() {
  local port="$1"
  echo "---- ss (${port}) ----"
  ss -lntp "( sport = :${port} )" || true
  echo "---- docker publish ${port} ----"
  docker ps --format 'table {{.Names}}\t{{.Ports}}' | grep ":${port}->" || true
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

ensure_haproxy_frontend_port_available() {
  local port
  port="$(haproxy_frontend_port)"

  if ! port_in_use_exact "$port"; then
    return 0
  fi

  echo "HAProxy frontend port ${port} is busy before starting containerized HAProxy."
  echo "ERROR: port ${port} is already occupied."
  show_port_occupant_exact "$port"
  echo "Free that port manually, then re-run deploy."
  exit 1
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

echo "[3.1/11] Normalize HAProxy env for container runtime..."
set_env_value "HAPROXY_OUTPUT_PATH" "ops/haproxy/runtime/haproxy.cfg"
set_env_value "HAPROXY_RELOAD_CMD" ""

echo "[4/11] Preflight checks..."
ensure_frontdoor_port_available

echo "[5/11] Build custom images..."
docker compose --env-file .env build web bot

echo "[6/11] Start data services..."
docker compose --env-file .env up -d db wpdb

echo "[7/11] Start app services..."
docker compose --env-file .env up -d wordpress web
echo "Rendering HAProxy runtime config for container..."
run_in_web_with_retry 15 2 python /app/scripts/ops/render_haproxy_cfg.py --env-file /app/.env --output-path /app/ops/haproxy/runtime/haproxy.cfg --skip-validate --skip-reload
ensure_haproxy_frontend_port_available
docker compose --env-file .env up -d haproxy
start_proxy_with_port_takeover
docker compose --env-file .env --profile bot up -d bot

echo "[8/11] Django migrations + static are handled by web entrypoint..."

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
