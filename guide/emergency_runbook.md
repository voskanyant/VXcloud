# VXcloud Emergency Runbook

Этот документ нужен не для разработки, а для реальной аварии.  
Открывайте его, когда что-то уже сломалось, и идите по шагам без импровизации.

## 0. Общие правила

Во всех инцидентах сначала делайте одно и то же:

1. Не паниковать и не менять сразу 10 вещей.
2. Зафиксировать:
   - время начала проблемы
   - что именно не работает
   - у всех или только у части клиентов
   - один сервер или все серверы
3. Проверить, что именно упало:
   - `site`
   - `bot`
   - `payments`
   - `VPN node`
   - `Telegram only`
4. Сначала убрать плохой узел из трафика, и только потом чинить его.
5. Если не уверены, не делайте destructive actions на проде.
6. Если ломается только VPN-трафик на main server, сначала отключайте VPN-роль этого сервера из LB, а не весь сервер целиком.

## 1. Быстрые команды

Основные команды на main server:

```bash
cd /srv/apps/vxcloud/app
docker compose --env-file .env ps
docker compose --env-file .env logs --tail=150 web
docker compose --env-file .env logs --tail=150 bot
docker compose --env-file .env logs --tail=150 proxy
```

Healthcheck сайта:

```bash
curl -I http://127.0.0.1:8088/
curl -I http://127.0.0.1:8088/account/
```

Проверка Xray/3x-ui ноды:

```bash
ss -ltnp | grep 29941
sudo tail -n 100 /usr/local/x-ui/access.log
```

Dry-run HAProxy config:

```bash
cd /srv/apps/vxcloud/app
python scripts/ops/render_haproxy_cfg.py --env-file .env --dry-run
```

Temporary HAProxy test path already proven on production:

```bash
cd /srv/apps/vxcloud/app
docker compose --env-file .env exec -T web python /app/scripts/ops/render_haproxy_cfg.py --env-file /app/.env --frontend-port 30940 --dry-run > /tmp/haproxy-vpn-test.cfg
sudo pkill -f "/tmp/haproxy-vpn-test.cfg" || true
sudo haproxy -f /tmp/haproxy-vpn-test.cfg -p /tmp/haproxy-vpn-test.pid -D
```

Current production HAProxy checks:

```bash
cd /srv/apps/vxcloud/app
docker compose --env-file .env exec -T web python /app/scripts/ops/render_haproxy_cfg.py --env-file /app/.env --frontend-port 29940 --dry-run > /tmp/haproxy-prod-cutover.cfg
grep -n "server " /tmp/haproxy-prod-cutover.cfg
sudo grep -n "server " /etc/haproxy/haproxy.cfg
sudo journalctl -u haproxy --since "5 minutes ago" --no-pager | tail -n 40
```

Expected production backend line:

- `server node_10_node-1-main 82.21.117.154:29941 check weight 100`
- no `send-proxy`
- no `check-send-proxy`

Быстрые operational reminders:

- current main server может быть одновременно control plane и `node-1`
- если сломан только VPN routing на main server, сначала выключайте `lb_enabled` у `node-1`
- это не должно останавливать site, bot, payments и `/ops/`

Deploy/restart:

```bash
cd /srv/apps/vxcloud/app
git pull origin main
chmod +x scripts/ops/deploy-auto.sh
./scripts/ops/deploy-auto.sh
```

## 2. Сценарий: один VPN node сломан полностью

Симптомы:
- клиенты на одном узле перестали подключаться
- Xray не слушает нужный порт
- node health падает
- другие узлы работают

Что делать:

1. Проверить, что проблема только на одном узле.
2. Убрать узел из балансировки:
   - в `/ops/` выключить `lb_enabled`
   - перерендерить/reload HAProxy
3. Убедиться, что новые подключения больше не попадают на этот узел.
4. Проверить рабочие узлы.
5. Только после этого чинить сломанный узел.

Если это именно main server как `node-1`, но сам control plane жив:

6. Не останавливать сайт, бот и backoffice.
7. Временно использовать main server только как control plane, пока VPN-часть не исправлена.

Цель:
- новые пользователи и переподключения должны уйти на живые узлы

Важно:
- уже существующие активные TCP-сессии на этом узле могут оборваться
- HAProxy не переносит уже установленную VPN-сессию на другой node
- изменение флагов ноды в `/ops/` само по себе не меняет уже запущенный HAProxy; нужен отдельный render/restart or reload step
- после production cutover не искать Xray на `29940`; теперь его backend должен слушать `29941`

## 3. Сценарий: node жив, но Telegram не работает

Это самый опасный сценарий, потому что сайт и другие приложения могут работать нормально.

Симптомы:
- YouTube / сайты / browser работают
- Telegram через этот node timeout или не грузится
- на другом node Telegram работает

Что делать:

1. Подтвердить, что проблема именно node-specific:
   - проверить этот же клиент на другом node
   - сравнить с Germany/main node
2. Проверить с самого сервера:

```bash
curl -I --max-time 15 https://telegram.org
curl -I --max-time 15 https://web.telegram.org
```

3. Если Telegram не ходит именно с этого node:
   - убрать узел из LB
   - оставить в пуле только хорошие узлы
4. Не пытаться чинить это через приложение VXcloud.
5. Открыть тикет провайдеру / датацентру.
6. Если есть запасной узел у другого провайдера, включить его в пул вместо плохого.

Что это значит:
- проблема обычно в маршрутизации, пиринге, доступности Telegram с конкретного IP/ASN
- HAProxy сам это не распознаёт как unhealthy

Важное правило:
- node, на котором не работает Telegram, нельзя оставлять в production LB pool

## 4. Сценарий: bot не отвечает, сайт жив

