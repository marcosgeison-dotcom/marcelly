"""
Memória persistente da Marcelly.
SQLite local + embeddings via Ollama para busca semântica.
Aprende preferências, fatos e padrões do usuário.
"""
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import DATA_DIR
from core.ollama_client import OllamaClient

DB_PATH = DATA_DIR / "marcelly.db"
PROFILE_PATH = DATA_DIR / "profile.json"


@dataclass
class Fact:
    key: str
    value: str
    confidence: float
    source: str
    updated_at: float


class Memory:
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.llm = OllamaClient()
        self._init_schema()
        self.profile = self._load_profile()

    def _init_schema(self):
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                user_message TEXT NOT NULL,
                intent TEXT,
                mood TEXT,
                response TEXT,
                embedding BLOB
            );
            CREATE INDEX IF NOT EXISTS idx_interactions_ts ON interactions(ts);

            CREATE TABLE IF NOT EXISTS facts (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                source TEXT,
                updated_at REAL
            );

            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL
            );

            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                occurrences INTEGER DEFAULT 1,
                last_seen REAL,
                UNIQUE(description)
            );
        """)
        self.conn.commit()

    # ---------- Perfil ----------
    def _load_profile(self) -> dict:
        if PROFILE_PATH.exists():
            return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        return {"name": "", "preferences": {}, "created_at": time.time()}

    def save_profile(self):
        PROFILE_PATH.write_text(
            json.dumps(self.profile, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def set_user_name(self, name: str):
        self.profile["name"] = name
        self.save_profile()

    # ---------- Interações ----------
    def log_interaction(
        self,
        user_message: str,
        intent: str,
        mood: str,
        response: str,
        store_embedding: bool = True,
    ):
        embedding_blob = None
        if store_embedding:
            try:
                vec = self.llm.embed(user_message[:500])
                embedding_blob = json.dumps(vec).encode("utf-8")
            except Exception:
                pass

        self.conn.execute(
            "INSERT INTO interactions (ts, user_message, intent, mood, response, embedding) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), user_message, intent, mood, response, embedding_blob),
        )
        self.conn.commit()

    def recent_interactions(self, limit: int = 10) -> list:
        rows = self.conn.execute(
            "SELECT ts, user_message, intent, mood FROM interactions "
            "ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------- Fatos ----------
    def learn_facts(self, user_message: str):
        """Extrai fatos do usuário e salva (com LLM local)."""
        system = (
            "Extraia fatos sobre o usuário do texto a seguir. "
            "Retorne APENAS JSON: {'facts': [{'key': str, 'value': str, 'confidence': 0.0-1.0}]}. "
            "Se não houver fatos, retorne {'facts': []}. "
            "Exemplos de fatos: nome, profissão, cidade, preferências, projetos, pets."
        )
        try:
            raw = self.llm.chat(user_message, system=system, format_json=True)
            data = json.loads(raw)
        except Exception:
            return

        for f in data.get("facts", []):
            key = f.get("key", "").strip()
            value = f.get("value", "").strip()
            if not key or not value:
                continue
            self.conn.execute(
                "INSERT INTO facts (key, value, confidence, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET "
                "value=excluded.value, confidence=excluded.confidence, updated_at=excluded.updated_at",
                (key, value, float(f.get("confidence", 0.6)), "auto", time.time()),
            )
        self.conn.commit()

    def get_facts(self) -> list:
        rows = self.conn.execute(
            "SELECT key, value, confidence, source, updated_at FROM facts "
            "ORDER BY updated_at DESC"
        ).fetchall()
        return [Fact(**dict(r)) for r in rows]

    def get_all_preferences(self) -> list:
        rows = self.conn.execute(
            "SELECT key, value FROM preferences ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def forget_fact(self, key: str) -> bool:
        cur = self.conn.execute("DELETE FROM facts WHERE key = ?", (key,))
        self.conn.commit()
        return cur.rowcount > 0

    # ---------- Padrões ----------
    def detect_patterns(self):
        """Detecta padrões simples (intenção + horário recorrentes)."""
        rows = self.conn.execute("""
            SELECT intent, CAST(strftime('%H', datetime(ts, 'unixepoch', 'localtime')) AS INTEGER) AS hour,
                   COUNT(*) AS n
            FROM interactions
            WHERE ts > ?
            GROUP BY intent, hour
            HAVING n >= 3
        """, (time.time() - 30 * 86400,)).fetchall()

        for r in rows:
            desc = f"Você costuma pedir '{r['intent']}' por volta das {r['hour']}h"
            self.conn.execute(
                "INSERT INTO patterns (description, occurrences, last_seen) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(description) DO UPDATE SET "
                "occurrences=occurrences+1, last_seen=excluded.last_seen",
                (desc, r["n"], time.time()),
            )
        self.conn.commit()

    def get_patterns(self, limit: int = 5) -> list:
        rows = self.conn.execute(
            "SELECT description FROM patterns ORDER BY occurrences DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [r["description"] for r in rows]

    # ---------- Preferências ----------
    def set_preference(self, key: str, value: str):
        self.conn.execute(
            "INSERT INTO preferences (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, time.time()),
        )
        self.conn.commit()

    def get_preference(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.conn.execute(
            "SELECT value FROM preferences WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    # ---------- Contexto para o LLM ----------
    def build_context(self) -> str:
        """Constrói um bloco de contexto para injetar no system prompt."""
        lines = []
        if self.profile.get("name"):
            lines.append(f"Nome do usuário: {self.profile['name']}")
        for f in self.get_facts()[:5]:
            lines.append(f"{f.key}: {f.value}")
        for p in self.get_patterns(3):
            lines.append(f"Padrão observado: {p}")
        if not lines:
            return ""
        return "Contexto aprendido:\n- " + "\n- ".join(lines)

    # ---------- Histórico por dia ----------
    def history_days(self, limit: int = 60) -> list:
        """Dias com conversas registradas, do mais recente para o mais antigo."""
        rows = self.conn.execute(
            "SELECT date(ts, 'unixepoch', 'localtime') AS day, COUNT(*) AS n "
            "FROM interactions GROUP BY day ORDER BY day DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def interactions_by_day(self, day: str, limit: int = 200) -> list:
        rows = self.conn.execute(
            "SELECT ts, user_message, intent, mood, response FROM interactions "
            "WHERE date(ts, 'unixepoch', 'localtime') = ? ORDER BY ts ASC LIMIT ?",
            (day, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def search_interactions(self, query: str, limit: int = 30) -> list:
        """Busca por assunto no histórico (texto contido em pedidos e respostas)."""
        pattern = "%" + query + "%"
        rows = self.conn.execute(
            "SELECT ts, user_message, intent, response FROM interactions "
            "WHERE user_message LIKE ? OR response LIKE ? "
            "ORDER BY ts DESC LIMIT ?",
            (pattern, pattern, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------- Manutenção: ciclo de 120 dias ----------
    CLEANUP_INTERVAL_DAYS = 120

    def days_since_cleanup_check(self):
        """Dias desde o último aviso de limpeza; None quando é a primeira execução."""
        last = self.get_preference("last_cleanup_check")
        if not last:
            return None
        try:
            return (time.time() - float(last)) / 86400.0
        except (TypeError, ValueError):
            return None

    def mark_cleanup_check(self):
        self.set_preference("last_cleanup_check", str(time.time()))

    def count_interactions_older_than(self, days: int = CLEANUP_INTERVAL_DAYS) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM interactions WHERE ts < ?",
            (time.time() - days * 86400,),
        ).fetchone()
        return row[0]

    def archive_old_interactions(self, days: int = CLEANUP_INTERVAL_DAYS) -> dict:
        """Salva uma cópia das interações antigas em JSON local e libera espaço no banco."""
        cutoff = time.time() - days * 86400
        rows = self.conn.execute(
            "SELECT id, ts, user_message, intent, mood, response FROM interactions "
            "WHERE ts < ? ORDER BY ts ASC",
            (cutoff,),
        ).fetchall()
        if not rows:
            return {"archived": 0, "file": None}
        data_dir = DB_PATH.parent
        stamp = time.strftime("%Y%m%d_%H%M%S")
        out = data_dir / ("arquivo_interacoes_" + stamp + ".json")
        payload = [
            {
                "data": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"])),
                "mensagem": r["user_message"],
                "intencao": r["intent"],
                "humor": r["mood"],
                "resposta": r["response"],
            }
            for r in rows
        ]
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.conn.execute("DELETE FROM interactions WHERE ts < ?", (cutoff,))
        self.conn.commit()
        return {"archived": len(rows), "file": out.name}
