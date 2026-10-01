"""Клавиатуры и двуязычные метки кнопок.

Кнопки главного меню существуют в двух вариантах (ru/en). Фильтр text_action()
узнаёт нажатую кнопку по её тексту на любом из языков.
"""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from .i18n import t

# action -> (текст ru, текст en)
MENU_LABELS: dict[str, tuple[str, str]] = {
    "browse": ("🔎 Смотреть", "🔎 Browse"),
    "dialogs": ("💬 Диалоги", "💬 Chats"),
    "profile": ("📝 Моя анкета", "📝 My profile"),
    "settings": ("⚙️ Настройки", "⚙️ Settings"),
    "back": ("🔙 В меню", "🔙 Menu"),
    "edit": ("✏️ Изменить анкету", "✏️ Edit profile"),
    "delete": ("🗑 Удалить анкету", "🗑 Delete profile"),
    "hide": ("🙈 Скрыть анкету", "🙈 Hide profile"),
    "unhide": ("👁 Показать анкету", "👁 Unhide profile"),
    "lang": ("🌐 Язык", "🌐 Language"),
    "gdpr": ("🧨 Удалить мои данные", "🧨 Delete my data"),
    "skip_photo": ("⏭ Без фото", "⏭ No photo"),
    # админ-панель
    "adm_stats": ("📊 Статистика", "📊 Stats"),
    "adm_reports": ("🚩 Жалобы", "🚩 Reports"),
    "adm_find": ("🔍 Найти", "🔍 Find"),
    "adm_del": ("🗑 Удалить по ID", "🗑 Delete by ID"),
    "adm_ban": ("⛔ Бан", "⛔ Ban"),
    "adm_unban": ("✅ Разбан", "✅ Unban"),
    "adm_rep": ("⭐ Репутация", "⭐ Reputation"),
    "adm_audit": ("🧾 Аудит", "🧾 Audit"),
}


def label(action: str, lang: str = "ru") -> str:
    ru, en = MENU_LABELS[action]
    return ru if lang == "ru" else en


def action_of(text: str | None) -> str | None:
    """Какой кнопке соответствует текст (на любом языке)."""
    if not text:
        return None
    for action, (ru, en) in MENU_LABELS.items():
        if text == ru or text == en:
            return action
    return None


def text_action(*actions: str):
    """Фильтр aiogram: сообщение совпадает с одной из кнопок."""

    def filter_(message: Message) -> bool:
        return action_of(message.text) in actions

    return filter_


# ------------------------------------------------------------ reply-клавиатуры

def _reply(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text) for text in row] for row in rows],
        resize_keyboard=True,
    )


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    return _reply([
        [label("browse", lang), label("dialogs", lang)],
        [label("profile", lang), label("settings", lang)],
    ])


def profile_kb(lang: str) -> ReplyKeyboardMarkup:
    return _reply([
        [label("edit", lang), label("delete", lang)],
        [label("back", lang)],
    ])


def settings_kb(lang: str, hidden: bool = False) -> ReplyKeyboardMarkup:
    visibility = label("unhide" if hidden else "hide", lang)
    return _reply([
        [label("lang", lang), visibility],
        [label("gdpr", lang)],
        [label("back", lang)],
    ])


def photo_kb(lang: str) -> ReplyKeyboardMarkup:
    return _reply([[label("skip_photo", lang)], [label("back", lang)]])


def admin_kb() -> ReplyKeyboardMarkup:
    return _reply([
        [label("adm_stats"), label("adm_reports")],
        [label("adm_find"), label("adm_del")],
        [label("adm_ban"), label("adm_unban")],
        [label("adm_rep"), label("adm_audit")],
        [label("back")],
    ])


# ----------------------------------------------------------- inline-клавиатуры

def _inline(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
            for row in rows
        ]
    )


def lang_kb() -> InlineKeyboardMarkup:
    return _inline([[("🇷🇺 Русский", "lang:ru")], [("🇬🇧 English", "lang:en")]])


def agree_kb(lang: str) -> InlineKeyboardMarkup:
    return _inline([[(t("agree_btn", lang), "agree")]])


def actions_kb(to_tg: int, lang: str) -> InlineKeyboardMarkup:
    return _inline([
        [("❤️", f"like:{to_tg}"), ("➡️", f"skip:{to_tg}"), ("🚩", f"rep:{to_tg}")],
    ])


REPORT_REASONS = ("spam", "abuse", "nsfw", "fake", "other")


def report_kb(to_tg: int, lang: str) -> InlineKeyboardMarkup:
    return _inline([
        [(t(f"rep_{code}", lang), f"repdo:{to_tg}:{code}") for code in REPORT_REASONS],
        [("↩️", "noop")],
    ])


def open_chat_kb(match_id: int, lang: str) -> InlineKeyboardMarkup:
    return _inline([[(t("open_chat", lang), f"chat:{match_id}")]])


def dialog_list_kb(items: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    return _inline([[(f"👤 {name}", f"chat:{mid}")] for mid, name in items])


def chat_controls_kb(match_id: int, lang: str) -> InlineKeyboardMarkup:
    return _inline([
        [(t("chat_exit_btn", lang), f"chatend:{match_id}"),
         (t("chat_report_btn", lang), f"chatrep:{match_id}")],
        [(t("chat_block_btn", lang), f"chatblock:{match_id}")],
    ])


def chat_reply_kb(match_id: int, lang: str) -> InlineKeyboardMarkup:
    return _inline([[(t("chat_reply_btn", lang), f"chat:{match_id}")]])


def admin_report_kb(to_tg: int, report_id: int) -> InlineKeyboardMarkup:
    return _inline([
        [(t("adm_ban_btn", "ru"), f"aban:{to_tg}:{report_id}")],
        [(t("adm_dismiss_btn", "ru"), f"adis:{report_id}")],
    ])


def gdpr_confirm_kb(lang: str) -> InlineKeyboardMarkup:
    return _inline([[(t("gdpr_yes", lang), "gdpr:yes")], [(t("gdpr_no", lang), "gdpr:no")]])


# ---------------------------------------------------------------- UI-хелпер

async def show_menu(message: Message, lang: str, text: str | None = None) -> None:
    """Показать главное меню (и сбросить клавиатуру на основную)."""
    await message.answer(text or t("menu_hint", lang), reply_markup=main_menu(lang))
