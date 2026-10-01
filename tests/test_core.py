"""Быстрые тесты ядра безопасности и данных.

Запуск:  python tests/test_core.py
Проверяет: шифрование, валидацию, лимиты, схему/миграции БД,
ленту анкет, автобан по жалобам, сборку роутеров.
"""
import asyncio
import os
import sqlite3
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

# Окружение теста — ДО импорта приложения.
os.environ["MASTER_KEY"] = "unit-test-master-key-0123456789"
os.environ["BOT_TOKEN"] = "123456:TESTTOKEN"
os.environ["ADMIN_ID"] = "1398491942"
TMP = tempfile.mkdtemp(prefix="fgeg-test-")
os.environ["DB_PATH"] = os.path.join(TMP, "t1.sqlite3")

from app import config, security  # noqa: E402
from app.db import (  # noqa: E402
    decrypt_profile,
    ensure_user,
    execute,
    fetchall,
    fetchone,
    init,
)
from app.handlers import setup_routers  # noqa: E402
from app.handlers.browse import file_report, next_profile  # noqa: E402

FAILED: list[str] = []


def check(name: str, cond: bool) -> None:
    status = "OK " if cond else "FAIL"
    print(f"  [{status}] {name}")
    if not cond:
        FAILED.append(name)


class DummyBot:
    """Бот-заглушка: send_message всегда падает (файл_report не должен упасть)."""

    async def send_message(self, *args, **kwargs):
        raise RuntimeError("no bot in tests")


def test_crypto():
    print("Шифрование AES-256-GCM:")
    box = security.get_box()
    secret = 'Привет, <b>мир</b> & "кавычки" \n перенос'
    blob = box.encrypt(secret)
    check("круглый путь", box.decrypt(blob) == secret)
    check("None остаётся None", box.encrypt(None) is None and box.decrypt(None) is None)
    check("подмена обнаружена", box.decrypt(blob[:-4] + "AAAA") is None)
    check("nonce уникален (два шифра различаются)", box.encrypt("x") != box.encrypt("x"))
    raw = box.encrypt("Аня")
    check("в базе нет открытого текста", "Аня" not in raw)
    key2 = security.CryptoBox(security.derive_key("другой-ключ-0123456789abcdef"))
    check("другой ключ не расшифрует", key2.decrypt(blob) is None)


def test_validation():
    print("Валидация ввода:")
    check("контрольные символы удалены", security.clean_text("a\x00b\x1fc\nd", 100) == "abc\nd")
    check("обрезка по длине", len(security.clean_text("x" * 500, 40)) == 40)
    check("trim", security.clean_text("  hi  ", 10) == "hi")
    check("имя ок", security.valid_name("Аня"))
    check("имя слишком короткое", not security.valid_name("А"))
    check("возраст ок", security.valid_age("25"))
    check("возраст несовершеннолетний", not security.valid_age("17"))
    check("возраст не число", not security.valid_age("abc"))


async def test_ratelimit():
    print("Анти-флуд:")
    rl = security.RateLimiter()
    results = [await rl.check("k", 3, 60) for _ in range(4)]
    check("первые 3 события разрешены", all(ok for ok, _ in results[:3]))
    check("4-е заблокировано", results[3][0] is False and results[3][1] > 0)
    ok, _ = await rl.check("other", 3, 60)
    check("другой ключ не задет", ok)
    mt = security.MuteTracker(max_strikes=2, window=60, duration=300)
    check("первое нарушение без мута", mt.strike("u") == 0)
    check("второе даёт мут 300 сек", mt.strike("u") == 300)
    check("мьют активен", mt.remaining("u") > 0)
    check("другой пользователь чист", mt.remaining("v") == 0)


