#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/srv/apps/vxcloud/app"
cd "$APP_DIR"

echo "[1/6] Fetch latest..."
git fetch origin main

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse origin/main)"
echo "LOCAL=$LOCAL"
echo "REMOTE=$REMOTE"

echo "[2/6] Auto-stash local/untracked changes (if any)..."
git stash push -u -m "auto-stash-before-deploy-$(date +%F_%H%M%S)" >/dev/null || true

echo "[3/6] Fast-forward pull..."
git pull --ff-only origin main

echo "[4/6] Rebuild/start containers..."
docker compose --env-file .env up -d --build db web
docker compose --env-file .env --profile bot up -d --build bot

echo "[5/6] Health checks..."
HTTP_CODE="$(curl -sS -o /dev/null -w "%{http_code}" -H "Host: vxcloud.ru" http://127.0.0.1:8088 || true)"
if [[ -z "$HTTP_CODE" || "$HTTP_CODE" == "000" || "$HTTP_CODE" -ge 500 ]]; then
  echo "ERROR: web healthcheck failed, HTTP=$HTTP_CODE"
  exit 1
fi
echo "web healthcheck OK (HTTP=$HTTP_CODE)"
docker compose --env-file .env ps

echo "[6/6] Done."
echo "If needed, stashes are here:"
git stash list | head -n 3 || true
