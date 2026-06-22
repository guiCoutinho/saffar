import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Optional

_DB_PATH = os.path.join(os.environ.get("APPDATA", "."), "Saffar", "profiles.db")


def _normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone)


class ProfileStore:
    def __init__(self, db_path: str = _DB_PATH) -> None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
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
        phone = _normalize_phone(phone)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO contacts (phone, name, last_sent_at)
                VALUES (?, ?, NULL)
                ON CONFLICT(phone) DO UPDATE SET name = excluded.name
                """,
                (phone, name),
            )

    def record_send(
        self,
        phone: str,
        message_text: str,
        status: str,
        error_reason: str = "",
    ) -> None:
        phone = _normalize_phone(phone)
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
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
        phone = _normalize_phone(phone)
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
        with self._conn:
            self._conn.execute(
                "INSERT INTO templates (name, body) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET body = excluded.body",
                (name.strip(), body),
            )

    def delete_template(self, name: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM templates WHERE name = ?", (name,))

    def list_templates(self) -> list[tuple[str, str]]:
        """Return [(name, body), ...] ordered by name."""
        rows = self._conn.execute(
            "SELECT name, body FROM templates ORDER BY name"
        ).fetchall()
        return [(r["name"], r["body"]) for r in rows]

    def close(self) -> None:
        self._conn.close()
