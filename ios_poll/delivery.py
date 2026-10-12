"""Best-effort Telegram result notification delivery."""
import asyncio
import logging
from aiogram import Bot
from . import runtime
from .ui import format_results
log = logging.getLogger(__name__)

async def deliver_results(bot: Bot, session_id: int) -> None:
    snapshot = runtime.store.snapshot(session_id)
    if snapshot["session_id"] != session_id or snapshot["status"] != "CLOSED":
        return
    message = "🏁 Голосование завершено!\n\n" + format_results(snapshot)
    while True:
        user_id = runtime.store.claim_notification(session_id)
        if user_id is None:
            break
        success = False
        try:
            await bot.send_message(user_id, message)
            success = True
        except Exception:  # individual blocked chats must not prevent other deliveries
            log.warning("Could not deliver poll results to one participant")
        finally:
            runtime.store.finish_notification(session_id, user_id, success)
        await asyncio.sleep(0.06)
