from __future__ import annotations

import asyncio
import logging

from telegram.ext import ApplicationBuilder

from .bot import VPNBot
from .cluster.jobs import healthcheck_tick, sync_tick
from .cluster.rebalance import rebalance_tick
from .config import load_settings
from .db import DB
from .xui_client import XUIClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


async def run() -> None:
    settings = load_settings()
    db = DB(settings.database_url)
    xui = XUIClient(settings.xui_base_url, settings.xui_username, settings.xui_password)

    await db.connect()
    await xui.start()

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    bot = VPNBot(app=app, settings=settings, db=db, xui=xui)
    bot.register()

    async def reminder_loop() -> None:
        while True:
            try:
                await bot.reminder_tick()
            except Exception:
                logging.exception("Reminder loop failed")
            await asyncio.sleep(3600)

    async def single_ip_loop() -> None:
        interval = max(10, settings.single_ip_check_interval_seconds)
        while True:
            try:
                await bot.single_ip_tick()
            except Exception:
                logging.exception("Single-IP loop failed")
            await asyncio.sleep(interval)

    async def cluster_health_loop() -> None:
        interval = max(10, int(getattr(settings, "vpn_cluster_healthcheck_interval_seconds", 30)))
        while True:
            try:
                await healthcheck_tick(db)
            except Exception:
                logging.exception("Cluster health loop failed")
            await asyncio.sleep(interval)

    async def cluster_sync_loop() -> None:
        interval = max(10, int(getattr(settings, "vpn_cluster_sync_interval_seconds", 60)))
        while True:
            try:
                await sync_tick(db, settings)
            except Exception:
                logging.exception("Cluster sync loop failed")
            await asyncio.sleep(interval)

    async def cluster_rebalance_loop() -> None:
        interval = max(30, int(getattr(settings, "vpn_rebalance_workflow_tick_seconds", 60)))
        while True:
            try:
                await rebalance_tick(db, settings)
            except Exception:
                logging.exception("Cluster rebalance loop failed")
            await asyncio.sleep(interval)

    asyncio.create_task(reminder_loop())
    asyncio.create_task(single_ip_loop())
    if settings.vpn_cluster_enabled:
        asyncio.create_task(cluster_health_loop())
        asyncio.create_task(cluster_sync_loop())
        if settings.vpn_rebalance_enabled:
            asyncio.create_task(cluster_rebalance_loop())

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await xui.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(run())
