"""Слой данных: SQLite (aiosqlite).

- Все запросы параметризованы (?) — защита от SQL-инъекций.
- Личные поля анкет пишутся только в зашифрованном виде (см. app.security).
- init() создаёт схему и мягко мигрирует базы старой версии бота.
"""
import aiosqlite

from . import config
from .security import get_box

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS users(
        tg INTEGER PRIMARY KEY,
        lang TEXT DEFAULT 'ru',
        accepted INTEGER DEFAULT 0,
        banned INTEGER DEFAULT 0,
        ban_reason TEXT,
        rep INTEGER DEFAULT 0,
        muted_until REAL DEFAULT 0,
        created TEXT DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS profiles(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg INTEGER UNIQUE,
        name TEXT,           -- зашифровано AES-256-GCM
        age INTEGER,
        city TEXT,           -- зашифровано
        about TEXT,          -- зашифровано
        interests TEXT,      -- зашифровано
        photo TEXT,          -- зашифрованный file_id
        hidden INTEGER DEFAULT 0,
        created TEXT DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS likes(
        from_tg INTEGER, to_tg INTEGER, kind TEXT DEFAULT 'like',
        UNIQUE(from_tg, to_tg))""",
    """CREATE TABLE IF NOT EXISTS matches(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        a INTEGER, b INTEGER, active INTEGER DEFAULT 1,
        created TEXT DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS blocks(
        from_tg INTEGER, to_tg INTEGER, UNIQUE(from_tg, to_tg))""",
    """CREATE TABLE IF NOT EXISTS reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_tg INTEGER, to_tg INTEGER, reason TEXT,
        status TEXT DEFAULT 'new',
        created TEXT DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS audit(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_tg INTEGER, action TEXT, target TEXT, details TEXT,
        created TEXT DEFAULT (datetime('now')))""",
)


async def init() -> None:
    """Создание схемы + миграции старой базы."""
    async with aiosqlite.connect(config.DB_PATH) as c:
        c.row_factory = aiosqlite.Row
        for stmt in SCHEMA:
            await c.execute(stmt)
        await _migrate(c)
        await c.commit()


async def _tables(c: aiosqlite.Connection) -> set[str]:
    cur = await c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in await cur.fetchall()}


async def _columns(c: aiosqlite.Connection, table: str) -> set[str]:
    cur = await c.execute(f"PRAGMA table_info({table})")  # table — из белого списка
    return {row[1] for row in await cur.fetchall()}


# Добавление колонок, которых не было в старой версии бота.
_MIGRATIONS: dict[str, dict[str, str]] = {
    "users": {
        "ban_reason": "ALTER TABLE users ADD COLUMN ban_reason TEXT",
        "muted_until": "ALTER TABLE users ADD COLUMN muted_until REAL DEFAULT 0",
        "rep": "ALTER TABLE users ADD COLUMN rep INTEGER DEFAULT 0",
        "accepted": "ALTER TABLE users ADD COLUMN accepted INTEGER DEFAULT 0",
    },
    "likes": {
        "kind": "ALTER TABLE likes ADD COLUMN kind TEXT DEFAULT 'like'",
    },
    "reports": {
        "status": "ALTER TABLE reports ADD COLUMN status TEXT DEFAULT 'new'",
    },
}


async def _migrate(c: aiosqlite.Connection) -> None:
    tables = await _tables(c)
    for table, columns in _MIGRATIONS.items():
        if table not in tables:
            continue
        existing = await _columns(c, table)
        for column, ddl in columns.items():
            if column not in existing:
                try:
                    await c.execute(ddl)
                except aiosqlite.OperationalError:
                    pass  # колонка уже есть / база новее схемы


# ------------------------------------------------------------ базовые запросы

async def execute(sql: str, args: tuple = ()) -> int:
    """INSERT/UPDATE/DELETE -> lastrowid."""
    async with aiosqlite.connect(config.DB_PATH) as c:
        cur = await c.execute(sql, args)
        await c.commit()
        try:
            return cur.lastrowid or 0
        finally:
            await cur.close()


async def fetchall(sql: str, args: tuple = ()) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(config.DB_PATH) as c:
        c.row_factory = aiosqlite.Row
        cur = await c.execute(sql, args)
        rows = await cur.fetchall()
        await cur.close()
        return rows


async def fetchone(sql: str, args: tuple = ()) -> aiosqlite.Row | None:
    rows = await fetchall(sql, args)
    return rows[0] if rows else None


# --------------------------------------------------------- доменные операции

async def ensure_user(tg: int) -> aiosqlite.Row:
    """Пользователь всегда существует (создаётся при первом касании)."""
    row = await fetchone("SELECT * FROM users WHERE tg=?", (tg,))
    if row:
        return row
    await execute("INSERT INTO users(tg) VALUES(?)", (tg,))
    return await fetchone("SELECT * FROM users WHERE tg=?", (tg,))  # type: ignore[return-value]


async def user_lang(tg: int) -> str:
    row = await fetchone("SELECT lang FROM users WHERE tg=?", (tg,))
    return (row["lang"] if row else "ru") or "ru"


async def get_profile(tg: int) -> aiosqlite.Row | None:
    return await fetchone("SELECT * FROM profiles WHERE tg=?", (tg,))


def decrypt_profile(row: aiosqlite.Row | None) -> dict | None:
    """Расшифровать анкету (для показа). Ничего не знает о Telegram-слое."""
    if row is None:
        return None
    box = get_box()
    return {
        "id": row["id"],
        "tg": row["tg"],
        "age": row["age"],
        "name": box.decrypt(row["name"]) or "—",
        "city": box.decrypt(row["city"]) or "",
        "about": box.decrypt(row["about"]) or "",
        "interests": box.decrypt(row["interests"]) or "",
        "photo": box.decrypt(row["photo"]),
        "hidden": row["hidden"],
    }
