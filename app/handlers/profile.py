"""Анкета: создание и редактирование с жёсткой валидацией, просмотр, удаление.

Все текстовые поля очищаются (app.security.clean_text) и проверяются по длине.
Личные поля сохраняются в базу ТОЛЬКО в зашифрованном виде (AES-256-GCM).
"""
from html import escape

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from .. import security
from ..db import decrypt_profile, execute, get_profile, user_lang
from ..i18n import t
from ..keyboards import action_of, main_menu, photo_kb, profile_kb, text_action

r = Router()


class Form(StatesGroup):
    name = State()
    age = State()
    city = State()
    about = State()
    interests = State()
    photo = State()


def card_html(p: dict) -> str:
    """Карточка анкеты в HTML (все данные экранированы)."""
    parts = [f"<b>{escape(p['name'])}, {p['age']}</b>"]
    if p["city"]:
        parts.append(f"📍 {escape(p['city'])}")
    if p["about"]:
        parts.append("")
        parts.append(escape(p["about"]))
    if p["interests"]:
        parts.append("")
        parts.append(f"<i>{escape(p['interests'])}</i>")
    parts.append("")
    parts.append(f"🆔 #{p['id']}")
    return "\n".join(parts)


async def start_wizard(m: Message, state: FSMContext) -> None:
    lang = await user_lang(m.from_user.id)
    await state.set_state(Form.name)
    await m.answer(t("w_name", lang))


async def _save(m: Message, state: FSMContext, photo: str | None) -> None:
    d = await state.get_data()
    box = security.get_box()
    await execute(
        """INSERT INTO profiles(tg,name,age,city,about,interests,photo,hidden)
           VALUES(?,?,?,?,?,?,?,0)
           ON CONFLICT(tg) DO UPDATE SET
             name=excluded.name, age=excluded.age, city=excluded.city,
             about=excluded.about, interests=excluded.interests,
             photo=excluded.photo, hidden=0""",
        (
            m.from_user.id,
            box.encrypt(d["name"]),
            d["age"],
            box.encrypt(d["city"]),
            box.encrypt(d["about"]),
            box.encrypt(d["interests"]),
            box.encrypt(photo),
        ),
    )
    await state.clear()
    lang = await user_lang(m.from_user.id)
    await m.answer(t("p_saved", lang), reply_markup=main_menu(lang))


# ------------------------------------------------------------ меню анкеты

@r.message(text_action("profile"), StateFilter(None))
async def my_profile(m: Message, state: FSMContext) -> None:
    lang = await user_lang(m.from_user.id)
    row = await get_profile(m.from_user.id)
    if row:
        p = decrypt_profile(row)
        await m.answer(card_html(p), parse_mode="HTML", reply_markup=profile_kb(lang))
    else:
        await start_wizard(m, state)


@r.message(text_action("edit"), StateFilter(None))
async def edit_profile(m: Message, state: FSMContext) -> None:
    await start_wizard(m, state)


@r.message(text_action("delete"), StateFilter(None))
async def delete_profile(m: Message) -> None:
    lang = await user_lang(m.from_user.id)
    await execute("DELETE FROM profiles WHERE tg=?", (m.from_user.id,))
    await m.answer(t("deleted", lang), reply_markup=main_menu(lang))


# ------------------------------------------------------------ мастер анкеты

@r.message(Form.name)
async def f_name(m: Message, state: FSMContext) -> None:
    lang = await user_lang(m.from_user.id)
    if not m.text:
        return await m.answer(t("w_text_only", lang))
    name = security.clean_text(m.text, 40)
    if not security.valid_name(name):
        return await m.answer(t("w_name_bad", lang))
    await state.update_data(name=name)
    await state.set_state(Form.age)
    await m.answer(t("w_age", lang))


@r.message(Form.age)
async def f_age(m: Message, state: FSMContext) -> None:
    lang = await user_lang(m.from_user.id)
    if not m.text:
        return await m.answer(t("w_text_only", lang))
    if not security.valid_age(m.text.strip()):
        return await m.answer(t("w_age_bad", lang))
    await state.update_data(age=int(m.text.strip()))
    await state.set_state(Form.city)
    await m.answer(t("w_city", lang))


@r.message(Form.city)
async def f_city(m: Message, state: FSMContext) -> None:
    lang = await user_lang(m.from_user.id)
    if not m.text:
        return await m.answer(t("w_text_only", lang))
    city = security.clean_text(m.text, 60)
    if not security.valid_city(city):
        return await m.answer(t("w_city_bad", lang))
    await state.update_data(city=city)
    await state.set_state(Form.about)
    await m.answer(t("w_about", lang))


@r.message(Form.about)
async def f_about(m: Message, state: FSMContext) -> None:
    lang = await user_lang(m.from_user.id)
    if not m.text:
        return await m.answer(t("w_text_only", lang))
    about = security.clean_text(m.text, 400)
    await state.update_data(about=about)
    await state.set_state(Form.interests)
    await m.answer(t("w_interests", lang))


@r.message(Form.interests)
async def f_interests(m: Message, state: FSMContext) -> None:
    lang = await user_lang(m.from_user.id)
    if not m.text:
        return await m.answer(t("w_text_only", lang))
    interests = security.clean_text(m.text, 200)
    await state.update_data(interests=interests)
    await state.set_state(Form.photo)
    await m.answer(t("w_photo", lang), reply_markup=photo_kb(lang))


@r.message(Form.photo, F.photo)
async def f_photo(m: Message, state: FSMContext) -> None:
    # Берём максимальный размер фото; file_id шифруем вместе с остальными полями.
    await _save(m, state, m.photo[-1].file_id)


@r.message(Form.photo, F.text)
async def f_photo_text(m: Message, state: FSMContext) -> None:

    lang = await user_lang(m.from_user.id)
    if action_of(m.text) == "skip_photo":
        return await _save(m, state, None)
    await m.answer(t("w_photo_bad", lang))


@r.message(Form.photo)
async def f_photo_other(m: Message) -> None:
    lang = await user_lang(m.from_user.id)
    await m.answer(t("w_photo_bad", lang))
