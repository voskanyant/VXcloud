#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/apps/vxcloud/app}"
BACKUP_ROOT="${BACKUP_ROOT:-/srv/backups/vxcloud}"
TIMESTAMP="${TIMESTAMP:-$(date +%F_%H%M%S)}"
BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"

cd "$APP_DIR"

if [[ ! -f .env && -f /srv/secrets/vxcloud.env ]]; then
  cp /srv/secrets/vxcloud.env .env
  chmod 600 .env
fi

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found in $APP_DIR"
  exit 1
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

env_get() {
  local key="$1"
  local fallback="${2:-}"
  local value
  value="$(grep -E "^${key}=" .env 2>/dev/null | tail -n1 | cut -d= -f2- || true)"
  if [[ -z "${value}" ]]; then
    printf '%s' "$fallback"
  else
    printf '%s' "$value"
  fi
}

POSTGRES_DB_NAME="$(env_get "POSTGRES_DB_NAME" "vxcloud")"
POSTGRES_DB_USER="$(env_get "POSTGRES_DB_USER" "vxcloud")"
WORDPRESS_DB_NAME="$(env_get "WORDPRESS_DB_NAME" "")"
WORDPRESS_DB_USER="$(env_get "WORDPRESS_DB_USER" "")"
WORDPRESS_DB_PASSWORD="$(env_get "WORDPRESS_DB_PASSWORD" "")"

find_named_volume() {
  local exact_name="$1"
  docker volume ls --format '{{.Name}}' | grep -E "(^|_)${exact_name}$" | head -n1 || true
}

backup_volume_tar() {
  local volume_name="$1"
  local output_name="$2"
  if [[ -z "$volume_name" ]]; then
    echo "WARN: volume for ${output_name} not found, skipping"
    return 0
  fi

  docker run --rm \
    -v "${volume_name}:/from:ro" \
    -v "${BACKUP_DIR}:/to" \
    alpine:3.20 \
    sh -lc "cd /from && tar czf /to/${output_name} ."
}

echo "[1/7] Copy env and compose metadata..."
cp .env "${BACKUP_DIR}/vxcloud.env"
cp docker-compose.yml "${BACKUP_DIR}/docker-compose.yml"
chmod 600 "${BACKUP_DIR}/vxcloud.env"

echo "[2/7] Export git revision..."
git rev-parse HEAD > "${BACKUP_DIR}/git-revision.txt"

echo "[3/7] Backup PostgreSQL..."
docker exec -T vxcloud-db pg_dump -U "${POSTGRES_DB_USER}" -d "${POSTGRES_DB_NAME}" -Fc \
  > "${BACKUP_DIR}/postgres-vxcloud.dump"

echo "[4/7] Backup MariaDB..."
if [[ -n "$WORDPRESS_DB_NAME" && -n "$WORDPRESS_DB_USER" && -n "$WORDPRESS_DB_PASSWORD" ]]; then
  docker exec -e MYSQL_PWD="${WORDPRESS_DB_PASSWORD}" -T vxcloud-wpdb \
    mariadb-dump -u"${WORDPRESS_DB_USER}" --single-transaction --quick "${WORDPRESS_DB_NAME}" \
    > "${BACKUP_DIR}/mariadb-wordpress.sql"
else
  echo "WARN: WordPress DB credentials are incomplete in .env, skipping MariaDB dump"
fi

echo "[5/7] Backup WordPress data volume..."
WORDPRESS_VOLUME="$(find_named_volume "vxcloud_wordpress_data")"
backup_volume_tar "$WORDPRESS_VOLUME" "wordpress-data.tar.gz"

echo "[6/7] Backup local x-ui data if present..."
if [[ -d /usr/local/x-ui ]]; then
  tar czf "${BACKUP_DIR}/x-ui-usr-local.tar.gz" /usr/local/x-ui
fi
if [[ -d /etc/x-ui ]]; then
  tar czf "${BACKUP_DIR}/x-ui-etc.tar.gz" /etc/x-ui
fi

echo "[7/7] Write checksums..."
(cd "$BACKUP_DIR" && sha256sum * > SHA256SUMS)

echo "Backup complete: ${BACKUP_DIR}"
