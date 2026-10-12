"""SQLite connection, schema, and shared state definitions."""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

CHOICES = {"ios": "iOS", "android": "Android", "other": "Другая ОС"}

class PollError(Exception):
    """Invalid poll state or stale callback."""

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

class StoreBase:
    def __init__(self, path: str | Path):
        self.path = Path(path)


    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection


    def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS poll_sessions (
                    id INTEGER PRIMARY KEY,
                    status TEXT NOT NULL CHECK(status IN ('WAITING','OPEN','CLOSED')),
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    closed_at TEXT,
                    version INTEGER NOT NULL DEFAULT 1
                );
                CREATE UNIQUE INDEX IF NOT EXISTS single_open_session
                    ON poll_sessions(status) WHERE status='OPEN';
                CREATE TABLE IF NOT EXISTS votes (
                    session_id INTEGER NOT NULL REFERENCES poll_sessions(id),
                    telegram_user_id INTEGER NOT NULL,
                    choice TEXT NOT NULL CHECK(choice IN ('ios','android','other')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(session_id,telegram_user_id)
                );
                CREATE TABLE IF NOT EXISTS notification_deliveries (
                    session_id INTEGER NOT NULL REFERENCES poll_sessions(id),
                    telegram_user_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending','sending','sent','failed')),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(session_id,telegram_user_id)
                );
            """)


    @staticmethod
    def _latest(db: sqlite3.Connection):
        return db.execute("SELECT * FROM poll_sessions ORDER BY id DESC LIMIT 1").fetchone()
