"""Интеграционный тест: полный путь пользователя «от входа до конца».

Эмулирует Telegram через FakeBot и запускает настоящие хендлеры:
  /start → язык → правила → анкета → лента → лайки → взаимный мэтч →
  анонимный диалог (пересылка сообщений) → завершение → удаление данных.

Запуск:  python tests/test_flow.py
"""
import asyncio
import os
import random
import sys
import tempfile
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

os.environ["MASTER_KEY"] = "flow-test-master-key-0123456789"
os.environ["BOT_TOKEN"] = "123456:TESTTOKEN"
os.environ["ADMIN_ID"] = "1398491942"
TMP = tempfile.mkdtemp(prefix="fgeg-flow-")
os.environ["DB_PATH"] = os.path.join(TMP, "flow.sqlite3")

from aiogram.fsm.context import FSMContext  # noqa: E402
from aiogram.fsm.storage.base import StorageKey  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from aiogram.types import CallbackQuery, Chat, Message, PhotoSize, User  # noqa: E402

from app.db import fetchone, init  # noqa: E402
from app.handlers.browse import browse, like_skip  # noqa: E402
from app.handlers.chat import dialogues, end_chat, open_chat, relay_text  # noqa: E402
from app.handlers.onboarding import agreed, set_lang, start  # noqa: E402
from app.handlers.profile import (  # noqa: E402
    f_about,
    f_age,
    f_city,
    f_interests,
    f_name,
    f_photo_text,
)
from app.handlers.settings import gdpr_delete  # noqa: E402

FAILED: list[str] = []


def check(name: str, cond: bool) -> None:
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}")
    if not cond:
        FAILED.append(name)


class FakeBot:
    """Двойник бота: и как aiogram-эмиттер (__call__), и как прямой Bot API."""

    def __init__(self) -> None:
        self.id = 999999
        self.sent: list[tuple[int, str]] = []

    async def __call__(self, method) -> None:
        name = type(method).__name__
        if name == "SendMessage":
            self.sent.append((method.chat_id, method.text or ""))
        elif name == "SendPhoto":
            self.sent.append((method.chat_id, f"[фото] {(method.caption or '')}".strip()))
        return None

    # Прямые вызовы из хендлеров (c.bot.send_message / m.bot.send_photo).
    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text or ""))
        return None

    async def send_photo(self, chat_id, photo, caption=None, **kwargs):
        self.sent.append((chat_id, f"[фото] {caption or ''}".strip()))
        return None

    def texts_to(self, uid: int) -> list[str]:
        return [text for to, text in self.sent if to == uid]


BOT = FakeBot()
STORAGE = MemoryStorage()
_mid = random.randint(1, 10**6)


def make_message(uid: int, text: str | None = None, photo: str | None = None, caption: str | None = None) -> Message:
    global _mid
    _mid += 1
    msg = Message(
        message_id=_mid,
        date=datetime.now(timezone.utc),
        chat=Chat(id=uid, type="private"),
        from_user=User(id=uid, is_bot=False, first_name=f"User{uid}"),
        text=text,
        caption=caption,
        photo=[PhotoSize(file_id=photo, file_unique_id="u", width=100, height=100)] if photo else None,
    )
    msg.as_(BOT)
    return msg


def make_callback(uid: int, data: str, message: Message | None = None) -> CallbackQuery:
    cb = CallbackQuery(
        id=str(_mid),
        from_user=User(id=uid, is_bot=False, first_name=f"User{uid}"),
        chat_instance="test",
        data=data,
        message=message or make_message(uid),
    )
    cb.as_(BOT)
    return cb


def fsm(uid: int) -> FSMContext:
    return FSMContext(storage=STORAGE, key=StorageKey(bot_id=BOT.id, chat_id=uid, user_id=uid))


async def onboard(uid: int, name: str, age: int) -> None:
    """Полный вход: старт → язык → правила → анкета."""
    await start(make_message(uid, "/start"), fsm(uid))
    await set_lang(make_callback(uid, "lang:ru"), fsm(uid))
    await agreed(make_callback(uid, "agree"), fsm(uid))
    state = fsm(uid)
    await f_name(make_message(uid, name), state)
    await f_age(make_message(uid, str(age)), state)
    await f_city(make_message(uid, "Москва"), state)
    await f_about(make_message(uid, "люблю прогулки"), state)
    await f_interests(make_message(uid, "музыка, кино"), state)
    await f_photo_text(make_message(uid, "⏭ Без фото"), state)


