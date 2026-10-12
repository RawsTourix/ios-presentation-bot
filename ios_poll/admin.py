"""Owner-only poll actions."""
import asyncio
from aiogram import F, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from . import runtime
from .storage import PollError
from .ui import admin_keyboard, format_results
from .delivery import deliver_results

@runtime.router.message(Command("admin"))
async def admin(message: Message) -> None:
    if not message.from_user or message.from_user.id != runtime.settings.admin_telegram_id or message.chat.type != "private":
        return
    state = runtime.store.snapshot()
    await message.answer(f"Управление опросом · {state['status']}", reply_markup=admin_keyboard(state["status"], state["session_id"]))


@runtime.router.callback_query(F.data.startswith("adm:"))
async def admin_action(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or callback.from_user.id != runtime.settings.admin_telegram_id:
        await callback.answer("Нет доступа", show_alert=True)
        return
    if not callback.message or callback.message.chat.type != "private":
        await callback.answer("Используй личный чат", show_alert=True)
        return
    action, _, argument = callback.data.removeprefix("adm:").partition(":")
    if action == "stats":
        await callback.answer()
        await callback.message.answer(format_results(runtime.store.snapshot()))
        return
    if action in {"confirm", "close"}:
        current = runtime.store.snapshot()
        if not argument.isdecimal() or int(argument) != current["session_id"] or current["status"] != "OPEN":
            await callback.answer("Кнопка устарела", show_alert=True)
            return
    if action == "confirm":
        await callback.answer()
        await callback.message.answer("Завершить голосование?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Да, завершить", callback_data=f"adm:close:{argument}")],
                [InlineKeyboardButton(text="Отмена", callback_data="adm:cancel")],
            ]))
        return
    if action == "cancel":
        await callback.answer("Отменено")
        return
    if action == "start":
        try:
            session_id = runtime.store.start()
        except PollError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await callback.answer("Открыто")
        await callback.message.answer(f"▶️ Голосование №{session_id} открыто.",
                                      reply_markup=admin_keyboard("OPEN", session_id))
        return
    if action == "close":
        try:
            session_id = runtime.store.close()
        except PollError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await callback.answer("Завершено")
        await callback.message.answer("⏹ Голосование завершено.\n" + format_results(runtime.store.snapshot()),
                                      reply_markup=admin_keyboard("CLOSED", session_id))
        asyncio.create_task(deliver_results(bot, session_id))
        return
    await callback.answer("Неизвестная команда", show_alert=True)
