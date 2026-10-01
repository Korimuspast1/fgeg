"""Двуязычные строки интерфейса (ru / en).

t('ключ', lang, **подстановки) — если перевода нет, берётся русский.
Тексты могут содержать HTML-теги: отправлять с parse_mode='HTML',
а пользовательские данные перед подстановкой экранировать (html.escape).
"""

T: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------ общий вход
    "choose_lang": {
        "ru": "Выбери язык 🌐",
        "en": "Choose language 🌐",
    },
    "hello": {
        "ru": "Привет! 👋 Это знакомства с защитой приватности: анкеты хранятся "
              "в зашифрованном виде, а общение — анонимное.",
        "en": "Hi! 👋 Privacy-first dating: profiles are stored encrypted "
              "and chats are anonymous.",
    },
    "rules": {
        "ru": "📜 <b>Правила и согласие</b>\n\n"
              "• Мне 18 лет или больше\n"
              "• Уважение к людям: без оскорблений, спама и навязчивости\n"
              "• Без фейков и чужих фото\n"
              "• Контент 18+ запрещён\n"
              "• Один человек — одна анкета\n\n"
              "Продолжая, ты подтверждаешь, что тебе 18+, согласен с правилами "
              "и с хранением анкеты в зашифрованном виде.",
        "en": "📜 <b>Rules and consent</b>\n\n"
              "• I am 18 or older\n"
              "• Respect people: no abuse, spam or harassment\n"
              "• No fakes or other people's photos\n"
              "• NSFW content is forbidden\n"
              "• One person — one profile\n\n"
              "By continuing you confirm you are 18+, accept the rules "
              "and encrypted storage of your profile.",
    },
    "agree_btn": {"ru": "✅ Принимаю правила", "en": "✅ I accept the rules"},
    "welcome": {
        "ru": "Отлично! Создай анкету — это твой вход в систему. "
              "Собеседники увидят только её, без твоего Telegram ID.",
        "en": "Great! Create your profile — it is your entrance to the system. "
              "Others will only see the profile, not your Telegram ID.",
    },
    "menu_hint": {"ru": "Главное меню. Выбирай действие 👇", "en": "Main menu. Pick an action 👇"},
    "banned": {"ru": "⛔ Доступ ограничен.", "en": "⛔ Access restricted."},
    "cancelled": {"ru": "Ок, возвращаемся в меню.", "en": "OK, back to the menu."},
    "help": {
        "ru": "🛡 <b>Как это работает</b>\n\n"
              "1. Создай анкету: 📝 Моя анкета\n"
              "2. Смотри анкеты: 🔎 Смотреть, ставь ❤️\n"
              "3. При взаимном лайке откроется приватный диалог — собеседник "
              "не узнает твой Telegram ID\n"
              "4. Сообщения передаются напрямую и на сервере не хранятся\n\n"
              "🔒 Анкеты в базе зашифрованы (AES-256-GCM)\n"
              "🚫 Флуд ограничен, жалобы уходят модерации\n\n"
              "Команды: /start, /help, /cancel",
        "en": "🛡 <b>How it works</b>\n\n"
              "1. Create a profile: 📝 My profile\n"
              "2. Browse: 🔎 Browse and send ❤️\n"
              "3. On a mutual like a private chat opens — the other person "
              "never sees your Telegram ID\n"
              "4. Messages are relayed directly and never stored on the server\n\n"
              "🔒 Profiles are encrypted in the database (AES-256-GCM)\n"
              "🚫 Flooding is limited, reports go to moderation\n\n"
              "Commands: /start, /help, /cancel",
    },
    # ------------------------------------------------------------ анкета
    "w_name": {"ru": "Как тебя зовут? (2–40 символов)", "en": "What is your name? (2–40 chars)"},
    "w_name_bad": {"ru": "Имя — от 2 до 40 символов. Попробуй ещё раз.", "en": "Name must be 2–40 characters. Try again."},
    "w_age": {"ru": "Сколько тебе лет? (18+)", "en": "How old are you? (18+)"},
    "w_age_bad": {"ru": "Возраст — число от 18 до 99.", "en": "Age is a number from 18 to 99."},
    "w_city": {"ru": "Из какого ты города?", "en": "What city are you from?"},
    "w_city_bad": {"ru": "Город — от 2 до 60 символов.", "en": "City — 2 to 60 characters."},
    "w_about": {"ru": "Пара фраз о себе (до 400 символов).", "en": "A few words about you (up to 400 characters)."},
    "w_interests": {"ru": "Твои интересы (до 200 символов).", "en": "Your interests (up to 200 characters)."},
    "w_photo": {
        "ru": "Пришли фото для анкеты или нажми «⏭ Без фото».",
        "en": "Send a photo for your profile or tap «⏭ No photo».",
    },
    "w_photo_bad": {
        "ru": "Пришли фото (кнопка 📎 → «Фото») или нажми «⏭ Без фото».",
        "en": "Send a photo (📎 → Photo) or tap «⏭ No photo».",
    },
    "w_text_only": {"ru": "Отправь ответ текстом 🙂", "en": "Send your answer as text 🙂"},
    "p_saved": {"ru": "Анкета готова ✨", "en": "Profile saved ✨"},
    "deleted": {
        "ru": "Анкета удалена. В любой момент можно создать новую.",
        "en": "Profile deleted. You can create a new one anytime.",
    },
    "need_profile": {
        "ru": "Сначала создай анкету — так честно и безопасно 🙂",
        "en": "First create your profile — fair and safe 🙂",
    },
    "no_profiles": {"ru": "Пока новых анкет нет. Загляни позже 🙂", "en": "No new profiles yet. Come back later 🙂"},
    "done": {"ru": "Готово", "en": "Done"},
    "slow": {"ru": "Не так быстро 🙂 Подожди {sec} сек.", "en": "Not so fast 🙂 Wait {sec} sec."},
    # ------------------------------------------------------------ мэтч и диалоги
    "mutual": {
        "ru": "💞 Взаимная симпатия с <b>{name}</b>! Открой диалог — "
              "твой Telegram ID останется скрытым.",
        "en": "💞 Mutual like with <b>{name}</b>! Open the chat — "
              "your Telegram ID stays hidden.",
    },
    "open_chat": {"ru": "💬 Открыть диалог", "en": "💬 Open chat"},
    "dialogs_title": {"ru": "Твои диалоги. Нажми на имя 👇", "en": "Your chats. Tap a name 👇"},
    "dialogs_empty": {
        "ru": "Диалогов пока нет. Ставь ❤️ — при взаимном лайке откроется чат 😉",
        "en": "No chats yet. Send ❤️ — a chat opens on a mutual like 😉",
    },
    "chat_opened": {
        "ru": "💬 Диалог с <b>{name}</b>. Пиши — передам собеседнику. Фото тоже можно.",
        "en": "💬 Chat with <b>{name}</b>. Write — I will deliver. Photos work too.",
    },
    "chat_exit_btn": {"ru": "⏹ Завершить", "en": "⏹ End chat"},
    "chat_report_btn": {"ru": "🚩 Пожаловаться", "en": "🚩 Report"},
    "chat_block_btn": {"ru": "⛔ Заблокировать", "en": "⛔ Block"},
    "chat_reply_btn": {"ru": "💬 Ответить", "en": "💬 Reply"},
    "chat_ended_you": {"ru": "Диалог завершён.", "en": "Chat ended."},
    "chat_ended_bye": {"ru": "Собеседник завершил диалог.", "en": "The other person ended the chat."},
    "chat_block_done": {
        "ru": "⛔ Собеседник заблокирован: он не увидит твою анкету и не сможет написать.",
        "en": "⛔ User blocked: they will not see your profile or write to you.",
    },
    "chat_closed": {"ru": "Этот диалог уже завершён.", "en": "This chat is already closed."},
    "relay_prefix": {"ru": "💌 <b>{name}</b>:", "en": "💌 <b>{name}</b>:"},
    "relay_photo": {"ru": "📸 от <b>{name}</b>", "en": "📸 from <b>{name}</b>"},
    "chat_only_media": {
        "ru": "В диалоге можно отправлять только текст и фото.",
        "en": "Only text and photos can be sent in this chat.",
    },
    # ------------------------------------------------------------ жалобы
    "rep_choose": {"ru": "Укажи причину жалобы:", "en": "Choose a report reason:"},
    "like_btn": {"ru": "❤️ Нравится", "en": "❤️ Like"},
    "skip_btn": {"ru": "➡️ Дальше", "en": "➡️ Next"},
    "rep_btn": {"ru": "🚩 Пожаловаться", "en": "🚩 Report"},
    "rep_spam": {"ru": "Спам / реклама", "en": "Spam / ads"},
    "rep_abuse": {"ru": "Оскорбления", "en": "Abuse"},
    "rep_nsfw": {"ru": "18+ контент", "en": "NSFW content"},
    "rep_fake": {"ru": "Фейк / обман", "en": "Fake / scam"},
    "rep_other": {"ru": "Другое", "en": "Other"},
    "rep_saved": {"ru": "Жалоба отправлена модерации. Спасибо!", "en": "Report sent to moderation. Thank you!"},
    "rep_text_ask": {
        "ru": "Опиши проблему одним сообщением (до 300 символов).",
        "en": "Describe the problem in one message (up to 300 characters).",
    },
    "rep_text_saved": {
        "ru": "Жалоба отправлена. Продолжай диалог: 💬 Диалоги → выбрать собеседника.",
        "en": "Report sent. Continue the chat: 💬 Chats → pick the person.",
    },
    # ------------------------------------------------------------ настройки
    "set_title": {"ru": "⚙️ Настройки", "en": "⚙️ Settings"},
    "set_rep": {"ru": "⭐ Твоя репутация: {rep}", "en": "⭐ Your reputation: {rep}"},
    "set_hidden": {"ru": "Анкета скрыта — её не видно в поиске.", "en": "Profile hidden — not visible in search."},
    "set_visible": {"ru": "Анкета снова видна в поиске.", "en": "Profile is visible in search again."},
    "set_gdpr_ask": {
        "ru": "🧨 Удалить ВСЕ твои данные: анкету, лайки, диалоги и историю? "
              "Это необратимо.",
        "en": "🧨 Delete ALL your data: profile, likes, chats and history? "
              "This cannot be undone.",
    },
    "gdpr_yes": {"ru": "Да, удалить всё", "en": "Yes, delete everything"},
    "gdpr_no": {"ru": "Отмена", "en": "Cancel"},
    "set_gdpr_done": {
        "ru": "Все данные удалены. Будем рады видеть тебя снова!",
        "en": "All data deleted. Hope to see you again!",
    },
    "lang_set": {"ru": "Язык установлен: русский 🇷🇺", "en": "Language set: English 🇬🇧"},
    # ------------------------------------------------------------ флуд
    "flood": {"ru": "Слишком часто! Подожди {sec} сек 🙂", "en": "Too fast! Wait {sec} sec 🙂"},
    "muted": {"ru": "⛔ Ты в муте за флуд ещё {min} мин.", "en": "⛔ You are muted for flooding for {min} more min."},
    "muted_on": {"ru": "⛔ Слишком много нарушений — мут на 5 минут.", "en": "⛔ Too many violations — muted for 5 minutes."},
    "unknown": {
        "ru": "Не понял 🙈 Используй кнопки меню или /help",
        "en": "Did not get that 🙈 Use the menu buttons or /help",
    },
    # ------------------------------------------------------------ админка
    "adm_panel": {"ru": "🛡 Админ-панель", "en": "🛡 Admin panel"},
    "adm_stats": {
        "ru": "📊 <b>Статистика</b>\n👤 Пользователей: {users}\n📝 Анкет: {profiles}\n"
              "💞 Мэтчей: {matches} (активных: {active})\n🚩 Новых жалоб: {reports}\n"
              "⛔ Забанено: {banned}",
        "en": "📊 <b>Stats</b>\n👤 Users: {users}\n📝 Profiles: {profiles}\n"
              "💞 Matches: {matches} (active: {active})\n🚩 New reports: {reports}\n"
              "⛔ Banned: {banned}",
    },
    "adm_ask_num": {
        "ru": "Отправь число: ID анкеты или Telegram ID. /cancel — отмена.",
        "en": "Send a number: profile ID or Telegram ID. /cancel to abort.",
    },
    "adm_ask_delta": {
        "ru": "Отправь изменение репутации, например +1 или -2.",
        "en": "Send a reputation change, e.g. +1 or -2.",
    },
    "adm_not_found": {"ru": "Не найдено.", "en": "Not found."},
    "adm_deleted": {"ru": "Удалено.", "en": "Deleted."},
    "adm_banned": {"ru": "Заблокирован.", "en": "Banned."},
    "adm_unbanned": {"ru": "Разблокирован.", "en": "Unbanned."},
    "adm_rep_done": {"ru": "Репутация обновлена.", "en": "Reputation updated."},
    "adm_self_ban": {"ru": "Нельзя забанить самого себя 🙂", "en": "You cannot ban yourself 🙂"},
    "adm_reports_empty": {"ru": "Новых жалоб нет.", "en": "No new reports."},
    "adm_audit_title": {"ru": "🧾 Последние действия:", "en": "🧾 Recent actions:"},
    "adm_audit_empty": {"ru": "Аудит пуст.", "en": "Audit log is empty."},
    "adm_report_msg": {
        "ru": "🚩 <b>Жалоба #{rid}</b>\nОт: {frm}\nНа: {to}\nПричина: {reason}",
        "en": "🚩 <b>Report #{rid}</b>\nFrom: {frm}\nOn: {to}\nReason: {reason}",
    },
    "adm_auto_ban": {"ru": "\n🤖 Автобан: 5+ жалоб.", "en": "\n🤖 Auto-ban: 5+ reports."},
    "adm_ban_btn": {"ru": "⛔ Забанить", "en": "⛔ Ban"},
    "adm_dismiss_btn": {"ru": "✅ Отклонить", "en": "✅ Dismiss"},
}


def t(key: str, lang: str = "ru", **fmt) -> str:
    """Строка интерфейса на языке пользователя (fallback — русский)."""
    entry = T.get(key)
    if not entry:
        return key
    text = entry.get(lang) or entry.get("ru") or key
    return text.format(**fmt) if fmt else text
