"""«Дайвинчик 2.0» — безопасная система знакомств «от входа до конца».

Полный путь пользователя: вход → язык → правила 18+ → анкета → поиск →
взаимный лайк → анонимный приватный диалог (сообщения не хранятся).

Запуск:
    pip install -r requirements.txt
    cp .env.example .env   # заполнить BOT_TOKEN и MASTER_KEY
    python bot.py
"""
import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import BOT_TOKEN, validate_config
from app.db import init as db_init
from app.handlers import setup_routers
from app.middlewares import ThrottlingMiddleware


async def main() -> None:
    problems = validate_config()
    if problems:
        print("⚠️  Проблемы конфигурации (см. .env и .env.example):")
        for problem in problems:
            print("  •", problem)
        sys.exit(1)

    await db_init()

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())
    dp.include_router(setup_routers())

    print("✅ Бот запущен. Остановка: Ctrl+C")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
