"""Админ-панель: статистика, очередь жалоб, модерация, аудит.

Каждое действие администратора записывается в журнал аудита (таблица audit).
Проверка прав — по Telegram ID из .env; действия с числами идут через FSM,
поэтому обычные пользователи не могут вызвать их «вслепую».
"""
import re
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import config
from ..db import decrypt_profile, execute, fetchall, fetchone
from ..i18n import t
from ..keyboards import action_of, admin_kb, admin_report_kb, text_action
from .profile import card_html

r = Router()


class AdminStates(StatesGroup):
    number = State()
    rep_delta = State()


def is_admin(tg: int) -> bool:
    return tg == config.ADMIN_ID


async def audit(admin_tg: int, action: str, target, details: str = "") -> None:
    await execute(
        "INSERT INTO audit(admin_tg,action,target,details) VALUES(?,?,?,?)",
        (admin_tg, action, str(target), details),
    )


async def ban_user(tg: int, reason: str) -> None:
    await execute("UPDATE users SET banned=1, ban_reason=? WHERE tg=?", (reason, tg))
    await execute("UPDATE matches SET active=0 WHERE a=? OR b=?", (tg, tg))


@r.message(Command("admin"))
async def admin_panel(m: Message, state: FSMContext) -> None:
    if not is_admin(m.from_user.id):
        return
    await state.clear()
    await m.answer(t("adm_panel", "ru"), reply_markup=admin_kb())


# ------------------------------------------------------------ мгновенные отчёты

@r.message(text_action("adm_stats"), StateFilter(None))
async def adm_stats(m: Message) -> None:
    if not is_admin(m.from_user.id):
        return
    async def count(sql: str) -> int:
        row = await fetchone(sql)
        return row["n"] if row else 0

    users = await count("SELECT COUNT(*) n FROM users")
    profiles = await count("SELECT COUNT(*) n FROM profiles WHERE hidden=0")
    matches = await count("SELECT COUNT(*) n FROM matches")
    active = await count("SELECT COUNT(*) n FROM matches WHERE active=1")
    reports = await count("SELECT COUNT(*) n FROM reports WHERE status='new'")
    banned = await count("SELECT COUNT(*) n FROM users WHERE banned=1")
    await m.answer(
        t("adm_stats", "ru", users=users, profiles=profiles, matches=matches,
          active=active, reports=reports, banned=banned),
        parse_mode="HTML",
    )


@r.message(text_action("adm_reports"), StateFilter(None))
async def adm_reports(m: Message) -> None:
    if not is_admin(m.from_user.id):
        return
    rows = await fetchall(
        "SELECT * FROM reports WHERE status='new' ORDER BY id DESC LIMIT 5"
    )
    if not rows:
        return await m.answer(t("adm_reports_empty", "ru"))
    for row in rows:
        await m.answer(
            t("adm_report_msg", "ru", rid=row["id"], frm=row["from_tg"],
              to=row["to_tg"], reason=escape(row["reason"] or "—")),
            parse_mode="HTML",
            reply_markup=admin_report_kb(row["to_tg"], row["id"]),
        )


@r.message(text_action("adm_audit"), StateFilter(None))
async def adm_audit(m: Message) -> None:
    if not is_admin(m.from_user.id):
        return
    rows = await fetchall("SELECT * FROM audit ORDER BY id DESC LIMIT 10")
    if not rows:
        return await m.answer(t("adm_audit_empty", "ru"))
    lines = [t("adm_audit_title", "ru")]
    for row in rows:
        lines.append(
            f"#{row['id']} · {row['created']} · {row['action']} → {row['target']}"
            + (f" ({row['details']})" if row["details"] else "")
        )
    await m.answer("\n".join(lines))


# ------------------------------------------------------------ действия с числом

NUM_ACTIONS = {"adm_find", "adm_del", "adm_ban", "adm_unban", "adm_rep"}


