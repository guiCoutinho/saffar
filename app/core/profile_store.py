import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

from app.core.phone_utils import normalize_phone

_DB_PATH = os.path.join(os.environ.get("APPDATA", "."), "Saffar", "profiles.db")


class ProfileStore:
    def __init__(self, db_path: str = _DB_PATH) -> None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # record_send roda na thread de envio enquanto a UI consulta o banco
        self._lock = threading.Lock()
        self._create_tables()

    def _create_tables(self) -> None:
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS contacts (
                    phone TEXT PRIMARY KEY,
                    name TEXT,
                    last_sent_at TEXT
                );
                CREATE TABLE IF NOT EXISTS send_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT,
                    sent_at TEXT,
                    message_text TEXT,
                    status TEXT,
                    error_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS templates (
                    name TEXT PRIMARY KEY,
                    body TEXT NOT NULL
                );
            """)

    def upsert_contact(self, phone: str, name: str) -> None:
        phone = normalize_phone(phone)
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO contacts (phone, name, last_sent_at)
                VALUES (?, ?, NULL)
                ON CONFLICT(phone) DO UPDATE SET name = excluded.name
                """,
                (phone, name),
            )

    def upsert_contacts_batch(
        self, contacts: list[tuple[str, str]]
    ) -> dict[str, Optional[str]]:
        """Upsert multiple contacts and return {phone: last_sent_at} in two DB round-trips."""
        if not contacts:
            return {}
        normalized = [(normalize_phone(p), n) for p, n in contacts]
        with self._lock, self._conn:
            self._conn.executemany(
                """
                INSERT INTO contacts (phone, name, last_sent_at)
                VALUES (?, ?, NULL)
                ON CONFLICT(phone) DO UPDATE SET name = excluded.name
                """,
                normalized,
            )
        phones = [p for p, _ in normalized]
        placeholders = ",".join("?" * len(phones))
        with self._lock:
            rows = self._conn.execute(
                f"SELECT phone, last_sent_at FROM contacts WHERE phone IN ({placeholders})",
                phones,
            ).fetchall()
        return {r["phone"]: r["last_sent_at"] for r in rows}

    def record_send(
        self,
        phone: str,
        message_text: str,
        status: str,
        error_reason: str = "",
    ) -> None:
        phone = normalize_phone(phone)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO send_history (phone, sent_at, message_text, status, error_reason)
                VALUES (?, ?, ?, ?, ?)
                """,
                (phone, now, message_text, status, error_reason),
            )
            if status == "success":
                self._conn.execute(
                    """
                    UPDATE contacts SET last_sent_at = ? WHERE phone = ?
                    """,
                    (now, phone),
                )

    def get_last_sent_at(self, phone: str) -> Optional[str]:
        phone = normalize_phone(phone)
        with self._lock:
            row = self._conn.execute(
                "SELECT last_sent_at FROM contacts WHERE phone = ?", (phone,)
            ).fetchone()
        if row is None:
            return None
        return row["last_sent_at"]

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    def save_template(self, name: str, body: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO templates (name, body) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET body = excluded.body",
                (name.strip(), body),
            )

    def delete_template(self, name: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM templates WHERE name = ?", (name,))

    def list_templates(self) -> list[tuple[str, str]]:
        """Return [(name, body), ...] ordered by name."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT name, body FROM templates ORDER BY name"
            ).fetchall()
        return [(r["name"], r["body"]) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
