"""Приватные диалоги после взаимного лайка — финальный этап системы.

Принципы приватности:
  • стороны не знают Telegram ID друг друга — только имена из анкет;
  • сообщения передаются напрямую и НИГДЕ не хранятся (в базе только факт
    существования диалога);
  • любой участник может завершить диалог или заблокировать собеседника;
  • лимит 20 сообщений в минуту.
"""
from html import escape

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery, Message

from .. import security
from ..db import decrypt_profile, execute, fetchall, fetchone, get_profile, user_lang
from ..i18n import t
from ..keyboards import (
    action_of,
    chat_controls_kb,
    chat_reply_kb,
    dialog_list_kb,
    main_menu,
    show_menu,
    text_action,
)
from ..security import RateLimiter
from .browse import blocked_between, file_report
from .profile import card_html

r = Router()

relay_limit = RateLimiter()  # 20 сообщений диалога в минуту


class ChatStates(StatesGroup):
    active = State()
    report = State()


def _other(row, me: int) -> int:
    return row["b"] if row["a"] == me else row["a"]


async def _get_match(match_id: int):
    return await fetchone("SELECT * FROM matches WHERE id=?", (match_id,))


async def _clear_partner_state(state: FSMContext, bot_id: int, partner: int, match_id: int) -> None:
    """Если собеседник сейчас в этом же диалоге — выходим из его состояния."""
    try:
        partner_state = FSMContext(
            storage=state.storage,
            key=StorageKey(bot_id=bot_id, chat_id=partner, user_id=partner),
        )
        data = await partner_state.get_data()
        if data.get("match_id") == match_id:
            await partner_state.clear()
    except Exception:
        pass


# ------------------------------------------------------------ список диалогов

@r.message(text_action("dialogs"), StateFilter(None))
async def dialogues(m: Message) -> None:
    me = m.from_user.id
    lang = await user_lang(me)
    rows = await fetchall(
        "SELECT * FROM matches WHERE active=1 AND (a=? OR b=?) ORDER BY id DESC LIMIT 10",
        (me, me),
    )
    if not rows:
        return await m.answer(t("dialogs_empty", lang))
    items: list[tuple[int, str]] = []
    for row in rows:
        p = decrypt_profile(await get_profile(_other(row, me)))
        items.append((row["id"], p["name"] if p else "—"))
    await m.answer(t("dialogs_title", lang), reply_markup=dialog_list_kb(items))


@r.callback_query(F.data.startswith("chat:"))
async def open_chat(c: CallbackQuery, state: FSMContext) -> None:
    match_id = int(c.data.split(":", 1)[1])
    me = c.from_user.id
    lang = await user_lang(me)
    row = await _get_match(match_id)
    if not row or row["active"] != 1 or me not in (row["a"], row["b"]):
        return await _alert(c, t("chat_closed", lang))
    partner = _other(row, me)
    p = decrypt_profile(await get_profile(partner))
    name = p["name"] if p else "—"
    await state.set_state(ChatStates.active)
    await state.update_data(match_id=match_id, partner=partner)
    header = t("chat_opened", lang, name=escape(name))
    if p:
        header += "\n\n" + card_html(p)
    try:
        await c.message.answer(header, parse_mode="HTML", reply_markup=chat_controls_kb(match_id, lang))
    except Exception:
        pass
    try:
        await c.answer()
    except Exception:
        pass


# ------------------------------------------------------------ пересылка

@r.message(ChatStates.active, F.text)
async def relay_text(m: Message, state: FSMContext) -> None:
    if action_of(m.text) is not None:
        # Нажата кнопка меню — выходим из диалога в главное меню.
        await state.clear()
        lang = await user_lang(m.from_user.id)
        return await show_menu(m, lang)
    if m.text.startswith("/"):
        # Неизвестные команды не пересылаем собеседнику.
        lang = await user_lang(m.from_user.id)
        return await m.answer(t("unknown", lang))
    await _relay(m, state, text=security.clean_text(m.text, 3500))


@r.message(ChatStates.active, F.photo)
async def relay_photo(m: Message, state: FSMContext) -> None:
    caption = security.clean_text(m.caption or "", 900)
    await _relay(m, state, text=caption, photo=m.photo[-1].file_id)


@r.message(ChatStates.active)
async def relay_other(m: Message) -> None:
    lang = await user_lang(m.from_user.id)
    await m.answer(t("chat_only_media", lang))


