"""Participant command and vote callbacks."""
from aiogram import F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from . import runtime
from .storage import CHOICES, PollError
from .ui import voter_keyboard, format_results

@runtime.router.message(CommandStart())
async def start(message: Message) -> None:
    if message.chat.type != "private":
        await message.answer("Откройте бота в личном чате, чтобы проголосовать.")
        return
    state = runtime.store.snapshot()
    if state["status"] == "OPEN":
        await message.answer(
            "📱 Какая ОС установлена на твоём основном смартфоне?\n\n"
            "Мы используем Telegram ID только для защиты от повторного голосования "
            "и отправки итогов. Публично показываются только общие результаты.",
            reply_markup=voter_keyboard(state["session_id"]),
        )
    elif state["status"] == "CLOSED":
        await message.answer("Голосование завершено.\n\n" + format_results(state))
    else:
        await message.answer("⏳ Голосование пока не началось. Вернись сюда немного позже.")


@runtime.router.callback_query(F.data.startswith("vote:"))
async def vote(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message or callback.message.chat.type != "private":
        await callback.answer("Голосуй в личном чате", show_alert=True)
        return
    try:
        _, session, choice = callback.data.split(":", 2)
        if not session.isdecimal() or choice not in CHOICES:
            raise ValueError("Invalid callback")
        changed = runtime.store.cast(int(session), callback.from_user.id, choice)
    except (ValueError, PollError):
        await callback.answer("Кнопка устарела. Нажми /start.", show_alert=True)
        return
    await callback.answer("✅ Голос сохранён" if changed else "Голос уже учтён")
    await callback.message.answer(
        f"✅ Твой выбор: {CHOICES[choice]}. До завершения опроса его можно изменить.",
        reply_markup=voter_keyboard(int(session)),
    )
