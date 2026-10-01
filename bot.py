"""«Дайвинчик 2.0» — безопасная система знакомств «от входа до конца».

Полный путь пользователя: вход → язык → правила 18+ → анкета → поиск →
взаимный лайк → анонимный приватный диалог (сообщения не хранятся).

Запуск локально:
    pip install -r requirements.txt
    cp .env.example .env   # заполнить BOT_TOKEN и MASTER_KEY
    python bot.py

На хостинге (Render и др.): переменные окружения BOT_TOKEN / MASTER_KEY /
ADMIN_ID задаются в панели хостинга; при наличии PORT автоматически
поднимается health-check сервер, который хостинг использует для проверки.
"""
import asyncio
import os
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import BOT_TOKEN, validate_config
from app.db import init as db_init
from app.handlers import setup_routers
from app.middlewares import ThrottlingMiddleware


async def _health_server() -> None:
    """Мини HTTP-сервер для хостингов, требующих открытый порт (Render и др.).

    Запускается только если задана переменная окружения PORT.
    """
    port = int(os.getenv("PORT", "0") or 0)
    if not port:
        return

    async def ok(_request):
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/", ok)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"✅ Health-check сервер на порту {port}")


async def main() -> None:
    problems = validate_config()
    if problems:
        print("⚠️  Проблемы конфигурации (переменные окружения / .env):")
        for problem in problems:
            print("  •", problem)
        sys.exit(1)

    await db_init()
    await _health_server()

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