async def _relay(m: Message, state: FSMContext, text: str, photo: str | None = None) -> None:
    me = m.from_user.id
    lang = await user_lang(me)
    data = await state.get_data()
    match_id = data.get("match_id")

    ok, wait = await relay_limit.check(f"relay:{me}", 20, 60.0)
    if not ok:
        return await m.answer(t("slow", lang, sec=wait))

    row = await _get_match(match_id) if match_id else None
    if not row or row["active"] != 1 or await blocked_between(me, _other(row, me)):
        await state.clear()
        return await m.answer(t("chat_closed", lang), reply_markup=main_menu(lang))

    partner = _other(row, me)
    my_p = decrypt_profile(await get_profile(me))
    my_name = my_p["name"] if my_p else "—"
    plang = await user_lang(partner)

    try:
        if photo:
            caption = t("relay_photo", plang, name=escape(my_name))
            if text:
                caption += ":\n" + escape(text)
            await m.bot.send_photo(
                partner, photo, caption=caption[:1000],
                parse_mode="HTML", reply_markup=chat_reply_kb(match_id, plang),
            )
        elif text:
            await m.bot.send_message(
                partner,
                t("relay_prefix", plang, name=escape(my_name)) + " " + escape(text),
                parse_mode="HTML",
                reply_markup=chat_reply_kb(match_id, plang),
            )
        else:
            return await m.answer(t("chat_only_media", lang))
    except Exception:
        # Собеседник мог заблокировать бота — считаем диалог закрытым.
        await state.clear()
        return await m.answer(t("chat_closed", lang), reply_markup=main_menu(lang))


# ------------------------------------------------- завершение / блок / жалоба

@r.callback_query(F.data.startswith("chatend:"))
async def end_chat(c: CallbackQuery, state: FSMContext) -> None:
    match_id = int(c.data.split(":", 1)[1])
    me = c.from_user.id
    lang = await user_lang(me)
    row = await _get_match(match_id)
    if not row or row["active"] != 1 or me not in (row["a"], row["b"]):
        return await _alert(c, t("chat_closed", lang))
    await execute("UPDATE matches SET active=0 WHERE id=?", (match_id,))
    partner = _other(row, me)
    await _clear_partner_state(state, c.bot.id, partner, match_id)
    try:
        await c.bot.send_message(partner, t("chat_ended_bye", await user_lang(partner)))
    except Exception:
        pass
    try:
        await c.message.delete()
    except Exception:
        pass
    await _alert(c, t("chat_ended_you", lang))


@r.callback_query(F.data.startswith("chatblock:"))
async def block_chat(c: CallbackQuery, state: FSMContext) -> None:
    match_id = int(c.data.split(":", 1)[1])
    me = c.from_user.id
    lang = await user_lang(me)
    row = await _get_match(match_id)
    if not row or row["active"] != 1 or me not in (row["a"], row["b"]):
        return await _alert(c, t("chat_closed", lang))
    partner = _other(row, me)
    await execute("UPDATE matches SET active=0 WHERE id=?", (match_id,))
    await execute("INSERT OR IGNORE INTO blocks(from_tg,to_tg) VALUES(?,?)", (me, partner))
    await _clear_partner_state(state, c.bot.id, partner, match_id)
    try:
        await c.bot.send_message(partner, t("chat_ended_bye", await user_lang(partner)))
    except Exception:
        pass
    try:
        await c.message.delete()
    except Exception:
        pass
    await _alert(c, t("chat_block_done", lang))


@r.callback_query(F.data.startswith("chatrep:"))
async def chat_report(c: CallbackQuery, state: FSMContext) -> None:
    match_id = int(c.data.split(":", 1)[1])
    me = c.from_user.id
    lang = await user_lang(me)
    row = await _get_match(match_id)
    if not row or me not in (row["a"], row["b"]):
        return await _alert(c, t("chat_closed", lang))
    await state.set_state(ChatStates.report)
    await state.update_data(match_id=match_id, partner=_other(row, me))
    try:
        await c.message.answer(t("rep_text_ask", lang))
    except Exception:
        pass
    try:
        await c.answer()
    except Exception:
        pass


@r.message(ChatStates.report, F.text)
async def chat_report_text(m: Message, state: FSMContext) -> None:
    lang = await user_lang(m.from_user.id)
    d = await state.get_data()
    reason = security.clean_text(m.text, 300)
    if not reason:
        return await m.answer(t("rep_text_ask", lang))
    await file_report(m.bot, m.from_user.id, d["partner"], reason)
    # Возвращаем пользователя в открытый диалог.
    await state.set_state(ChatStates.active)
    await state.update_data(match_id=d["match_id"], partner=d["partner"])
    await m.answer(t("rep_text_saved", lang))


async def _alert(c: CallbackQuery, text: str) -> None:
    try:
        await c.answer(text, show_alert=True)
    except Exception:
        pass
