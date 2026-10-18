"""Cache local de respostas exatas para reduzir chamadas repetidas ao modelo."""
import hashlib
import sqlite3
import time

from config import DATA_DIR


class ResponseCache:
    def __init__(self, ttl_seconds: int = 24 * 60 * 60):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self.conn = sqlite3.connect(str(DATA_DIR / "marcelly.db"), check_same_thread=False)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS response_cache (cache_key TEXT PRIMARY KEY, response TEXT NOT NULL, expires_at REAL NOT NULL)"
        )
        self.conn.commit()

    @staticmethod
    def _key(prompt: str) -> str:
        normalized = " ".join(prompt.lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get(self, prompt: str) -> str | None:
        row = self.conn.execute(
            "SELECT response FROM response_cache WHERE cache_key = ? AND expires_at > ?",
            (self._key(prompt), time.time()),
        ).fetchone()
        return row[0] if row else None

    def put(self, prompt: str, response: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO response_cache (cache_key, response, expires_at) VALUES (?, ?, ?)",
            (self._key(prompt), response, time.time() + self.ttl_seconds),
        )
        self.conn.commit()
