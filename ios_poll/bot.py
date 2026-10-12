"""Start the Telegram bot with long polling."""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from . import runtime
from . import voting, admin  # import registers handlers
from .settings import Settings
from .storage import PollStore

async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    runtime.settings = Settings.from_env()
    runtime.store = PollStore(runtime.settings.database_path)
    runtime.store.init()
    dispatcher = Dispatcher()
    dispatcher.include_router(runtime.router)
    async with Bot(token=runtime.settings.bot_token) as bot:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
