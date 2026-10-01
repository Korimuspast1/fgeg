"""Ядро безопасности.

1. Шифрование AES-256-GCM: личные поля анкет хранятся в базе зашифрованными.
   Ключ выводится из MASTER_KEY через PBKDF2-HMAC-SHA256 (200 000 итераций).
   Даже если украсть файл базы — имена, города, описания и фото прочитать нельзя.

2. RateLimiter / MuteTracker: скользящее окно лимитов и авто-мут за флуд.

3. Валидация и очистка пользовательского ввода (контрольные символы, длины).
"""
import asyncio
import base64
import hashlib
import os
import re
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import config

# ---------------------------------------------------------------- шифрование

_KDF_SALT = b"fgeg-dating-bot-v1"  # контекст вывода ключа (не секрет)


def derive_key(master_key: str) -> bytes:
    """Вывод 256-битного ключа из мастер-ключа (медленный KDF — брутфорс дорог)."""
    return hashlib.pbkdf2_hmac("sha256", master_key.encode("utf-8"), _KDF_SALT, 200_000)


class CryptoBox:
    """Шифрование строк AES-256-GCM: base64(nonce(12) + шифртекст + тег)."""

    def __init__(self, key: bytes) -> None:
        self._aes = AESGCM(key)

    def encrypt(self, text: str | None) -> str | None:
        if text is None:
            return None
        nonce = os.urandom(12)  # уникальный nonce на каждое значение
        ct = self._aes.encrypt(nonce, text.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("ascii")

    def decrypt(self, blob: str | None) -> str | None:
        if not blob:
            return None
        try:
            raw = base64.b64decode(blob.encode("ascii"))
            return self._aes.decrypt(raw[:12], raw[12:], None).decode("utf-8")
        except Exception:
            # Повреждённые/подменённые данные не должны ронять бота — вернём пусто.
            return None


_box: CryptoBox | None = None


def get_box() -> CryptoBox:
    """Синглтон шифровальщика (ленивая инициализация по MASTER_KEY)."""
    global _box
    if _box is None:
        if len(config.MASTER_KEY) < 16:
            raise RuntimeError("MASTER_KEY не задан или слишком короткий (минимум 16 символов)")
        _box = CryptoBox(derive_key(config.MASTER_KEY))
    return _box


# ---------------------------------------------------------------- анти-флуд

class RateLimiter:
    """Скользящее окно: не более `limit` событий за `window` секунд по ключу."""

    def __init__(self) -> None:
        self._events: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str, limit: int, window: float = 60.0) -> tuple[bool, float]:
        """-> (разрешено?, сколько секунд ждать)."""
        now = time.monotonic()
        async with self._lock:
            queue = [t for t in self._events.get(key, ()) if now - t < window]
            if len(queue) >= limit:
                self._events[key] = queue
                return False, round(window - (now - queue[0]), 1)
            queue.append(now)
            self._events[key] = queue
            if len(self._events) > 4096:  # защита от роста памяти
                cutoff = now - window
                self._events = {
                    k: [t for t in v if t > cutoff]
                    for k, v in self._events.items()
                    if any(t > cutoff for t in v)
                }
            return True, 0.0


class MuteTracker:
    """Нарушения внутри окна → автоматический мут. Возвращает длину мута."""

    def __init__(self, max_strikes: int = 3, window: float = 600.0, duration: float = 300.0) -> None:
        self.max_strikes = max_strikes
        self.window = window
        self.duration = duration
        self._strikes: dict[str, list[float]] = {}
        self._muted: dict[str, float] = {}

    def strike(self, key: str) -> float:
        """Засчитать нарушение. -> секунды мута (0 — мута нет)."""
        now = time.monotonic()
        until = self._muted.get(key, 0.0)
        if until > now:
            return until - now  # уже в муте — не продлеваем
        queue = [t for t in self._strikes.get(key, ()) if now - t < self.window]
        queue.append(now)
        if len(queue) >= self.max_strikes:
            self._muted[key] = now + self.duration
            self._strikes[key] = []
            return self.duration
        self._strikes[key] = queue
        return 0.0

    def remaining(self, key: str) -> float:
        until = self._muted.get(key, 0.0)
        return max(0.0, until - time.monotonic())


# ---------------------------------------------------------------- валидация

# Удаляем управляющие символы (кроме перевода строки) — защита от
# невидимых символов, ANSI-экранирования и прочего мусора.
_CTRL = {c: None for c in range(0x20)}
_CTRL.pop(0x0A)  # \n разрешён
_CTRL[0x7F] = None


def clean_text(value: str | None, max_len: int) -> str:
    """Очистка и обрезка пользовательского текста."""
    if not value:
        return ""
    value = value.translate(_CTRL).strip()
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value[:max_len]


def valid_name(value: str) -> bool:
    return 2 <= len(value) <= 40


def valid_age(value: str | None) -> bool:
    return bool(value) and value.isdigit() and 18 <= int(value) <= 99


def valid_city(value: str) -> bool:
    return 2 <= len(value) <= 60
