"""Поиск: лента анкет, лайк / пропуск / жалоба, взаимный мэтч.

Лента исключает: себя, скрытые и забаненные анкеты, уже просмотренных,
а также всех, кто связан блокировкой (в любую сторону).
"""
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message

from .. import config
from ..db import decrypt_profile, execute, fetchone, get_profile, user_lang
from ..i18n import t
from ..keyboards import (
    REPORT_REASONS,
    actions_kb,
    admin_report_kb,
    main_menu,
    open_chat_kb,
    report_kb,
    text_action,
)
from ..security import RateLimiter
from .profile import card_html

r = Router()

feed_limit = RateLimiter()  # 10 запросов ленты в минуту


async def next_profile(tg: int):
    return await fetchone(
        """
        SELECT p.* FROM profiles p JOIN users u ON u.tg = p.tg
        WHERE p.tg <> ?
          AND p.hidden = 0
          AND u.banned = 0
          AND u.accepted = 1
          AND p.tg NOT IN (SELECT to_tg FROM likes WHERE from_tg = ?)
          AND p.tg NOT IN (SELECT to_tg FROM blocks WHERE from_tg = ?)
          AND p.tg NOT IN (SELECT from_tg FROM blocks WHERE to_tg = ?)
        ORDER BY RANDOM() LIMIT 1
        """,
        (tg, tg, tg, tg),
    )


async def blocked_between(a: int, b: int) -> bool:
    row = await fetchone(
        "SELECT 1 FROM blocks WHERE (from_tg=? AND to_tg=?) OR (from_tg=? AND to_tg=?)",
        (a, b, b, a),
    )
    return row is not None


async def file_report(bot: Bot | None, from_tg: int, to_tg: int, reason: str) -> bool:
    """Регистрирует жалобу. При 5+ новых жалобах — автобан нарушителя.
    Возвращает True, если сработал автобан."""
    rid = await execute(
        "INSERT INTO reports(from_tg,to_tg,reason) VALUES(?,?,?)",
        (from_tg, to_tg, reason),
    )
    row = await fetchone(
        "SELECT COUNT(*) AS n FROM reports WHERE to_tg=? AND status='new'", (to_tg,)
    )
    auto = bool(row and row["n"] >= 5)
    if auto:
        await execute(
            "UPDATE users SET banned=1, ban_reason='auto: 5+ жалоб' WHERE tg=?", (to_tg,)
        )
        await execute("UPDATE matches SET active=0 WHERE a=? OR b=?", (to_tg, to_tg))
    if bot is not None:
        lang = await user_lang(config.ADMIN_ID)
        try:
            await bot.send_message(
                config.ADMIN_ID,
                t("adm_report_msg", lang, rid=rid, frm=from_tg, to=to_tg, reason=escape(reason))
                + (t("adm_auto_ban", lang) if auto else ""),
                parse_mode="HTML",
                reply_markup=admin_report_kb(to_tg, rid),
            )
        except Exception:
            pass  # админ мог остановить бота — не роняем логику
    return auto


# ------------------------------------------------------------ лента

@r.message(text_action("browse"), StateFilter(None))
async def browse(m: Message) -> None:
    me = m.from_user.id
    lang = await user_lang(me)

    me_profile = await get_profile(me)
    if not me_profile:
        return await m.answer(t("need_profile", lang), reply_markup=main_menu(lang))

    ok, wait = await feed_limit.check(f"feed:{me}", 10, 60.0)
    if not ok:
        return await m.answer(t("slow", lang, sec=wait))

    row = await next_profile(me)
    if not row:
        return await m.answer(t("no_profiles", lang))

    p = decrypt_profile(row)
    if p["photo"]:
        await m.answer_photo(
            p["photo"], caption=card_html(p), parse_mode="HTML", reply_markup=actions_kb(row["tg"], lang)
        )
    else:
        await m.answer(card_html(p), parse_mode="HTML", reply_markup=actions_kb(row["tg"], lang))


# ------------------------------------------------------- лайк / пропуск

@r.callback_query(F.data.startswith(("like:", "skip:")))
async def like_skip(c: CallbackQuery) -> None:
    kind, _, raw_tg = c.data.partition(":")
    to_tg = int(raw_tg)
    me = c.from_user.id
    lang = await user_lang(me)

    if not await blocked_between(me, to_tg):
        await execute(
            "INSERT OR IGNORE INTO likes(from_tg,to_tg,kind) VALUES(?,?,?)", (me, to_tg, kind)
        )

    if kind == "like" and not await blocked_between(me, to_tg):
        back = await fetchone(
            "SELECT 1 FROM likes WHERE from_tg=? AND to_tg=? AND kind='like'", (to_tg, me)
        )
        if back:
            # Взаимный лайк -> мэтч и приватный диалог.
            match_id = await execute("INSERT INTO matches(a,b) VALUES(?,?)", (me, to_tg))
            await execute("UPDATE users SET rep=rep+1 WHERE tg IN (?,?)", (me, to_tg))
            my_p = decrypt_profile(await get_profile(me))
            other_p = decrypt_profile(await get_profile(to_tg))
            my_name = my_p["name"] if my_p else "—"
            other_name = other_p["name"] if other_p else "—"
            other_lang = await user_lang(to_tg)
            for uid, ulang, name in (
                (me, lang, other_name),
                (to_tg, other_lang, my_name),
            ):
                try:
                    await c.bot.send_message(
                        uid,
                        t("mutual", ulang, name=escape(name)),
                        parse_mode="HTML",
                        reply_markup=open_chat_kb(match_id, ulang),
                    )
                except Exception:
                    pass

    try:
        await c.message.delete()
    except Exception:
        pass
    try:
        await c.answer(t("done", lang))
    except Exception:
        pass


# ------------------------------------------------------------ жалобы

@r.callback_query(F.data.startswith("repdo:"))
async def report_do(c: CallbackQuery) -> None:
    _, raw_tg, code = c.data.split(":", 2)
    to_tg = int(raw_tg)
    lang = await user_lang(c.from_user.id)
    if code not in REPORT_REASONS:
        return
    await file_report(c.bot, c.from_user.id, to_tg, t(f"rep_{code}", lang))
    try:
        await c.message.delete()
    except Exception:
        pass
    try:
        await c.answer(t("rep_saved", lang))
    except Exception:
        pass


@r.callback_query(F.data == "noop")
async def noop(c: CallbackQuery) -> None:
    try:
        await c.answer()
    except Exception:
        pass


@r.callback_query(F.data.startswith("rep:"))
async def report_choose(c: CallbackQuery) -> None:
    # Важно: регистрируется ПОСЛЕ repdo, чтобы не перехватывать его данные.
    to_tg = int(c.data.split(":", 1)[1])
    lang = await user_lang(c.from_user.id)
    try:
        await c.message.edit_reply_markup(reply_markup=report_kb(to_tg, lang))
    except Exception:
        pass
    try:
        await c.answer()
    except Exception:
        pass
