# VXcloud Main Server DR Plan

Этот runbook нужен для восстановления **control plane** после полной потери main server.

Текущая архитектура:

- main server держит:
  - Django web
  - Telegram bot
  - payments/webhooks
  - HAProxy public VPN frontend
  - Postgres
  - MariaDB / WordPress
  - local `node-1` Xray/3x-ui
- это текущий single point of failure

## 1. Recovery targets

- целевой RTO: `30-90 минут`, если есть готовый standby server и свежие backups
- целевой RPO: зависит от частоты backup job
- без свежих backup артефактов полного DR нет

## 2. Что должно существовать заранее

Нужно иметь заранее:

- один резервный Linux server
- доступ к GitHub repo
- доступ к DNS
- свежий `.env`
- свежий PostgreSQL backup
- свежий MariaDB backup
- backup WordPress data volume
- backup local x-ui data (`/usr/local/x-ui`, `/etc/x-ui`) если main server всё ещё является `node-1`

Практический минимум:

- nightly backup артефакт
- хранимый **вне** main server
- последняя известная рабочая git revision

## 3. Backup creation on the current main server

На main server:

```bash
cd /srv/apps/vxcloud/app
chmod +x scripts/ops/backup-main-server.sh
sudo ./scripts/ops/backup-main-server.sh
```

По умолчанию backup складывается в:

```bash
/srv/backups/vxcloud/<timestamp>/
```

Ожидаемые артефакты:

- `vxcloud.env`
- `docker-compose.yml`
- `git-revision.txt`
- `postgres-vxcloud.dump`
- `mariadb-wordpress.sql`
- `wordpress-data.tar.gz`
- `x-ui-usr-local.tar.gz` if present
- `x-ui-etc.tar.gz` if present
- `SHA256SUMS`

После создания backup:

```bash
ls -lah /srv/backups/vxcloud/$(ls -1 /srv/backups/vxcloud | tail -n1)
```

Критично:

- этот backup нужно копировать **вне** main server
- локальный backup на том же сервере не является DR

## 4. Standby server bootstrap

На новом standby server:

```bash
apt update
apt -y upgrade
apt -y install git curl wget ca-certificates jq tar gzip unzip docker.io docker-compose-plugin
systemctl enable --now docker
mkdir -p /srv/apps/vxcloud
cd /srv/apps/vxcloud
git clone https://github.com/voskanyant/VXcloud.git app
cd app
git checkout <git-revision-from-backup>
```

Скопировать backup directory на standby, например:

```bash
/srv/backups/vxcloud/2026-04-12_160000
```

## 5. Restore sequence on standby

### 5.1 Restore env

```bash
cd /srv/apps/vxcloud/app
cp /srv/backups/vxcloud/<timestamp>/vxcloud.env .env
chmod 600 .env
```

### 5.2 Start data containers

```bash
docker compose --env-file .env up -d db wpdb
docker compose --env-file .env ps
```

Wait until `db` and `wpdb` become healthy.

### 5.3 Restore PostgreSQL

```bash
cat /srv/backups/vxcloud/<timestamp>/postgres-vxcloud.dump | docker exec -i vxcloud-db pg_restore -U vxcloud -d vxcloud --clean --if-exists --no-owner --no-privileges
```

### 5.4 Restore MariaDB

```bash
source .env
cat /srv/backups/vxcloud/<timestamp>/mariadb-wordpress.sql | docker exec -e MYSQL_PWD="$WORDPRESS_DB_PASSWORD" -i vxcloud-wpdb mariadb -u"$WORDPRESS_DB_USER" "$WORDPRESS_DB_NAME"
```

### 5.5 Restore WordPress data volume

Сначала найти volume name:

```bash
docker volume ls --format '{{.Name}}' | grep -E '(^|_)vxcloud_wordpress_data$'
```

Потом восстановить:

```bash
docker run --rm \
  -v <resolved_wordpress_volume>:/to \
  -v /srv/backups/vxcloud/<timestamp>:/backup:ro \
  alpine:3.20 \
  sh -lc 'cd /to && tar xzf /backup/wordpress-data.tar.gz'
```

### 5.6 Start app stack

```bash
cd /srv/apps/vxcloud/app
chmod +x scripts/ops/deploy-auto.sh
./scripts/ops/deploy-auto.sh
```

## 6. Restore local node-1 x-ui if main server still serves VPN traffic

Если standby должен сразу заменить и control plane, и current `node-1`, то восстановить x-ui data:

```bash
tar xzf /srv/backups/vxcloud/<timestamp>/x-ui-usr-local.tar.gz -C /
tar xzf /srv/backups/vxcloud/<timestamp>/x-ui-etc.tar.gz -C /
systemctl daemon-reload
systemctl restart x-ui
systemctl status x-ui --no-pager
ss -ltnp | egrep ':(2053|2096|29941)\b' || true
```

Если VPN data plane будет жить на отдельной ноде, этот шаг не обязателен.

## 7. DNS and traffic cutover

После восстановления сервисов:

1. перевести `A`/`AAAA` записи домена на новый standby IP
2. проверить TTL заранее, если migration planned
3. убедиться, что webhook/provider callbacks будут идти на новый IP

Важно:

- если public VPN endpoint остаётся тем же доменом и портом, клиенты начнут переподключаться туда после DNS/route cutover
- активные существующие VPN сессии не мигрируют live

## 8. Post-restore validation

На standby server:

```bash
cd /srv/apps/vxcloud/app
docker compose --env-file .env ps
docker compose --env-file .env logs --tail=100 web
docker compose --env-file .env logs --tail=100 bot
docker compose --env-file .env logs --tail=100 proxy
docker compose --env-file .env logs --tail=100 haproxy
curl -I http://127.0.0.1:8088/
curl -I http://127.0.0.1:8088/account/
```

Если standby также заменяет `node-1`:

```bash
sudo tail -n 50 /usr/local/x-ui/access.log
```

Проверить вручную:

- сайт открывается
- `/account/` открывается
- bot отвечает
- checkout создаётся
- webhook URL отвечает
- `/ops/` открывается

## 9. Minimal operator checklist

До аварии:

- nightly backups running
- backups copied off-host
- one spare server available or quickly provisionable
- DNS credentials available
- restore process rehearsed at least once

Во время аварии:

- не чинить сразу старый main server, если можно быстрее поднять standby
- сначала вернуть control plane
- потом уже разбираться с root cause

После аварии:

- зафиксировать фактический RTO
- проверить, что backup cadence хватает
- обновить этот runbook по реальным шагам, которые сработали/не сработали
