"""Настройки: язык, видимость анкеты, репутация, полное удаление данных."""
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..db import ensure_user, execute, fetchone, get_profile, user_lang
from ..i18n import t
from ..keyboards import (
    gdpr_confirm_kb,
    lang_kb,
    settings_kb,
    show_menu,
    text_action,
)

r = Router()


@r.message(text_action("settings"), StateFilter(None))
async def settings(m: Message) -> None:
    me = m.from_user.id
    lang = await user_lang(me)
    row = await fetchone("SELECT rep FROM users WHERE tg=?", (me,))
    profile = await get_profile(me)
    hidden = bool(profile and profile["hidden"])
    await m.answer(
        f"{t('set_title', lang)}\n{t('set_rep', lang, rep=row['rep'] if row else 0)}",
        reply_markup=settings_kb(lang, hidden),
    )


@r.message(text_action("lang"), StateFilter(None))
async def change_lang(m: Message) -> None:
    await m.answer(t("choose_lang", "ru"), reply_markup=lang_kb())


@r.message(text_action("hide"), StateFilter(None))
async def hide_profile(m: Message) -> None:
    me = m.from_user.id
    lang = await user_lang(me)
    await execute("UPDATE profiles SET hidden=1 WHERE tg=?", (me,))
    await m.answer(t("set_hidden", lang), reply_markup=settings_kb(lang, hidden=True))


@r.message(text_action("unhide"), StateFilter(None))
async def unhide_profile(m: Message) -> None:
    me = m.from_user.id
    lang = await user_lang(me)
    await execute("UPDATE profiles SET hidden=0 WHERE tg=?", (me,))
    await m.answer(t("set_visible", lang), reply_markup=settings_kb(lang, hidden=False))


@r.message(text_action("gdpr"), StateFilter(None))
async def gdpr_ask(m: Message) -> None:
    lang = await user_lang(m.from_user.id)
    await m.answer(t("set_gdpr_ask", lang), reply_markup=gdpr_confirm_kb(lang))


@r.callback_query(F.data == "gdpr:yes")
async def gdpr_delete(c: CallbackQuery, state: FSMContext) -> None:
    """Полное удаление всех данных пользователя (право на забвение)."""
    me = c.from_user.id
    lang = await user_lang(me)
    await state.clear()
    await execute("DELETE FROM profiles WHERE tg=?", (me,))
    await execute("DELETE FROM likes WHERE from_tg=? OR to_tg=?", (me, me))
    await execute("DELETE FROM matches WHERE a=? OR b=?", (me, me))
    await execute("DELETE FROM users WHERE tg=?", (me,))
    # Пересоздаём чистую строку: пользователь заново проходит вход
    # (язык, правила, анкета) — как будто впервые.
    await ensure_user(me)
    try:
        await c.answer()
    except Exception:
        pass
    await c.message.answer(t("set_gdpr_done", lang), reply_markup=lang_kb())


@r.callback_query(F.data == "gdpr:no")
async def gdpr_cancel(c: CallbackQuery, state: FSMContext) -> None:
    lang = await user_lang(c.from_user.id)
    await state.clear()
    try:
        await c.answer()
    except Exception:
        pass
    await show_menu(c.message, lang)


# Фолбэк: неизвестный текст без состояния -> подсказка.
# Зарегистрирован последним во всём боте (см. handlers/__init__.py).
@r.message(StateFilter(None))
async def unknown(m: Message) -> None:
    lang = await user_lang(m.from_user.id)
    await m.answer(t("unknown", lang))
