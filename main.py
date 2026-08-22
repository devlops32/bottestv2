# main.py - Запуск бота

import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault
from config import BOT_TOKEN, AUTO_SELL_ENABLED
from handlers import router
from utils import proxy_rotator
from automation import init_auto_engine
from database import db

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

async def on_startup(bot: Bot):
    logger.info("🚀 Бот запускается...")
    db.init_db()
    logger.info("✅ База данных готова")

async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    if proxy_rotator.proxies:
        first_proxy = proxy_rotator.proxies[0]
        logger.info(f"🌐 Using proxy: {first_proxy}")
    
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="subscribe", description="Подписаться на уведомления"),
        BotCommand(command="unsubscribe", description="Отписаться от уведомлений"),
        BotCommand(command="code", description="Найти товар по коду"),
    ], scope=BotCommandScopeDefault())
    
    auto_engine = init_auto_engine(bot)
    
    dp = Dispatcher()
    dp.include_router(router)
    
    await on_startup(bot)
    
    if AUTO_SELL_ENABLED:
        logger.info("🚀 Запуск движка автоматизации...")
        asyncio.create_task(auto_engine.start())
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    finally:
        if AUTO_SELL_ENABLED:
            await auto_engine.stop()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())