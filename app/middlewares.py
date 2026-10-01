"""Глобальный анти-флуд (middleware на сообщения и кнопки).

Лимиты на пользователя:
  • 25 сообщений / 60 сек
  • 20 нажатий кнопок / 60 сек
  • 3 нарушения за 10 минут -> мут 5 минут (пишется в базу, живёт перезапуски)

Администратор не ограничивается. Забаненные/мьюченные обновления отбрасываются
до хендлеров, чтобы флуд не нагружал логику.
"""
import time

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject

from . import config
from .db import execute, fetchone
from .i18n import t
from .security import MuteTracker, RateLimiter

MSG_LIMIT = 25   # сообщений в минуту
CB_LIMIT = 20    # нажатий кнопок в минуту
WINDOW = 60.0


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self.limiter = RateLimiter()
        self.mutes = MuteTracker()
        self._last_note: dict[int, float] = {}  # анти-спам уведомлений о муте

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = data.get("event_from_user")
        if user is None or user.is_bot or user.id == config.ADMIN_ID:
            return await handler(event, data)

        tg = user.id

        # 1) Проверяем постоянный мут в базе (переживает перезапуск бота).
        row = await fetchone("SELECT muted_until, lang FROM users WHERE tg=?", (tg,))
        now = time.time()
        muted_until = (row["muted_until"] or 0) if row else 0
        if muted_until > now:
            await self._notify(event, tg, t("muted", row["lang"], min=int((muted_until - now) // 60) + 1))
            return

        # 2) Скользящее окно лимитов.
        if isinstance(event, CallbackQuery):
            ok, wait = await self.limiter.check(f"cb:{tg}", CB_LIMIT, WINDOW)
        else:
            ok, wait = await self.limiter.check(f"msg:{tg}", MSG_LIMIT, WINDOW)
        if not ok:
            lang = row["lang"] if row else "ru"
            mute = self.mutes.strike(f"strike:{tg}")
            if mute > 0:
                # Пишем мут в базу (переживает перезапуск бота).
                await execute(
                    "UPDATE users SET muted_until=? WHERE tg=?", (time.time() + mute, tg)
                )
                await self._notify(event, tg, t("muted_on", lang))
            else:
                await self._notify(event, tg, t("flood", lang, sec=wait))
            return

        return await handler(event, data)

    async def _notify(self, event: TelegramObject, tg: int, text: str) -> None:
        """Одно уведомление о муте не чаще, чем раз в 15 секунд."""
        now = time.monotonic()
        if now - self._last_note.get(tg, 0.0) < 15:
            return
        self._last_note[tg] = now
        try:
            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            else:
                await event.answer(text)
        except Exception:
            pass
