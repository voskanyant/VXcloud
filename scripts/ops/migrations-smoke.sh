#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/apps/vxcloud/app}"
ENV_FILE="${ENV_FILE:-.env}"
DB_SERVICE="${DB_SERVICE:-db}"
DB_USER="${DB_USER:-vxcloud}"
BASE_DB="${BASE_DB:-vxcloud}"

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

SMOKE_DB="vxcloud_migrate_smoke_$(date +%s)"

MIGRATIONS=(
  "sql/migrations/20260328_add_client_code_to_users.sql"
  "sql/migrations/20260328_add_xui_sub_id_to_subscriptions.sql"
  "sql/migrations/20260328_create_payment_events.sql"
  "sql/migrations/20260328_expand_orders_for_card_payments.sql"
  "sql/migrations/20260328_create_support_tables.sql"
  "sql/migrations/20260328_create_web_login_tokens.sql"
  "sql/migrations/20260328_add_orders_notified_at.sql"
  "sql/migrations/20260328_add_orders_payment_idempotency_guards.sql"
  "sql/migrations/20260329_add_multiconfig_fields_to_orders.sql"
  "sql/migrations/20260329_add_multiconfig_fields_to_subscriptions.sql"
)

psql_db() {
  local db_name="$1"
  shift
  docker compose --env-file "$ENV_FILE" exec -T \
    -e PGPASSWORD="${POSTGRES_PASSWORD}" \
    "$DB_SERVICE" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$db_name" "$@"
}

cleanup() {
  set +e
  psql_db "$BASE_DB" -c "DROP DATABASE IF EXISTS ${SMOKE_DB};" >/dev/null 2>&1
}
trap cleanup EXIT

echo "[1/5] Creating temporary smoke DB: $SMOKE_DB"
psql_db "$BASE_DB" -c "CREATE DATABASE ${SMOKE_DB};"

echo "[2/5] Creating legacy baseline schema"
psql_db "$SMOKE_DB" <<'SQL'
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  telegram_id BIGINT UNIQUE NOT NULL,
  username TEXT,
  first_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE subscriptions (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  inbound_id INTEGER NOT NULL,
  client_uuid UUID NOT NULL,
  client_email TEXT NOT NULL UNIQUE,
  vless_url TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE orders (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  amount_stars INTEGER NOT NULL,
  currency TEXT NOT NULL DEFAULT 'XTR',
  payload TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'pending',
  telegram_payment_charge_id TEXT UNIQUE,
  provider_payment_charge_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  paid_at TIMESTAMPTZ
);
SQL

echo "[3/5] Applying SQL migrations"
for migration in "${MIGRATIONS[@]}"; do
  if [[ ! -f "$migration" ]]; then
    echo "ERROR: migration file not found: $migration"
    exit 1
  fi
  echo "  -> $migration"
  psql_db "$SMOKE_DB" -f - < "$migration"
done

echo "[4/5] Running smoke scenarios"
psql_db "$SMOKE_DB" <<'SQL'
INSERT INTO users (telegram_id, username, first_name)
VALUES (78050167, 'smoke_user', 'Smoke');

INSERT INTO subscriptions (
  user_id, inbound_id, client_uuid, client_email, vless_url, expires_at, is_active
)
VALUES (
  1, 1, '11111111-1111-1111-1111-111111111111', 'smoke_1', 'vless://smoke', NOW() + INTERVAL '30 day', TRUE
);

INSERT INTO orders (user_id, amount_stars, payload, status)
VALUES (1, 250, 'renew:1:1:smoke', 'pending');

INSERT INTO payment_events (provider, event_id, body)
VALUES ('reference', 'evt-smoke-1', '{"status":"ok"}');

DO $$
DECLARE
  code_val TEXT;
  order_kind_val TEXT;
  meta_val JSONB;
  display_name_val TEXT;
  event_count INTEGER;
BEGIN
  SELECT client_code INTO code_val FROM users WHERE id = 1;
  IF code_val IS NULL OR code_val = '' THEN
    RAISE EXCEPTION 'client_code is empty after migrations';
  END IF;

  SELECT order_kind, meta INTO order_kind_val, meta_val FROM orders WHERE id = 1;
  IF order_kind_val IS DISTINCT FROM 'renew' THEN
    RAISE EXCEPTION 'orders.order_kind default mismatch: %', order_kind_val;
  END IF;
  IF meta_val IS DISTINCT FROM '{}'::jsonb THEN
    RAISE EXCEPTION 'orders.meta default mismatch: %', meta_val;
  END IF;

  SELECT display_name INTO display_name_val FROM subscriptions WHERE id = 1;
  IF display_name_val IS NULL THEN
    RAISE EXCEPTION 'subscriptions.display_name is null';
  END IF;

  BEGIN
    INSERT INTO payment_events (provider, event_id, body)
    VALUES ('reference', 'evt-smoke-1', '{"status":"dup"}');
  EXCEPTION WHEN unique_violation THEN
    -- expected
    NULL;
  END;

  SELECT COUNT(*) INTO event_count
  FROM payment_events
  WHERE provider = 'reference' AND event_id = 'evt-smoke-1';
  IF event_count <> 1 THEN
    RAISE EXCEPTION 'payment_events dedup failed; count=%', event_count;
  END IF;
END $$;
SQL

echo "[5/5] Migration smoke passed on ${SMOKE_DB}"
