"""SQLite polling store facade."""
from .core import CHOICES, PollError, StoreBase
from .sessions import SessionMixin
from .votes import VoteMixin
from .notifications import NotificationMixin

class PollStore(SessionMixin, VoteMixin, NotificationMixin, StoreBase):
    """One source of truth for bot handlers and the future read-only API."""
