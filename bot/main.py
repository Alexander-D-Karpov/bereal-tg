import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from bot.config import Config
from bot.handlers import router, setup_commands
from bot.scheduler import Scheduler
from bot.storage import Storage


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    config = Config.from_env()

    if not config.bot_token:
        logger.error("BOT_TOKEN not set in environment variables")
        return

    storage = Storage(config.data_file)
    await storage.load()

    session = AiohttpSession(proxy=config.proxy_url) if config.proxy_url else None

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )

    scheduler = Scheduler(bot, storage)

    dp = Dispatcher()
    dp.include_router(router)

    dp["storage"] = storage
    dp["scheduler"] = scheduler

    await setup_commands(bot)

    scheduler.reschedule_all()

    storage.start_periodic_save()

    logger.info("Bot started")

    try:
        await dp.start_polling(bot)
    finally:
        storage.stop_periodic_save()
        storage.save()
        scheduler.stop_all()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