@r.message(text_action(*NUM_ACTIONS), StateFilter(None))
async def adm_ask_number(m: Message, state: FSMContext) -> None:

    if not is_admin(m.from_user.id):
        return
    action = action_of(m.text)
    await state.set_state(AdminStates.number)
    await state.update_data(action=action)
    await m.answer(t("adm_ask_num", "ru"))


@r.message(AdminStates.number, F.text)
async def adm_number(m: Message, state: FSMContext) -> None:
    if not is_admin(m.from_user.id):
        await state.clear()
        return
    if not re.fullmatch(r"\d{1,12}", m.text.strip()):
        return await m.answer(t("adm_ask_num", "ru"))
    n = int(m.text.strip())
    d = await state.get_data()
    action = d.get("action")
    me = m.from_user.id

    if action == "adm_find":
        row = await fetchone("SELECT * FROM profiles WHERE id=? OR tg=?", (n, n))
        p = decrypt_profile(row)
        await m.answer(card_html(p) if p else t("adm_not_found", "ru"), parse_mode="HTML")

    elif action == "adm_del":
        await execute("DELETE FROM profiles WHERE id=? OR tg=?", (n, n))
        await audit(me, "delete_profile", n)
        await m.answer(t("adm_deleted", "ru"))

    elif action == "adm_ban":
        if n == config.ADMIN_ID:
            return await m.answer(t("adm_self_ban", "ru"))
        await ban_user(n, "admin")
        await audit(me, "ban", n)
        await m.answer(t("adm_banned", "ru"))

    elif action == "adm_unban":
        await execute("UPDATE users SET banned=0, ban_reason=NULL WHERE tg=?", (n,))
        await audit(me, "unban", n)
        await m.answer(t("adm_unbanned", "ru"))

    elif action == "adm_rep":
        await state.set_state(AdminStates.rep_delta)
        await state.update_data(target=n)
        return await m.answer(t("adm_ask_delta", "ru"))

    await state.clear()


@r.message(AdminStates.rep_delta, F.text)
async def adm_rep_delta(m: Message, state: FSMContext) -> None:
    if not is_admin(m.from_user.id):
        await state.clear()
        return
    if not re.fullmatch(r"[+-]?\d{1,3}", m.text.strip()):
        return await m.answer(t("adm_ask_delta", "ru"))
    delta = int(m.text.strip())
    d = await state.get_data()
    target = d.get("target")
    await execute("UPDATE users SET rep=rep+? WHERE tg=?", (delta, target))
    await audit(m.from_user.id, "rep", target, f"{delta:+d}")
    await state.clear()
    await m.answer(t("adm_rep_done", "ru"))


# ------------------------------------------------------------ кнопки в жалобах

@r.callback_query(F.data.startswith("aban:"))
async def adm_ban_cb(c: CallbackQuery) -> None:
    if not is_admin(c.from_user.id):
        return
    _, raw_tg, raw_rid = c.data.split(":", 2)
    tg, rid = int(raw_tg), int(raw_rid)
    if tg == config.ADMIN_ID:
        return
    await ban_user(tg, f"admin: жалоба #{rid}")
    await execute("UPDATE reports SET status='handled' WHERE to_tg=? AND status='new'", (tg,))
    await audit(c.from_user.id, "ban", tg, f"жалоба #{rid}")
    try:
        await c.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    try:
        await c.answer(t("adm_banned", "ru"))
    except Exception:
        pass


@r.callback_query(F.data.startswith("adis:"))
async def adm_dismiss_cb(c: CallbackQuery) -> None:
    if not is_admin(c.from_user.id):
        return
    rid = int(c.data.split(":", 1)[1])
    await execute("UPDATE reports SET status='dismissed' WHERE id=?", (rid,))
    await audit(c.from_user.id, "dismiss_report", rid)
    try:
        await c.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    try:
        await c.answer(t("adm_deleted", "ru"))
    except Exception:
        pass
