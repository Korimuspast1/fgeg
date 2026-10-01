"""Вход в систему: /start, выбор языка, правила и согласие, /help, выход в меню.

Порядок регистрации хендлеров здесь важен: эти хендлеры срабатывают раньше
состояний (анкета, диалог, админка), поэтому /start, /cancel и «🔙 В меню»
работают из любого места бота.
"""
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..db import ensure_user, execute, fetchone, user_lang
from ..i18n import t
from ..keyboards import agree_kb, show_menu, text_action

r = Router()


@r.message(CommandStart())
async def start(m: Message, state: FSMContext) -> None:
    await state.clear()
    user = await ensure_user(m.from_user.id)
    lang = user["lang"] or "ru"
    if user["banned"]:
        await m.answer(t("banned", lang))
        return
    if not user["accepted"]:
        await m.answer(t("hello", lang))
        await m.answer(t("rules", lang), parse_mode="HTML", reply_markup=agree_kb(lang))
        return
    profile = await fetchone("SELECT id FROM profiles WHERE tg=?", (m.from_user.id,))
    if not profile:
        from .profile import start_wizard
        await start_wizard(m, state)
        return
    await show_menu(m, lang)


@r.callback_query(F.data.startswith("lang:"))
async def set_lang(c: CallbackQuery, state: FSMContext) -> None:
    lang = c.data.split(":", 1)[1]
    if lang not in ("ru", "en"):
        return
    await state.clear()
    user = await ensure_user(c.from_user.id)
    if user["banned"]:
        return
    await execute("UPDATE users SET lang=? WHERE tg=?", (lang, c.from_user.id))
    try:
        await c.answer()
    except Exception:
        pass
    if not user["accepted"]:
        await c.message.answer(t("hello", lang))
        await c.message.answer(t("rules", lang), parse_mode="HTML", reply_markup=agree_kb(lang))
    else:
        await show_menu(c.message, lang, t("lang_set", lang))


@r.callback_query(F.data == "agree")
async def agreed(c: CallbackQuery, state: FSMContext) -> None:
    user = await ensure_user(c.from_user.id)
    lang = user["lang"] or "ru"
    if user["banned"]:
        return
    await execute("UPDATE users SET accepted=1 WHERE tg=?", (c.from_user.id,))
    try:
        await c.answer()
    except Exception:
        pass
    await c.message.answer(t("welcome", lang))
    from .profile import start_wizard
    await start_wizard(c.message, state)


@r.callback_query(F.data == "menu")
async def cb_menu(c: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    lang = await user_lang(c.from_user.id)
    await show_menu(c.message, lang)
    try:
        await c.answer()
    except Exception:
        pass


@r.message(Command("help"))
async def help_cmd(m: Message) -> None:
    lang = await user_lang(m.from_user.id)
    await m.answer(t("help", lang), parse_mode="HTML")


@r.message(Command("cancel"))
async def cancel_cmd(m: Message, state: FSMContext) -> None:
    await state.clear()
    lang = await user_lang(m.from_user.id)
    await show_menu(m, lang, t("cancelled", lang))


@r.message(text_action("back"))
async def back_to_menu(m: Message, state: FSMContext) -> None:
    """«🔙 В меню» работает в любом состоянии: выходит из анкеты/диалога/админки."""
    await state.clear()
    lang = await user_lang(m.from_user.id)
    await show_menu(m, lang, t("cancelled", lang))
