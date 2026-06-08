"""
Telegram Bot на aiogram 3
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import BotCommand
from shared.config import BOT_TOKEN, OWNER_ID
from shared.database import init_db, SessionLocal
from bot.utils.helpers import load_config_cache
from bot.handlers import client, admin

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def set_default_commands(bot: Bot):
    """Установить команды бота"""
    commands = [
        BotCommand(command="start", description="🚀 Главное меню"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="buy", description="💳 Купить подписку"),
        BotCommand(command="admin", description="⚙️ Админ-панель"),
        BotCommand(command="help", description="ℹ️ Справка"),
    ]
    await bot.set_my_commands(commands)
    logger.info("✅ Команды бота установлены")


async def on_startup():
    """Действия при запуске бота"""
    logger.info("🤖 Бот запускается...")
    init_db()
    # Загружаем кэш конфигов в память
    db = SessionLocal()
    try:
        load_config_cache(db)
    finally:
        db.close()
    await set_default_commands(bot)
    logger.info("✅ Бот готов к работе")


async def on_shutdown():
    """Действия при остановке бота"""
    logger.info("⛔ Бот останавливается...")
    await bot.session.close()


async def main():
    """Главная функция"""
    # Регистрируем хэндлеры
    dp.include_router(client.router)
    dp.include_router(admin.router)

    # Регистрируем обработчики событий
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Удаляем вебхуки и запускаем polling
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("🚀 Запуск polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
