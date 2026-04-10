"""
Запускает веб-сервер и Telegram-бот одновременно.
Использование:
    python run.py
"""
import asyncio
import logging
import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    from app.main import app as fastapi_app
    from app.bot import build_application

    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))

    # Web server
    config = uvicorn.Config(fastapi_app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    # Telegram bot
    bot_app = build_application()

    logger.info("Запуск сервера на http://%s:%s", host, port)
    logger.info("Запуск Telegram-бота...")

    async with bot_app:
        await bot_app.start()
        await bot_app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram-бот запущен")
        await server.serve()
        await bot_app.updater.stop()
        await bot_app.stop()


if __name__ == "__main__":
    asyncio.run(main())