Симптомы:
- сайт и `/account/` открываются
- платежи и кабинет могут работать
- Telegram bot не отвечает или не шлёт сообщения

Что делать:

1. Проверить контейнер бота:

```bash
cd /srv/apps/vxcloud/app
docker compose --env-file .env ps bot
docker compose --env-file .env logs --tail=200 bot
```

2. Если bot container умер:
   - перезапустить deploy script
3. Если bot container жив, но Telegram API недоступен:
   - проверить сетевую доступность Telegram с main server
4. Если Telegram API у main server недоступен:
   - это уже control-plane incident
   - временно вести клиентов через сайт и кабинет

Временный fallback:
- платежи картой через сайт
- выдача конфигов через сайт
- support через сайт/ops, пока bot не восстановлен

## 5. Сценарий: сайт не открывается, bot жив

Симптомы:
- бот отвечает
- сайт или `/account/` не открываются
- платежи картой недоступны

Что делать:

1. Проверить `web`, `proxy`, `wordpress`, `db`, `wpdb`:

```bash
cd /srv/apps/vxcloud/app
docker compose --env-file .env ps
docker compose --env-file .env logs --tail=150 web
docker compose --env-file .env logs --tail=150 proxy
docker compose --env-file .env logs --tail=150 wordpress
```

2. Проверить локальный health:

```bash
curl -I http://127.0.0.1:8088/
curl -I http://127.0.0.1:8088/account/
```

3. Если приложение поднимается локально, а снаружи нет:
   - проблема в nginx/proxy/domain/firewall
4. Если `web` падает:
   - быстро вернуть через deploy/restart

Временный fallback:
- если bot жив, не обещать клиентам оплату картой до восстановления сайта
- в support ответе писать, что идёт временное восстановление кабинета

## 6. Сценарий: main server умер полностью

Это худший сценарий. Сейчас это single point of failure.

Что падает сразу:
- bot
- site
- payments/webhooks
- backoffice
- HAProxy на main server
- databases, если они только там

Цель:
- поднять standby control server

Нужно иметь заранее:
- резервный сервер
- repo
- `.env`
- Postgres backup
- WordPress/MariaDB backup
- доступ к DNS

Порядок восстановления:

1. Поднять standby server.
2. Развернуть repo.
3. Восстановить `.env`.
4. Восстановить Postgres.
5. Восстановить WordPress DB/files.
6. Запустить docker stack.
7. Переключить домен/DNS/reverse proxy.
8. Проверить:
   - сайт
   - `/account/`
   - bot
   - YooKassa webhook endpoint
   - `/ops/`

Если standby не готов:
- это значит, что полного backup plan для control plane пока нет

## 7. Сценарий: YooKassa/оплаты сломались

Симптомы:
- checkout не создаётся
- webhook не активирует заказ
- `/ops/` показывает новые `pending`

Что делать:

1. Проверить `PAYMENT_PROVIDER`, `PAYMENT_YOOKASSA_SHOP_ID`, `PAYMENT_YOOKASSA_API_KEY` на сервере.
2. Проверить, что webhook URL жив:
   - `https://vxcloud.ru/api/webhooks/yookassa`
3. Проверить `web` logs.
4. Проверить последние заказы в `/ops/ -> Заказы`.

Если checkout создаётся, но активации нет:
- проблема чаще всего в webhook

Если checkout не создаётся:
- проблема в credentials/config/runtime

Временный fallback:
- не направлять людей на card flow, пока проблема не понятна
- отвечать в support, что платёжная интеграция временно диагностируется

## 8. Сценарий: новый deploy сломал production

Симптомы:
- после deploy сайт/бот/кабинет ведут себя хуже, чем до deploy

Что делать:

1. Не деплоить ещё что-то поверх.
2. Зафиксировать текущий commit:

```bash
cd /srv/apps/vxcloud/app
git rev-parse HEAD
```

3. Найти предыдущий рабочий commit.
4. Вернуть production на предыдущий рабочий commit.

Безопасный rollback:
- checkout previous working commit
- redeploy through the same deploy script

Важно:
- не делать `git reset --hard` без понимания
- не удалять базы
- rollback только к заведомо рабочему коду

## 9. Что должно быть готово заранее

До роста пользователей должны быть готовы:

- минимум 2 VPN nodes у разных провайдеров
- main server backup plan
- standby control server
- свежие DB backups
- documented DNS access
- быстрый способ выключить `lb_enabled` у плохого node
- проверенный HAProxy reload path
- понимание, что main server можно временно оставить только control plane, отключив его VPN-роль через `/ops/`
- понимание, что production `29940` уже HAProxy path, а Xray backend живёт на `29941`
- понимание, что Xray access log сейчас не показывает реальный client IP после HAProxy cutover

## 10. Минимальный emergency checklist

Если что-то случилось, всегда пройти этот короткий список:

1. Это один node или весь сервис?
2. Это только Telegram или всё?
3. Живы ли `web`, `bot`, `proxy`, `db`?
4. Нужно ли убрать node из LB прямо сейчас?
5. Есть ли рабочий второй node?
6. Нужно ли делать rollback?
7. Нужно ли включать standby plan?

## 11. Нельзя делать в аварии

- не трогать сразу и bot, и site, и HAProxy, и node одновременно
- не включать в LB node, который не проверен вручную
- не оставлять в production пуле node, где Telegram broken
- не править expiry/payments/subscriptions вручную в 3x-ui как основной recovery path
- не удалять заказы/подписки из БД “чтобы стало чище”

## 12. После инцидента

После восстановления обязательно записать:

- что именно сломалось
- какой был реальный root cause
- как быстро нашли
- что нужно автоматизировать, чтобы второй раз это не повторилось
