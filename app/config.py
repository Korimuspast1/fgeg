"""Конфигурация приложения.

Правило безопасности: ВСЕ секреты читаются только из переменных окружения
(файл .env, который не попадает в git). В коде секретов быть не должно.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int = 0) -> int:
    raw = (os.getenv(name) or "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
# Telegram ID администратора (по умолчанию — владелец проекта).
ADMIN_ID = _int_env("ADMIN_ID", 1398491942)
# Путь к базе SQLite.
DB_PATH = (os.getenv("DB_PATH") or "dating.sqlite3").strip()
# Мастер-ключ шифрования анкет (AES-256-GCM). Держи в секрете и не теряй:
# без него зашифрованные анкеты восстановить невозможно.
MASTER_KEY = (os.getenv("MASTER_KEY") or "").strip()

_BAD_TOKENS = {"", "PASTE_NEW_TOKEN_HERE", "123:ABC"}


def validate_config() -> list[str]:
    """Проверка конфигурации при старте. Возвращает список проблем."""
    problems: list[str] = []
    if BOT_TOKEN in _BAD_TOKENS:
        problems.append(
            "BOT_TOKEN не задан. Создай новый токен в @BotFather "
            "(старый отзови командой /revoke) и впиши его в .env"
        )
    if len(MASTER_KEY) < 16:
        problems.append(
            "MASTER_KEY отсутствует или короче 16 символов. Сгенерируй:\n"
            '  python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )
    if ADMIN_ID <= 0:
        problems.append("ADMIN_ID не задан в .env (укажи свой Telegram ID)")
    return problems
