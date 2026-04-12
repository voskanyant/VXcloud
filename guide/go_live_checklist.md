# VXcloud Go-Live Checklist

Аварийный план: [emergency_runbook.md](./emergency_runbook.md)

Этот чек-лист нужен не для разработки, а для реального запуска. Идите по нему сверху вниз и не пропускайте шаги.

## 1. Production env

Проверьте на сервере `/srv/apps/vxcloud/app/.env`:

- `PAYMENT_PROVIDER=yookassa`
- `ENABLE_CARD_PAYMENTS=1`
- `PAYMENT_YOOKASSA_SHOP_ID` заполнен
- `PAYMENT_YOOKASSA_API_KEY` заполнен
- `VPN_PUBLIC_HOST=vxcloud.ru`
- `VPN_PUBLIC_PORT=29940`
- `HAPROXY_FRONTEND_PORT=29940`
- `HAPROXY_BACKEND_SEND_PROXY=0`
- `CMS_BASE_URL=` пусто
- `CMS_TOKEN=` пусто

Если `CMS_BASE_URL` или `CMS_TOKEN` заполнены, legacy Directus bridge всё ещё активен.

## 2. Deploy

```bash
cd /srv/apps/vxcloud/app
git pull origin main
chmod +x scripts/ops/deploy-auto.sh
./scripts/ops/deploy-auto.sh
```

После деплоя проверьте:

```bash
docker compose --env-file .env ps
```

Ожидается:

- `vxcloud-web` running
- `vxcloud-bot` running
- `vxcloud-proxy` running
- базы healthy

## 3. Site payment flow

Проверьте как обычный клиент:

1. Откройте сайт.
2. Войдите в аккаунт.
3. Нажмите `Купить доступ`.
4. Убедитесь, что открывается YooKassa.
5. Отмените оплату.
6. Вернитесь и повторите ещё раз.

Ожидается:

- checkout открывается без ошибок
- отменённый checkout не ломает повторную попытку
- старый `pending` не висит вечно

## 4. Bot payment flow

Проверьте в Telegram:

1. `⭐ Купить новый доступ`
2. `💳 Оплатить картой`
3. Кнопка должна открыть сразу checkout, не просто кабинет
4. `📊 Мой доступ`
5. `🔄 Продлить`
6. Кнопка должна открыть сразу renew checkout

Ожидается:

- buy card ведёт в checkout
- renew card ведёт в checkout
- Stars не подсовывается вместо card там, где нужен card

## 5. Successful payment

Сделайте одну реальную тестовую покупку.

Проверьте:

- заказ в `/ops/` уходит из `pending` в `activated`
- пользователю приходит доступ
- в боте и на сайте виден новый конфиг
- ссылка конфигурации импортируется без ручного редактирования
- порт в `vless://...` равен `29940`

## 6. Config delivery

Проверьте оба канала:

- бот `Скопировать ссылку`
- сайт `Скопировать ссылку`
- страница `QR и конфиг`

Ожидается:

- копируется именно `vless://...`
- не копируется `https://.../sub/...`
- QR-код соответствует той же `vless://...` ссылке
- импорт проходит без ручной правки порта

## 7. Existing clients

Проверьте хотя бы один старый конфиг:

- старый клиент продолжает подключаться
- если открыть старый конфиг в кабинете, ссылка нормализуется под текущий public host/port

## 8. Backoffice sanity

Проверьте `/ops/`:

- `Тикеты`
- `Заказы`
- `Подписки`
- `Пользователи`
- `VPN ноды`
- `Cluster & HAProxy`

Особенно:

- нет ли старых `pending` card orders старше 30 минут
- если есть, нажмите `Очистить stale card pending`
- `Legacy Directus` должен быть `Off`
- current main server должен быть заведён в `VPN ноды` как `node-1`
- у `node-1` должно быть понятно, что его можно отдельно выключить из LB через `lb_enabled`, не ломая site/bot/backend
- production path должен быть уже переведён под HAProxy:
  - public `29940` слушает HAProxy
  - `node-1-main backend_port = 29941`
  - local Xray inbound слушает `29941`
  - 3x-ui inbound `Proxy Protocol = off`

## 9. Support path

Отправьте тестовое сообщение в поддержку из Telegram.

Проверьте:

- тикет появляется в `/ops/`
- reply из backoffice доходит пользователю
- тикет можно закрыть

## 10. HAProxy readiness before first node add

До добавления новой ноды убедитесь:

- текущая нода стабильна
- новая нода имеет тот же REALITY public key / short id / SNI / fingerprint, что и основная majority pool
- на новой ноде открыт inbound port в firewall
- новая нода не помечена `lb_enabled`, пока не завершён backfill

Dry-run:

```bash
python scripts/ops/render_haproxy_cfg.py --env-file .env --dry-run
```

Проверьте:

- в output только здоровые ноды
- frontend port правильный
- backend servers правильные

Temporary tested HAProxy path:

```bash
docker compose --env-file .env exec -T web python /app/scripts/ops/render_haproxy_cfg.py --env-file /app/.env --frontend-port 30940 --dry-run > /tmp/haproxy-vpn-test.cfg
sudo pkill -f "/tmp/haproxy-vpn-test.cfg" || true
sudo haproxy -f /tmp/haproxy-vpn-test.cfg -p /tmp/haproxy-vpn-test.pid -D
```

Expected behavior:

- if `node-1-main` is enabled, VPN through client port `30940` works
- if `node-1-main` is disabled and test HAProxy is re-rendered/restarted, VPN through `30940` stops
- if manual clients are used in 3x-ui, create them only on the canonical node before checking cross-node sync

Current production HAProxy path:

```bash
docker compose --env-file .env exec -T web python /app/scripts/ops/render_haproxy_cfg.py --env-file /app/.env --frontend-port 29940 --dry-run > /tmp/haproxy-prod-cutover.cfg
grep -n "server " /tmp/haproxy-prod-cutover.cfg
sudo cp /tmp/haproxy-prod-cutover.cfg /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
sudo grep -n "server " /etc/haproxy/haproxy.cfg
```

Expected behavior:

- backend line points to `82.21.117.154:29941`
- backend line contains `check weight 100`
- backend line does not contain `send-proxy`
- backend line does not contain `check-send-proxy`
- client keeps using the same old public port `29940`

## 11. First node add rehearsal

Порядок:

1. Добавить ноду в БД
2. Проверить health
3. Синхронизировать клиентов
4. Проверить, что `needs_backfill = false`
5. Только потом включить `lb_enabled`
6. Сгенерировать HAProxy config
7. Проверить старый клиент
8. Проверить новый созданный клиент

Если что-то не так:

- сразу выключить `lb_enabled` у новой ноды
- перерендерить HAProxy
- reload HAProxy

## 12. Final no-go conditions

Не запускать в прод, если верно хотя бы одно:

- checkout иногда открывает кабинет вместо оплаты
- новые конфиги всё ещё содержат старый порт
- в backoffice копятся свежие необъяснимые `pending`
- тикеты из Telegram не попадают в `/ops/`
- новая нода не проходит health/backfill, но уже включена в HAProxy
- Directus случайно всё ещё включён
