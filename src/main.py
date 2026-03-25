from __future__ import annotations

import asyncio
import logging

from telegram.ext import ApplicationBuilder

from .bot import VPNBot
from .cms import DirectusCMS
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
    cms: DirectusCMS | None = None
    if settings.cms_base_url and settings.cms_token:
        cms = DirectusCMS(
            base_url=settings.cms_base_url,
            token=settings.cms_token,
            content_collection=settings.cms_content_collection,
            button_collection=settings.cms_button_collection,
        )

    await db.connect()
    await xui.start()
    if cms is not None:
        await cms.start()

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    bot = VPNBot(app=app, settings=settings, db=db, xui=xui, cms=cms)
    bot.register()

    async def reminder_loop() -> None:
        while True:
            try:
                await bot.reminder_tick()
            except Exception:
                logging.exception("Reminder loop failed")
            await asyncio.sleep(3600)

    asyncio.create_task(reminder_loop())

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
        if cms is not None:
            await cms.close()
        await xui.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(run())
