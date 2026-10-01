"""Сборка всех роутеров.

Порядок критичен (первый подошедший хендлер выигрывает):
  1. onboarding — /start, /help, /cancel, «🔙 В меню» (работают из любого состояния)
  2. chat       — пересылка сообщений в активном диалоге + его кнопки
  3. admin      — админские состояния и кнопки
  4. profile    — мастер анкеты
  5. browse     — лента анкет
  6. settings   — настройки + фолбэк на неизвестный текст
"""
from aiogram import Router

from . import admin, browse, chat, onboarding, profile, settings


def setup_routers() -> Router:
    root = Router(name="root")
    root.include_routers(
        onboarding.r,
        chat.r,
        admin.r,
        profile.r,
        browse.r,
        settings.r,
    )
    return root
