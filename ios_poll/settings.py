"""Read configuration from environment without loading secrets from source code."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_telegram_id: int
    database_path: Path

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.environ.get("BOT_TOKEN", "").strip()
        admin = os.environ.get("ADMIN_TELEGRAM_ID", "").strip()
        if not token or not admin.isdecimal() or int(admin) <= 0:
            raise ValueError("Set BOT_TOKEN and positive ADMIN_TELEGRAM_ID in the environment")
        return cls(
            bot_token=token,
            admin_telegram_id=int(admin),
            database_path=Path(os.environ.get("DATABASE_PATH", "./data/poll.sqlite3")),
        )