async def test_db_and_feed():
    print("База данных и лента:")
    await init()
    await ensure_user(111)
    await ensure_user(555)
    box = security.get_box()

    async def add_profile(tg, name, age, hidden=0, banned=0, accepted=1):
        await ensure_user(tg)
        if banned:
            await execute("UPDATE users SET banned=1 WHERE tg=?", (tg,))
        await execute("UPDATE users SET accepted=? WHERE tg=?", (accepted, tg))
        await execute(
            "INSERT INTO profiles(tg,name,age,city,about,interests,photo,hidden)"
            " VALUES(?,?,?,?,?,?,?,?)"
            " ON CONFLICT(tg) DO UPDATE SET hidden=excluded.hidden",
            (tg, box.encrypt(name), age, box.encrypt("Город"), box.encrypt("о себе"),
             box.encrypt("интересы"), None, hidden),
        )

    await add_profile(111, "Аня", 25)
    await add_profile(222, "Борис", 30, banned=1)      # забанен — не показываем
    await add_profile(333, "Вера", 28, hidden=1)       # скрыл анкету — не показываем
    await add_profile(444, "Гоша", 22)                 # уже лайкнут — не показываем
    await add_profile(666, "Ева", 27, accepted=0)      # не принял правила
    await add_profile(555, "Даша", 26)                 # должен остаться в ленте

    await execute("INSERT INTO likes(from_tg,to_tg,kind) VALUES(111,444,'like')")

    row = await next_profile(111)
    check("лента исключает бан/скрытые/лайкнутых/не принявших", row and row["tg"] == 555)

    await execute("INSERT INTO blocks(from_tg,to_tg) VALUES(555,111)")  # Даша блокирует Аню
    row = await next_profile(111)
    check("лента исключает блокировщика", row is None)

    raw = await fetchone("SELECT name FROM profiles WHERE tg=111")
    check("имя в базе зашифровано", raw["name"] != "Аня")
    p = decrypt_profile(await fetchone("SELECT * FROM profiles WHERE tg=111"))
    check("анкета расшифровывается", p["name"] == "Аня" and p["age"] == 25)

    # взаимный лайк -> мэтч
    await execute("INSERT INTO likes(from_tg,to_tg,kind) VALUES(555,111,'like')")
    row = await fetchone("SELECT * FROM likes WHERE from_tg=555 AND to_tg=111 AND kind='like'")
    check("обратный лайк зафиксирован", row is not None)


async def test_reports_autoban():
    print("Жалобы и автобан:")
    await execute("DELETE FROM reports WHERE to_tg=777")
    await ensure_user(777)
    auto = False
    for _ in range(5):
        auto = await file_report(DummyBot(), 111, 777, "спам")
    check("после 5 жалоб — автобан", auto is True)
    row = await fetchone("SELECT banned, ban_reason FROM users WHERE tg=777")
    check("пользователь забанен с причиной", row["banned"] == 1 and "жалоб" in row["ban_reason"])
    count = await fetchone("SELECT COUNT(*) n FROM reports WHERE to_tg=777 AND status='new'")
    check("жалобы зарегистрированы", count["n"] == 5)


async def test_migration():
    print("Миграция старой базы:")
    config.DB_PATH = os.path.join(TMP, "t2.sqlite3")
    con = sqlite3.connect(config.DB_PATH)
    con.execute("CREATE TABLE likes(from_tg INTEGER, to_tg INTEGER, UNIQUE(from_tg,to_tg))")
    con.execute(
        "CREATE TABLE users(tg INTEGER PRIMARY KEY, lang TEXT DEFAULT 'ru',"
        " accepted INTEGER DEFAULT 0, banned INTEGER DEFAULT 0, rep INTEGER DEFAULT 0)"
    )
    con.commit()
    con.close()
    await init()  # должна добавить недостающие колонки и новые таблицы
    likes_cols = {row[1] for row in await fetchall("PRAGMA table_info(likes)")}
    users_cols = {row[1] for row in await fetchall("PRAGMA table_info(users)")}
    check("likes.kind добавлен", "kind" in likes_cols)
    check("users.muted_until добавлен", "muted_until" in users_cols)
    check("users.ban_reason добавлен", "ban_reason" in users_cols)
    tables = {row[0] for row in await fetchall("SELECT name FROM sqlite_master WHERE type='table'")}
    check("новые таблицы созданы", {"matches", "blocks", "audit"} <= tables)


def test_routers():
    print("Сборка роутеров:")
    router = setup_routers()
    check("роутеры собираются без ошибок", router is not None)


async def main() -> None:
    test_crypto()
    test_validation()
    await test_ratelimit()
    await test_db_and_feed()
    await test_reports_autoban()
    await test_migration()
    test_routers()
    print()
    if FAILED:
        print(f"❌ Провалено проверок: {len(FAILED)}")
        for name in FAILED:
            print("   -", name)
        sys.exit(1)
    print("✅ Все проверки пройдены.")


if __name__ == "__main__":
    asyncio.run(main())
