#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/apps/vxcloud/app}"
ENV_FILE="${ENV_FILE:-.env}"
HEALTHCHECK_HOST="${HEALTHCHECK_HOST:-vxcloud.ru}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8088}"
ENABLE_FLAGS=true

if [[ "${1:-}" == "--skip-flags" ]]; then
  ENABLE_FLAGS=false
fi

cd "$APP_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $APP_DIR/$ENV_FILE"
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
  echo "ERROR: POSTGRES_PASSWORD is empty in $ENV_FILE"
  exit 1
fi

MIGRATIONS=(
  "sql/migrations/20260328_add_client_code_to_users.sql"
  "sql/migrations/20260328_add_xui_sub_id_to_subscriptions.sql"
  "sql/migrations/20260328_create_payment_events.sql"
  "sql/migrations/20260328_expand_orders_for_card_payments.sql"
  "sql/migrations/20260328_create_support_tables.sql"
  "sql/migrations/20260328_create_web_login_tokens.sql"
  "sql/migrations/20260328_add_orders_notified_at.sql"
  "sql/migrations/20260328_add_orders_payment_idempotency_guards.sql"
  "sql/migrations/20260402_create_vpn_cluster_tables.sql"
  "sql/migrations/20260402_add_vpn_nodes_backfill_requested_at.sql"
  "sql/migrations/20260402_extend_vpn_nodes_ops_fields.sql"
  "sql/migrations/20260420_add_subscription_assignment_and_rebalance.sql"
)

set_env_var() {
  local key="$1"
  local value="$2"
  local file="$3"
  if grep -q "^${key}=" "$file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$file"
  else
    echo "${key}=${value}" >> "$file"
  fi
}

healthcheck() {
  curl -fsS -I -H "Host: ${HEALTHCHECK_HOST}" "${HEALTHCHECK_URL}" >/dev/null
}

echo "[1/5] Applying SQL migrations..."
for migration in "${MIGRATIONS[@]}"; do
  if [[ ! -f "$migration" ]]; then
    echo "ERROR: migration file not found: $migration"
    exit 1
  fi
  echo "  -> $migration"
  docker compose --env-file "$ENV_FILE" exec -T \
    -e PGPASSWORD="${POSTGRES_PASSWORD}" \
    db psql -v ON_ERROR_STOP=1 -U vxcloud -d vxcloud -f - < "$migration"
done

echo "[2/5] Healthcheck after SQL migrations..."
healthcheck
echo "  OK"

echo "[3/5] Enabling feature flags..."
if [[ "$ENABLE_FLAGS" == true ]]; then
  cp "$ENV_FILE" "${ENV_FILE}.bak.$(date +%F_%H%M%S)"
  set_env_var "ENABLE_CARD_PAYMENTS" "1" "$ENV_FILE"
  echo "  ENABLE_CARD_PAYMENTS=1"
else
  echo "  skipped (--skip-flags)"
fi

echo "[4/5] Rolling restart web/bot..."
docker compose --env-file "$ENV_FILE" up -d --no-deps web
docker compose --env-file "$ENV_FILE" --profile bot up -d --no-deps bot

echo "[5/5] Final healthcheck..."
healthcheck
docker compose --env-file "$ENV_FILE" ps
echo "Done."
