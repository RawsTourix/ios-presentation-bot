"""Claim and record participant notification deliveries."""
from contextlib import closing
from .core import utcnow

class NotificationMixin:
    def claim_notification(self, session_id: int) -> int | None:
        """Claim one queued notification; sending rows are never claimed again automatically."""
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""
                SELECT telegram_user_id FROM notification_deliveries
                WHERE session_id=? AND status='pending' ORDER BY telegram_user_id LIMIT 1
            """, (session_id,)).fetchone()
            if row is None:
                return None
            db.execute("""
                UPDATE notification_deliveries SET status='sending',attempts=attempts+1,updated_at=?
                WHERE session_id=? AND telegram_user_id=?
            """, (utcnow(), session_id, row["telegram_user_id"]))
            db.commit()
            return row["telegram_user_id"]


    def finish_notification(self, session_id: int, user_id: int, delivered: bool) -> None:
        with closing(self._connect()) as db:
            db.execute("""
                UPDATE notification_deliveries SET status=?,updated_at=?
                WHERE session_id=? AND telegram_user_id=? AND status='sending'
            """, ("sent" if delivered else "failed", utcnow(), session_id, user_id))
