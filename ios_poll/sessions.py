"""Atomic poll lifecycle transitions."""
from contextlib import closing
from .core import PollError, utcnow

class SessionMixin:
    def start(self) -> int:
        """Start a fresh session. Never change a currently open session."""
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            latest = self._latest(db)
            if latest and latest["status"] == "OPEN":
                raise PollError("Голосование уже открыто")
            now = utcnow()
            cursor = db.execute(
                "INSERT INTO poll_sessions(status,created_at,started_at) VALUES('OPEN',?,?)",
                (now, now),
            )
            db.commit()
            return cursor.lastrowid


    def close(self) -> int:
        """Atomically close the active session and queue at-most-once planned notifications."""
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            session = self._latest(db)
            if not session or session["status"] != "OPEN":
                raise PollError("Нет открытого голосования")
            now = utcnow()
            session_id = session["id"]
            db.execute("""
                UPDATE poll_sessions SET status='CLOSED',closed_at=?,version=version+1
                WHERE id=? AND status='OPEN'
            """, (now, session_id))
            db.execute("""
                INSERT OR IGNORE INTO notification_deliveries(session_id,telegram_user_id,updated_at)
                SELECT session_id,telegram_user_id,? FROM votes WHERE session_id=?
            """, (now, session_id))
            db.commit()
            return session_id
