"""Atomic vote upsert and read-only aggregation."""
from contextlib import closing
from .core import CHOICES, PollError, utcnow

class VoteMixin:
    def cast(self, session_id: int, user_id: int, choice: str) -> bool:
        """Returns True only when aggregate counts change."""
        if choice not in CHOICES or user_id <= 0:
            raise ValueError("Invalid vote")
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            session = self._latest(db)
            if not session or session["id"] != session_id or session["status"] != "OPEN":
                raise PollError("Голосование уже закрыто или кнопка устарела")
            now = utcnow()
            cursor = db.execute("""
                INSERT INTO votes(session_id,telegram_user_id,choice,created_at,updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(session_id,telegram_user_id) DO UPDATE SET
                    choice=excluded.choice, updated_at=excluded.updated_at
                WHERE votes.choice != excluded.choice
            """, (session_id, user_id, choice, now, now))
            changed = cursor.rowcount > 0
            if changed:
                db.execute("UPDATE poll_sessions SET version=version+1 WHERE id=?", (session_id,))
            db.commit()
            return changed


    def get_vote(self, session_id: int, user_id: int) -> str | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT choice FROM votes WHERE session_id=? AND telegram_user_id=?",
                (session_id, user_id),
            ).fetchone()
            return row["choice"] if row else None


    def snapshot(self, session_id: int | None = None) -> dict:
        with closing(self._connect()) as db:
            session = (db.execute("SELECT * FROM poll_sessions WHERE id=?", (session_id,)).fetchone()
                       if session_id is not None else self._latest(db))
            counts = {choice: 0 for choice in CHOICES}
            if session:
                rows = db.execute("""
                    SELECT choice, COUNT(*) AS count FROM votes
                    WHERE session_id=? GROUP BY choice
                """, (session["id"],)).fetchall()
                counts.update({row["choice"]: row["count"] for row in rows})
            total = sum(counts.values())
            return {
                "session_id": session["id"] if session else None,
                "status": session["status"] if session else "WAITING",
                "version": session["version"] if session else 0,
                "total": total,
                "results": {
                    choice: {"votes": count, "percentage": round(count / total * 100, 1) if total else 0.0}
                    for choice, count in counts.items()
                },
            }