async def main() -> None:
    print("Подготовка базы:")
    await init()

    print("Вход двух пользователей и создание анкет:")
    await onboard(111, "Аня", 25)
    await onboard(555, "Даша", 26)
    u = await fetchone("SELECT accepted, lang FROM users WHERE tg=111")
    check("пользователь принял правила, язык ru", u["accepted"] == 1 and u["lang"] == "ru")
    p = await fetchone("SELECT name, age FROM profiles WHERE tg=111")
    check("анкета сохранена (зашифрована)", p["age"] == 25 and p["name"] != "Аня")

    print("Валидация анкеты:")
    state_bad = fsm(777)
    await start(make_message(777, "/start"), state_bad)
    await set_lang(make_callback(777, "lang:ru"), state_bad)
    await agreed(make_callback(777, "agree"), state_bad)
    await f_name(make_message(777, "А"), state_bad)   # слишком короткое имя
    check("короткое имя отклонено", "2" in BOT.texts_to(777)[-1])
    await f_name(make_message(777, "<b>Хакер</b>"), state_bad)
    row = await fetchone("SELECT name FROM profiles WHERE tg=777")
    check("анкеты ещё нет (мастер не завершён)", row is None)

    print("Лента и лайки:")
    await browse(make_message(111, "🔎 Смотреть"))
    check("Аня видит анкету Даши", any("Даша" in text for text in BOT.texts_to(111)))
    await like_skip(make_callback(111, "like:555", make_message(111, "x")))
    await browse(make_message(555, "🔎 Смотреть"))
    check("Даша видит анкету Ани", any("Аня" in text for text in BOT.texts_to(555)))
    await like_skip(make_callback(555, "like:111", make_message(555, "x")))

    check("Аня получила уведомление о мэтче", any("взаимная симпатия" in text.lower() for text in BOT.texts_to(111)))
    check("Даша получила уведомление о мэтче", any("взаимная симпатия" in text.lower() for text in BOT.texts_to(555)))
    match = await fetchone("SELECT * FROM matches WHERE (a=111 AND b=555) OR (a=555 AND b=111)")
    check("мэтч создан", match is not None and match["active"] == 1)

    print("Анонимный диалог:")
    mid = match["id"]
    await open_chat(make_callback(111, f"chat:{mid}"), fsm(111))
    await open_chat(make_callback(555, f"chat:{mid}"), fsm(555))
    BOT.sent.clear()
    await relay_text(make_message(111, "Привет, Даша! <script>"), fsm(111))
    to_dasha = BOT.texts_to(555)
    check("сообщение доставлено Даше", len(to_dasha) == 1 and "Привет, Даша!" in to_dasha[0])
    check("HTML собеседника экранирован", "&lt;script&gt;" in to_dasha[0])
    check("Telegram ID Ани не раскрыт", "111" not in to_dasha[0])
    await relay_text(make_message(555, "Привет!"), fsm(555))
    check("ответ доставлен Ане", any("Привет!" in text for text in BOT.texts_to(111)))

    # Блокируем флуд: 20 сообщений в минуту уже исчерпаны частично, добьём лимит.
    BOT.sent.clear()
    for i in range(25):
        await relay_text(make_message(111, f"флуд {i}"), fsm(111))
    delivered = len(BOT.texts_to(555))
    check("флуд в диалоге ограничен (доставлено < 30)", delivered <= 20)

    print("Завершение диалога:")
    BOT.sent.clear()
    await end_chat(make_callback(111, f"chatend:{mid}"), fsm(111))
    check("Даша уведомлена о завершении", any("завершил" in text for text in BOT.texts_to(555)))
    match = await fetchone("SELECT active FROM matches WHERE id=?", (mid,))
    check("диалог закрыт в базе", match["active"] == 0)

    print("Список диалогов после завершения:")
    await dialogues(make_message(555, "💬 Диалоги"))
    check("активных диалогов нет", any("пока нет" in text.lower() for text in BOT.texts_to(555)))

    print("Полное удаление данных (право на забвение):")
    await gdpr_delete(make_callback(111, "gdpr:yes"), fsm(111))
    check("анкета удалена", await fetchone("SELECT 1 FROM profiles WHERE tg=111") is None)
    check("лайки удалены", await fetchone("SELECT 1 FROM likes WHERE from_tg=111 OR to_tg=111") is None)
    check("мэтчи удалены", await fetchone("SELECT 1 FROM matches WHERE a=111 OR b=111") is None)

    print()
    if FAILED:
        print(f"❌ Провалено: {len(FAILED)}")
        for name in FAILED:
            print("   -", name)
        sys.exit(1)
    print("✅ Полный путь «от входа до конца» работает.")


if __name__ == "__main__":
    asyncio.run(main())
